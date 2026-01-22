import asyncio
import logging
from http import HTTPStatus
from os import environ
from typing import Any

import httpx
from tenacity import retry, retry_if_result, stop_after_attempt, wait_exponential

from spotify.auth import Auth
from spotify.db import DB
from spotify.schema import LikedTracksResponse, Track


class Client:
    TIMEOUT = 15
    MAX_LOG_URL_LENGTH = 120
    ME_BATCH_SIZE = 50
    BATCH_SIZE = 100
    MAX_CONCURRENT_REQUESTS = 5

    def __init__(self, auth: Auth, my_mongo: DB) -> None:
        self.logger = logging.getLogger(__name__)
        self.auth = auth
        self.api_url = "https://api.spotify.com/v1"

        self.db = my_mongo
        self.spotify_playlist_id = environ["SPOTIFY_PLAYLIST_ID"]
        self.logger.debug(
            "Initialized Client: api_url=%s playlist_id=%s",
            self.api_url,
            self.spotify_playlist_id,
        )

    async def _get_headers(self) -> dict[str, str]:
        self.logger.debug("Generating request headers using current access token")
        access_token = await self.auth.get_valid_access_token()
        self.logger.debug("Access token obtained: length=%d", len(access_token or ""))
        return {"Authorization": f"Bearer {access_token}"}

    def describe_paging_window(self, url: str) -> str:
        self.logger.debug(
            "Parsing batch window from URL: %s",
            url
            if len(url) <= self.MAX_LOG_URL_LENGTH
            else url[: self.MAX_LOG_URL_LENGTH - 3] + "...",
        )
        temp_list = url.split("?")[1].split("&")
        from_value = 0
        to_value = 0
        for item in temp_list:
            tmp_val = item.split("=")
            if tmp_val[0] == "offset":
                from_value = int(tmp_val[1])
            elif tmp_val[0] == "limit":
                to_value = int(tmp_val[1])
            else:
                raise ValueError("Invalid URL")

        human = f"from {from_value} to {from_value + to_value}"
        self.logger.debug("Computed human readable batch window: %s", human)
        return human

    async def get_available_device_id(self) -> str | None:
        self.logger.debug("Getting available device ID")
        device_id: str | None = None
        headers = await self._get_headers()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/me/player/devices", headers=headers, timeout=self.TIMEOUT
            )
        response.raise_for_status()
        response_data = response.json()
        if (
            "devices" in response_data
            and response_data["devices"]
            and "id" in response_data["devices"][0]
        ):
            device_id = response_data["devices"][0]["id"]
        self.logger.debug("Available device ID: %s", device_id)
        return device_id

    def read_latest_playlist_track_uris(self) -> list[str]:
        return self.db.get_latest_playlist_uris()

    def insert_tracks_to_db(self, tracks: list[Track]) -> None:
        self.logger.debug("Saving tracks to MongoDB: count=%d", len(tracks))
        new_tracks = []
        for t in tracks:
            mongo_track_dict = t.model_dump(by_alias=True)
            new_tracks.append(mongo_track_dict)

        self.db.insert_tracks(new_tracks)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_result(lambda r: r.status_code == HTTPStatus.TOO_MANY_REQUESTS),
    )
    async def _make_request(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        headers = await self._get_headers()
        return await client.get(url, headers=headers, timeout=self.TIMEOUT)

    async def fetch_tracks_batch(
        self, client: httpx.AsyncClient, url: str, msg: str
    ) -> LikedTracksResponse:
        self.logger.debug(
            "Fetching liked tracks batch: url=%s kind=%s timeout=%ss",
            url,
            msg,
            self.TIMEOUT,
        )

        human_readable = self.describe_paging_window(url)
        self.logger.info("Getting batch of %s tracks %s", msg, human_readable)

        response = await self._make_request(client, url)
        response.raise_for_status()
        response_data = response.json()
        if "tracks" in response_data:
            response_data = response_data["tracks"]

        try:
            result = LikedTracksResponse(**response_data)
            self.logger.debug(
                "Parsed LikedTracksResponse: items=%d next=%s", len(result.items), bool(result.next)
            )
        except Exception as e:
            self.logger.error("Error found processing %s: %s", msg, e)
            raise
        return result

    async def fetch_with_sem(
        self, client: httpx.AsyncClient, sem: asyncio.Semaphore, url: str
    ) -> LikedTracksResponse:
        async with sem:
            return await self.fetch_tracks_batch(client, url, "liked")

    async def delete_with_sem(
        self, client: httpx.AsyncClient, sem: asyncio.Semaphore, url: str, json_data: dict[str, Any]
    ) -> httpx.Response:
        headers = await self._get_headers()
        headers["Content-Type"] = "application/json"
        async with sem:
            return await client.request(
                "DELETE", url, headers=headers, json=json_data, timeout=self.TIMEOUT
            )

    async def get_all_liked_tracks(self) -> None:
        self.logger.debug("Starting retrieval of all liked tracks")
        self.logger.info("Getting all liked tracks")
        url = f"{self.api_url}/me/tracks?offset=0&limit={self.ME_BATCH_SIZE}"

        async with httpx.AsyncClient() as client:
            # Fetch first batch to get total count
            first_batch = await self.fetch_tracks_batch(client, url, "liked")
            batch_tracks = [item.track for item in first_batch.items]
            self.insert_tracks_to_db(batch_tracks)

            total = first_batch.total
            self.logger.info("Total liked tracks to fetch: %d", total)

            # Generate tasks for remaining batches
            sem = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

            tasks = []
            for offset in range(self.ME_BATCH_SIZE, total, self.ME_BATCH_SIZE):
                next_url = f"{self.api_url}/me/tracks?offset={offset}&limit={self.ME_BATCH_SIZE}"
                tasks.append(self.fetch_with_sem(client, sem, next_url))

            if tasks:
                responses = await asyncio.gather(*tasks)
                for response_data in responses:
                    batch_tracks = [item.track for item in response_data.items]
                    self.insert_tracks_to_db(batch_tracks)

        self.logger.debug("Completed retrieval of liked tracks")

    async def delete_all_playlist_tracks(self) -> None:
        self.logger.debug("Deleting playlist content: playlist_id=%s", self.spotify_playlist_id)
        self.logger.info("Deleting playlist content")
        url = f"{self.api_url}/playlists/{self.spotify_playlist_id}/tracks"

        uri_list = self.read_latest_playlist_track_uris()
        self.logger.debug("Tracks to remove: total=%d", len(uri_list))

        # Remove tracks in batches of self.BATCH_SIZE (Spotify API limit)
        async with httpx.AsyncClient() as client:
            sem = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

            tasks = []
            for i in range(0, len(uri_list), self.BATCH_SIZE):
                batch = uri_list[i : i + self.BATCH_SIZE]
                self.logger.debug("Deleting batch: size=%d index=%d", len(batch), i)
                data = {"tracks": [{"uri": uri} for uri in batch]}
                tasks.append(self.delete_with_sem(client, sem, url, data))
            responses = await asyncio.gather(*tasks)
            for response in responses:
                response.raise_for_status()

    async def populate_playlist_from_db(self) -> None:
        self.logger.debug(
            "Generating content in playlist: playlist_id=%s", self.spotify_playlist_id
        )
        self.logger.info("Generating content")
        url = f"{self.api_url}/playlists/{self.spotify_playlist_id}/tracks"
        uri_list = self.read_latest_playlist_track_uris()
        self.logger.debug("Preparing to add tracks: total=%d", len(uri_list))
        headers = await self._get_headers()
        headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient() as client:
            sem = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

            async def post_with_sem(url: str, json_data: dict[str, Any]) -> httpx.Response:
                async with sem:
                    return await client.post(
                        url, headers=headers, json=json_data, timeout=self.TIMEOUT
                    )

            tasks = []
            for i in range(0, len(uri_list), self.BATCH_SIZE):
                batch = uri_list[i : i + self.BATCH_SIZE]
                self.logger.debug("Adding batch to playlist: size=%d index=%d", len(batch), i)
                # Note: We remove 'position' to allow concurrent appends.
                # Order of blocks might vary but it's acceptable for randomness.
                data = {"uris": batch}
                tasks.append(post_with_sem(url, data))
            responses = await asyncio.gather(*tasks)
            for response in responses:
                response.raise_for_status()

    async def update_queue(self) -> None:
        device_id = await self.get_available_device_id()
        if not device_id:
            self.logger.error("No available device found")
            return
        self.logger.info("Updating playlist queue")
        url = f"{self.api_url}/me/player/play"
        if device_id:
            url += f"?device_id={device_id}"

        playlist_uri = f"spotify:playlist:{self.spotify_playlist_id}"
        headers = await self._get_headers()
        headers["Content-Type"] = "application/json"
        real_data = {
            "context_uri": playlist_uri,
            "offset": {"position": 0},
        }
        self.logger.debug("updating queue with playlist URI: %s", playlist_uri)
        async with httpx.AsyncClient() as client:
            response = await client.put(url, headers=headers, json=real_data, timeout=self.TIMEOUT)
        response.raise_for_status()

    async def get_all_playlists(self) -> None:
        self.logger.info("Getting all playlists")
        url: str | None = f"{self.api_url}/me/playlists?offset=0&limit={self.ME_BATCH_SIZE}"

        async with httpx.AsyncClient() as client:
            while url:
                self.logger.debug("Fetching playlists batch: url=%s timeout=%ss", url, self.TIMEOUT)
                headers = await self._get_headers()
                human_readable = self.describe_paging_window(url)
                self.logger.info("Getting batch of playlists %s", human_readable)
                response = await client.get(url, headers=headers, timeout=self.TIMEOUT)
                response.raise_for_status()
                response_data = response.json()

                for item in response_data.get("items", []):
                    self.logger.info(
                        "Playlist: Name='%s' ID='%s' Tracks=%d",
                        item["name"],
                        item["id"],
                        item["tracks"]["total"],
                    )

                url = response_data.get("next")

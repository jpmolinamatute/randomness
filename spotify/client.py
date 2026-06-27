import asyncio
import logging
from collections.abc import AsyncGenerator
from http import HTTPStatus
from os import environ

import httpx
from tenacity import retry, retry_if_result, stop_after_attempt, wait_exponential

from spotify.auth import Auth
from spotify.db import DB
from spotify.schema import (
    AddPlaylistPayload,
    DeletePlaylistPayload,
    HeadersType,
    LikedTracksResponse,
    PlaylistItems,
)


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

    async def _get_headers(self) -> HeadersType:
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
        url_parts = url.split("?")
        valid_number_of_parts = 2
        temp_list: list[str] = []
        if len(url_parts) == valid_number_of_parts:
            temp_list = url_parts[1].split("&")
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

    async def get_available_all_devices(self) -> list[str]:
        self.logger.debug("Getting all available device IDs")
        devices: list[str] = []
        headers = await self._get_headers()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/me/player/devices", headers=headers, timeout=self.TIMEOUT
            )
        response.raise_for_status()
        response_data = response.json()

        raw_devices = response_data.get("devices", [])
        for d in raw_devices:
            d_id = d.get("id")
            if d_id:
                devices.append(d_id)
        return devices

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_result(lambda r: r.status_code == HTTPStatus.TOO_MANY_REQUESTS),
    )
    async def _make_get_request(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        headers = await self._get_headers()
        return await client.get(url, headers=headers, timeout=self.TIMEOUT)

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_result(lambda r: r.status_code == HTTPStatus.TOO_MANY_REQUESTS),
    )
    async def _make_delete_request(
        self, client: httpx.AsyncClient, url: str, json_data: DeletePlaylistPayload
    ) -> httpx.Response:
        headers = await self._get_headers()
        headers["Content-Type"] = "application/json"
        return await client.request(
            "DELETE", url, headers=headers, json=json_data, timeout=self.TIMEOUT
        )

    @retry(
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(5),
        retry=retry_if_result(lambda r: r.status_code == HTTPStatus.TOO_MANY_REQUESTS),
    )
    async def _make_post_request(
        self,
        client: httpx.AsyncClient,
        url: str,
        json_data: AddPlaylistPayload | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        headers = await self._get_headers()
        if json_data is not None:
            headers["Content-Type"] = "application/json"
        return await client.post(
            url, headers=headers, json=json_data, params=params, timeout=self.TIMEOUT
        )

    async def fetch_liked_items(self, client: httpx.AsyncClient, url: str) -> LikedTracksResponse:
        human_readable = self.describe_paging_window(url)
        self.logger.info(
            "Fetching liked tracks batch: url=%s human_readable=%s timeout=%ss",
            url,
            human_readable,
            self.TIMEOUT,
        )
        response = await self._make_get_request(client, url)
        response.raise_for_status()
        response_data = response.json()

        try:
            result = LikedTracksResponse(**response_data)
            self.logger.debug(
                "Parsed LikedTracksResponse: items=%d next=%s", len(result.items), bool(result.next)
            )
        except Exception as e:
            self.logger.error("Error found %s", e)
            raise
        return result

    async def fetch_playlist_items(self, client: httpx.AsyncClient, url: str) -> PlaylistItems:
        human_readable = self.describe_paging_window(url)
        self.logger.info(
            "Fetching playlist items: url=%s human_readable=%s timeout=%ss",
            url,
            human_readable,
            self.TIMEOUT,
        )
        response = await self._make_get_request(client, url)
        response.raise_for_status()
        response_data = response.json()

        try:
            result = PlaylistItems(**response_data)
            self.logger.debug(
                "Parsed PlaylistItems: items=%d next=%s", len(result.items), bool(result.next)
            )
        except Exception as e:
            self.logger.error("Error found %s", e)
            raise
        return result

    async def fetch_with_sem(
        self, client: httpx.AsyncClient, sem: asyncio.Semaphore, url: str
    ) -> LikedTracksResponse | PlaylistItems:
        async with sem:
            if f"/playlists/{self.spotify_playlist_id}/items" in url:
                return await self.fetch_playlist_items(client, url)
            elif "/me/tracks" in url:
                return await self.fetch_liked_items(client, url)
            else:
                raise ValueError(f"Invalid URL for fetch_with_sem: {url}")

    async def delete_with_sem(
        self,
        client: httpx.AsyncClient,
        sem: asyncio.Semaphore,
        url: str,
        json_data: DeletePlaylistPayload,
    ) -> httpx.Response:
        async with sem:
            return await self._make_delete_request(client, url, json_data)

    async def post_with_sem(
        self,
        client: httpx.AsyncClient,
        sem: asyncio.Semaphore,
        url: str,
        json_data: AddPlaylistPayload | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        async with sem:
            return await self._make_post_request(client, url, json_data, params)

    async def get_all_liked_tracks(self) -> None:
        self.logger.debug("Starting retrieval of all liked tracks")
        self.logger.info("Getting all liked tracks")
        url = f"{self.api_url}/me/tracks?offset=0&limit={self.ME_BATCH_SIZE}"
        all_tracks = []

        async with httpx.AsyncClient() as client:
            first_batch = await self.fetch_liked_items(client, url)
            all_tracks.extend([item.track for item in first_batch.items if item.track])
            sem = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

            tasks = []
            for offset in range(self.ME_BATCH_SIZE, first_batch.total, self.ME_BATCH_SIZE):
                next_url = f"{self.api_url}/me/tracks?offset={offset}&limit={self.ME_BATCH_SIZE}"
                tasks.append(self.fetch_with_sem(client, sem, next_url))

            if tasks:
                responses = await asyncio.gather(*tasks)
                for response_data in responses:
                    all_tracks.extend([item.track for item in response_data.items if item.track])

        # Do a single sync at the end
        self.db.sync_tracks(all_tracks)
        self.logger.debug("Completed retrieval of liked tracks")

    async def _yield_playlist_tracks_batches(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[list[str]]:
        """Yield batches of track URIs from the playlist, always fetching from offset 0."""
        url = f"{self.api_url}/playlists/{self.spotify_playlist_id}/items"
        while True:
            try:
                response_data = await self.fetch_playlist_items(client, url)
                items = response_data.items
                if not items:
                    break

                uris = [playlist_item.item.uri for playlist_item in items if playlist_item.item]
                if not uris:
                    break

                yield uris

                # If the total items reported in this response is <= what we just processed,
                # then this is the last batch and we don't need to fetch again.
                if response_data.total <= len(uris):
                    break

            except Exception:
                self.logger.exception("Error fetching playlist tracks batch")
                break

    async def delete_all_playlist_tracks(self) -> None:
        self.logger.debug("Deleting playlist content: playlist_id=%s", self.spotify_playlist_id)
        self.logger.info("Deleting playlist content")
        url = f"{self.api_url}/playlists/{self.spotify_playlist_id}/items"

        async with httpx.AsyncClient() as client:
            sem = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

            # Use async generator to process batches
            async for batch_uris in self._yield_playlist_tracks_batches(client):
                self.logger.debug("Deleting batch: size=%d", len(batch_uris))
                data: DeletePlaylistPayload = {"items": [{"uri": uri} for uri in batch_uris]}
                try:
                    await self.delete_with_sem(client, sem, url, data)
                except Exception:
                    self.logger.exception("Failed to delete batch")
                    raise

    async def populate_playlist_with_uris(self, uri_list: list[str]) -> None:
        self.logger.debug(
            "Generating content in playlist: playlist_id=%s", self.spotify_playlist_id
        )
        self.logger.info("Generating content")
        url = f"{self.api_url}/playlists/{self.spotify_playlist_id}/items"
        self.logger.debug("Preparing to add tracks: total=%d", len(uri_list))

        async with httpx.AsyncClient() as client:
            sem = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

            tasks = []
            for i in range(0, len(uri_list), self.BATCH_SIZE):
                batch = uri_list[i : i + self.BATCH_SIZE]
                self.logger.debug("Adding batch to playlist: size=%d index=%d", len(batch), i)
                # Note: We remove 'position' to allow concurrent appends.
                # Order of blocks might vary but it's acceptable for randomness.
                data: AddPlaylistPayload = {"uris": batch}
                tasks.append(self.post_with_sem(client, sem, url, json_data=data))
            responses = await asyncio.gather(*tasks)
            for response in responses:
                response.raise_for_status()

    async def update_queue(self, uri_list: list[str]) -> None:
        devices = await self.get_available_all_devices()
        sem = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)

        async def queue_device(client: httpx.AsyncClient, device_id: str) -> None:
            for uri in uri_list:
                url = f"{self.api_url}/me/player/queue"
                params = {
                    "device_id": device_id,
                    "uri": uri,
                }
                self.logger.info("Adding track %s to queue for device %s", uri, device_id)
                response = await self.post_with_sem(client, sem, url, params=params)
                response.raise_for_status()

        async with httpx.AsyncClient() as client:
            await asyncio.gather(*(queue_device(client, d) for d in devices))

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

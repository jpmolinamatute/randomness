import logging
from os import environ

import requests

from spotify.auth import Auth
from spotify.db import DB
from spotify.schema import LikedTracksResponse, Track


class Client:
    TIMEOUT = 15
    ME_BATCH_SIZE = 50
    BATCH_SIZE = 100

    def __init__(self, auth: Auth, my_mongo: DB) -> None:
        self.logger = logging.getLogger(__name__)
        self.auth = auth
        self.api_url = "https://api.spotify.com/v1"

        self.tracks_coll = my_mongo.get_tracks_coll()
        self.playlist_coll = my_mongo.get_playlist_coll()
        self.spotify_playlist_id = environ["SPOTIFY_PLAYLIST_ID"]
        self.logger.debug(
            "Initialized Client: api_url=%s playlist_id=%s",
            self.api_url,
            self.spotify_playlist_id,
        )

    def _get_headers(self) -> dict[str, str]:
        self.logger.debug("Generating request headers using current access token")
        access_token = self.auth.get_valid_access_token()
        self.logger.debug("Access token obtained: length=%d", len(access_token or ""))
        return {"Authorization": f"Bearer {access_token}"}

    def describe_paging_window(self, url: str) -> str:
        self.logger.debug(
            "Parsing batch window from URL: %s", url if len(url) <= 120 else url[:117] + "..."
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

    def fetch_tracks_batch(self, url: str, msg: str) -> LikedTracksResponse:
        self.logger.debug(
            "Fetching liked tracks batch: url=%s kind=%s timeout=%ss",
            url,
            msg,
            self.TIMEOUT,
        )
        headers = self._get_headers()
        human_readable = self.describe_paging_window(url)
        self.logger.info("Getting batch of %s tracks %s", msg, human_readable)
        response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
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

    def insert_tracks_to_db(self, tracks: list[Track]) -> None:
        self.logger.debug("Saving tracks to MongoDB: count=%d", len(tracks))
        new_tracks = []
        for t in tracks:
            mongo_track_dict = t.model_dump(by_alias=True)
            new_tracks.append(mongo_track_dict)

        self.tracks_coll.insert_many(new_tracks)

    def get_all_liked_tracks(self) -> None:
        self.logger.debug("Starting retrieval of all liked tracks")
        self.logger.info("Getting all liked tracks")
        url: str | None = f"{self.api_url}/me/tracks?offset=0&limit={self.ME_BATCH_SIZE}"

        while url:
            response_data = self.fetch_tracks_batch(url=url, msg="liked")
            batch_tracks = [item.track for item in response_data.items]
            self.insert_tracks_to_db(batch_tracks)
            url = response_data.next

        self.logger.debug("Completed retrieval of liked tracks")

    def read_latest_playlist_track_uris(self) -> list[str]:
        self.logger.debug("Reading playlist from DB")
        uri_list = []
        playlist = self.playlist_coll.find_one(
            sort=[("created_at", -1)], projection={"tracks.uri": 1, "_id": 0}
        )
        if playlist:
            uri_list = [track["uri"] for track in playlist["tracks"]]
        self.logger.info("Read %d tracks from the playlist", len(uri_list))
        return uri_list

    def delete_all_playlist_tracks(self) -> None:
        self.logger.debug("Deleting playlist content: playlist_id=%s", self.spotify_playlist_id)
        self.logger.info("Deleting playlist content")
        url = f"{self.api_url}/playlists/{self.spotify_playlist_id}/tracks"
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"

        uri_list = self.read_latest_playlist_track_uris()
        self.logger.debug("Tracks to remove: total=%d", len(uri_list))

        # Remove tracks in batches of self.BATCH_SIZE (Spotify API limit)
        for i in range(0, len(uri_list), self.BATCH_SIZE):
            batch = uri_list[i : i + self.BATCH_SIZE]
            self.logger.debug("Deleting batch: size=%d index=%d", len(batch), i)
            data = {"tracks": [{"uri": uri} for uri in batch]}
            response = requests.delete(url, headers=headers, json=data, timeout=self.TIMEOUT)
            response.raise_for_status()

    def get_all_playlists(self) -> None:
        self.logger.info("Getting all playlists")
        url: str | None = f"{self.api_url}/me/playlists?offset=0&limit={self.ME_BATCH_SIZE}"

        while url:
            self.logger.debug("Fetching playlists batch: url=%s timeout=%ss", url, self.TIMEOUT)
            headers = self._get_headers()
            human_readable = self.describe_paging_window(url)
            self.logger.info("Getting batch of playlists %s", human_readable)
            response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
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

    def update_queue(self) -> None:
        self.logger.info("Updating playlist queue")
        url = f"{self.api_url}/me/player/play"
        playlist_uri = f"spotify:playlist:{self.spotify_playlist_id}"
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"
        real_data = {
            "context_uri": playlist_uri,
            "offset": {"position": 0},
        }
        self.logger.debug("updating queue with playlist URI: %s", playlist_uri)
        response = requests.put(url, headers=headers, json=real_data, timeout=self.TIMEOUT)
        response.raise_for_status()

    def populate_playlist_from_db(self) -> None:
        self.logger.debug(
            "Generating content in playlist: playlist_id=%s", self.spotify_playlist_id
        )
        self.logger.info("Generating content")
        url = f"{self.api_url}/playlists/{self.spotify_playlist_id}/tracks"
        uri_list = self.read_latest_playlist_track_uris()
        self.logger.debug("Preparing to add tracks: total=%d", len(uri_list))
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"
        for i in range(0, len(uri_list), self.BATCH_SIZE):
            batch = uri_list[i : i + self.BATCH_SIZE]
            self.logger.debug("Adding batch to playlist: size=%d index=%d", len(batch), i)
            data = {"uris": batch, "position": i}
            response = requests.post(url, headers=headers, json=data, timeout=self.TIMEOUT)
            response.raise_for_status()

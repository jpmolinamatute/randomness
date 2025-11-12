import logging
from os import environ
from pathlib import Path

import requests
from bson import encode
from bson.raw_bson import RawBSONDocument

from spotify.auth import Auth
from spotify.db import DB
from spotify.types import LikedTracksResponse, Track


TIMEOUT = 15


class Client:
    def __init__(self, auth: Auth, my_mongo: DB) -> None:
        self.logger = logging.getLogger(__name__)
        self.auth = auth
        self.api_url = "https://api.spotify.com/v1"

        self.mongo_tracks_collection = my_mongo.get_tracks_collection()
        self.mongo_playlist_collection = my_mongo.get_playlist_collection()
        self.filename = Path(__name__).parent.joinpath("liked_tracks.csv")
        self.spotify_playlist_id = environ["SPOTIFY_PLAYLIST_ID"]
        self.logger.debug(
            "Initialized Client: api_url=%s playlist_id=%s filename=%s",
            self.api_url,
            self.spotify_playlist_id,
            self.filename,
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
            TIMEOUT,
        )
        headers = self._get_headers()
        human_readable = self.describe_paging_window(url)
        self.logger.info("Getting batch of %s tracks %s", msg, human_readable)
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
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

    def clean_csv_field(self, csv_field: str) -> str:
        self.logger.debug("Cleaning CSV field: original_len=%d", len(csv_field))
        return csv_field.replace(",", " ")

    def get_all_liked_tracks(self) -> list[Track]:
        self.logger.debug("Starting retrieval of all liked tracks")
        self.logger.info("Getting all liked tracks")
        all_tracks: list[Track] = []
        url: str | None = f"{self.api_url}/me/tracks?offset=0&limit=50"

        while url:
            response_data = self.fetch_tracks_batch(url=url, msg="liked")
            batch_tracks = [item.track for item in response_data.items]
            all_tracks.extend(batch_tracks)
            self.insert_tracks(batch_tracks)
            url = response_data.next
        self.save_tracks_to_file(all_tracks)

        self.logger.debug("Completed retrieval of liked tracks: total=%d", len(all_tracks))
        return all_tracks

    def insert_tracks(self, tracks: list[Track]) -> None:
        self.logger.debug("Saving tracks to MongoDB: count=%d", len(tracks))
        new_tracks = []
        for t in tracks:
            mongo_track_dict = t.to_dict(True)
            bson_data = encode(mongo_track_dict)
            raw_bson_document = RawBSONDocument(bson_data)
            new_tracks.append(raw_bson_document)

        self.mongo_tracks_collection.insert_many(new_tracks)

    def save_tracks_to_file(self, tracks: list[Track]) -> None:
        self.logger.debug(
            "Writing tracks to CSV file: path=%s count=%d", self.filename, len(tracks)
        )
        with open(self.filename, "w", encoding="utf-8") as f:
            f.write("Artist,Track,Album\n")
            for track in tracks:
                artist = self.clean_csv_field(track.artists[0].name)
                name = self.clean_csv_field(track.name)
                album = self.clean_csv_field(track.album.name)
                f.write(f"{artist},{name},{album}\n")

    def get_playlist_tracks(self) -> list[Track]:
        self.logger.debug("Fetching playlist tracks: playlist_id=%s", self.spotify_playlist_id)
        self.logger.info("Getting playlist tracks")
        all_tracks = []
        url: str | None = (
            f"{self.api_url}/playlists/{self.spotify_playlist_id}/tracks?offset=0&limit=50"
        )

        while url:
            response_data = self.fetch_tracks_batch(url, "playlist")
            batch_tracks = [item.track for item in response_data.items]
            all_tracks.extend(batch_tracks)
            url = response_data.next

        self.logger.debug("Fetched playlist tracks: total=%d", len(all_tracks))
        return all_tracks

    def delete_all_playlist_tracks(self) -> None:
        self.logger.debug("Deleting playlist content: playlist_id=%s", self.spotify_playlist_id)
        self.logger.info("Deleting playlist content")
        url = f"{self.api_url}/playlists/{self.spotify_playlist_id}/tracks"
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"

        # Get all tracks in the playlist
        playlist_tracks = self.get_playlist_tracks()
        track_uris = [{"uri": track.uri} for track in playlist_tracks]
        self.logger.debug("Tracks to remove: total=%d", len(track_uris))

        # Remove tracks in batches of 100 (Spotify API limit)
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i : i + 100]
            self.logger.debug("Deleting batch: size=%d index=%d", len(batch), i)
            data = {"tracks": batch}
            response = requests.delete(url, headers=headers, json=data, timeout=TIMEOUT)
            response.raise_for_status()

    def read_latest_playlist_track_ids(self) -> list[str]:
        self.logger.debug("Reading playlist from DB")
        id_list = []
        playlist = self.mongo_playlist_collection.find_one(
            sort=[("created_at", -1)], projection={"tracks._id": 1, "_id": 0}
        )
        if playlist:
            id_list = [track["_id"] for track in playlist["tracks"]]
        self.logger.info("Read %d tracks from the playlist", len(id_list))
        return id_list

    def populate_playlist_from_db(self) -> None:
        self.logger.debug(
            "Generating content in playlist: playlist_id=%s", self.spotify_playlist_id
        )
        self.logger.info("Generating content")
        url = f"{self.api_url}/playlists/{self.spotify_playlist_id}/tracks"
        id_list = self.read_latest_playlist_track_ids()
        self.logger.debug("Preparing to add tracks: total=%d", len(id_list))
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"
        for i in range(0, len(id_list), 50):
            chunk = id_list[i : i + 50]
            self.logger.debug("Adding batch to playlist: size=%d index=%d", len(chunk), i)
            data = {"uris": [f"spotify:track:{track_id}" for track_id in chunk]}
            response = requests.post(url, headers=headers, json=data, timeout=TIMEOUT)
            if response.status_code != 201:
                self.logger.error(
                    "Failed to add tracks: %d, %s", response.status_code, response.json()
                )

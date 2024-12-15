from os import environ
from pathlib import Path

import requests
from bson import encode
from bson.raw_bson import RawBSONDocument

from src.auth import SpotifyAuth
from src.db_client import DBClient
from src.logger import Logger
from src.spotify_types import LikedTracksResponse, Track


TIMEOUT = 15


class SpotifyClient:
    def __init__(self, auth: SpotifyAuth, my_mongo: DBClient) -> None:
        self.auth = auth
        self.logger = Logger().get_logger()
        self.api_url = "https://api.spotify.com/v1"

        self.mongo_tracks_collection = my_mongo.get_tracks_collection()
        self.mongo_playlist_collection = my_mongo.get_playlist_collection()
        self.filename = Path(__name__).parent.joinpath("liked_tracks.csv")
        self.spotify_playlist_id = environ["SPOTIFY_PLAYLIST_ID"]

    def _get_headers(self) -> dict[str, str]:
        access_token = self.auth.get_valid_access_token()
        return {"Authorization": f"Bearer {access_token}"}

    def get_human_readable_batch_name(self, url: str) -> str:
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

        return f"from {from_value} to {from_value + to_value}"

    def get_liked_tracks_batch(self, url: str, msg: str) -> LikedTracksResponse:
        headers = self._get_headers()
        human_readable = self.get_human_readable_batch_name(url)
        self.logger.info(f"Getting batch of {msg} tracks {human_readable}")
        response = requests.get(url, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        response_data = response.json()
        if "tracks" in response_data:
            response_data = response_data["tracks"]

        try:
            result = LikedTracksResponse(**response_data)
        except Exception as e:
            self.logger.error(f"Error found processing {msg}: {e}")
            raise
        return result

    def clean_cvs_field(self, csv_field: str) -> str:
        return csv_field.replace(",", " ")

    def get_all_liked_tracks(self) -> list[Track]:
        self.logger.info("Getting all liked tracks")
        all_tracks: list[Track] = []
        url: str | None = f"{self.api_url}/me/tracks?offset=0&limit=50"

        while url:
            response_data = self.get_liked_tracks_batch(url=url, msg="liked")
            batch_tracks = [item.track for item in response_data.items]
            all_tracks.extend(batch_tracks)
            self.save_tracks_to_mongodb(batch_tracks)
            url = response_data.next
        self.save_tracks_to_file(all_tracks)

        return all_tracks

    def save_tracks_to_mongodb(self, tracks: list[Track]) -> None:
        new_tracks = []
        for t in tracks:
            mongo_track_dict = t.to_dict(True)
            bson_data = encode(mongo_track_dict)
            raw_bson_document = RawBSONDocument(bson_data)
            new_tracks.append(raw_bson_document)

        self.mongo_tracks_collection.insert_many(new_tracks)

    def save_tracks_to_file(self, tracks: list[Track]) -> None:
        with open(self.filename, "w", encoding="utf-8") as f:
            f.write("Artist,Track,Album\n")
            for track in tracks:
                artist = self.clean_cvs_field(track.artists[0].name)
                name = self.clean_cvs_field(track.name)
                album = self.clean_cvs_field(track.album.name)
                f.write(f"{artist},{name},{album}\n")

    def get_playlist_tracks(self) -> list[Track]:
        self.logger.info("Getting playlist tracks")
        all_tracks = []
        url: str | None = (
            f"{self.api_url}/playlists/{self.spotify_playlist_id}/tracks?offset=0&limit=50"
        )

        while url:
            response_data = self.get_liked_tracks_batch(url, "playlist")
            batch_tracks = [item.track for item in response_data.items]
            all_tracks.extend(batch_tracks)
            url = response_data.next

        return all_tracks

    def delete_playlist_content(self) -> None:
        self.logger.info("Deleting playlist content")
        url = f"{self.api_url}/playlists/{self.spotify_playlist_id}/tracks"
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"

        # Get all tracks in the playlist
        playlist_tracks = self.get_playlist_tracks()
        track_uris = [{"uri": track.uri} for track in playlist_tracks]

        # Remove tracks in batches of 100 (Spotify API limit)
        for i in range(0, len(track_uris), 100):
            batch = track_uris[i : i + 100]
            data = {"tracks": batch}
            response = requests.delete(url, headers=headers, json=data, timeout=TIMEOUT)
            response.raise_for_status()

    def read_playlist_from_db(self) -> list[str]:
        id_list = []
        playlist = self.mongo_playlist_collection.find_one(
            sort=[("created_at", -1)], projection={"tracks._id": 1, "_id": 0}
        )
        if playlist:
            id_list = [track["_id"] for track in playlist["tracks"]]
        self.logger.info(f"Read {len(id_list)} tracks from the playlist")
        return id_list

    def generate_content(self) -> None:
        self.logger.info("Generating content")
        url = f"{self.api_url}/playlists/{self.spotify_playlist_id}/tracks"
        id_list = self.read_playlist_from_db()
        headers = self._get_headers()
        headers["Content-Type"] = "application/json"
        for i in range(0, len(id_list), 50):
            chunk = id_list[i : i + 50]
            data = {"uris": [f"spotify:track:{track_id}" for track_id in chunk]}
            response = requests.post(url, headers=headers, json=data, timeout=TIMEOUT)
            if response.status_code != 201:
                print(f"Failed to add tracks: {response.status_code}, {response.json()}")

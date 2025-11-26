import json
import logging
from collections.abc import Mapping
from datetime import date
from os import environ
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection


type CollType = dict[str, Any]


class DB:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        # Read connection settings from environment and initialize client/db.
        mongo_user = environ["MONGO_INITDB_ROOT_USERNAME"]
        mongo_password = environ["MONGO_INITDB_ROOT_PASSWORD"]
        mongo_db_name = environ["MONGO_INITDB_DATABASE"]
        self.logger.debug(
            "Initializing DB: connecting to MongoDB on %s with user=%s, database=%s",
            "localhost:27017",
            mongo_user,
            mongo_db_name,
        )
        # Do not log raw password; mask if ever needed.
        mongo_uri = f"mongodb://{mongo_user}:{mongo_password}@localhost:27017"
        self.mongo_client: MongoClient[CollType] = MongoClient(mongo_uri)
        self.mongo_db = self.mongo_client[mongo_db_name]
        self.playlist_coll_name = "playlist"
        self.tracks_coll_name = "tracks"

    def count_track(self, mongo_filters: Mapping[str, Any]) -> int:
        """Delegate to tracks collection count for testing convenience."""
        self.logger.debug("Counting documents in 'tracks' with filters=%s", mongo_filters)
        return self.get_tracks_coll().count_documents(mongo_filters)

    def check_connection(self) -> bool:
        self.logger.debug("Checking MongoDB connection via server_info()")
        is_up = True
        try:
            info = self.mongo_client.server_info()
            version = info.get("version")
            is_primary = getattr(self.mongo_client, "is_primary", None)
            self.logger.debug(
                "MongoDB connection ok: version=%s, is_primary=%s", version, is_primary
            )
        except Exception:
            self.logger.exception("MongoDB is not available", exc_info=True)
            is_up = False
        return is_up

    def get_tracks_coll(self) -> Collection[CollType]:
        self.logger.debug("Retrieving collection: %s", self.tracks_coll_name)
        return self.mongo_db[self.tracks_coll_name]

    def get_playlist_coll(self) -> Collection[CollType]:
        self.logger.debug("Retrieving collection: %s", self.playlist_coll_name)
        return self.mongo_db[self.playlist_coll_name]

    def export_to_json(self) -> None:
        self.logger.debug("Exporting tracks to JSON")
        tracks = self.get_tracks_coll().find({})
        export_data = []
        for track in tracks:
            # Safely get artist name
            artists = track.get("artists", [])
            artist_name = (
                artists[0].get("name")
                if artists and isinstance(artists, list) and len(artists) > 0
                else "Unknown"
            )

            data = {
                "_id": str(track.get("_id")),
                "href": track.get("href"),
                "name": track.get("name"),
                "artist_name": artist_name,
            }
            export_data.append(data)

        filename = f"export-{date.today()}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=4)

        self.logger.info("Exported %d tracks to %s", len(export_data), filename)

    def close(self) -> None:
        self.logger.debug("Closing MongoDB client connection")
        self.mongo_client.close()

import json
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from os import environ
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo import MongoClient, UpdateOne
from pymongo.collection import Collection
from pymongo.errors import AutoReconnect

from spotify.custom_types import RandomnessType

type CollType = dict[str, Any]


class DB:
    MAX_SIZE_WINDOW = 300
    RATIO_WINDOW = 3
    MAX_PLAYLIST_ITEMS = 100

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
        mongo_uri = f"mongodb://{mongo_user}:{mongo_password}@localhost:27017/?maxIdleTimeMS=50000"
        self.mongo_client: MongoClient[CollType] = MongoClient(mongo_uri)
        self.mongo_db = self.mongo_client[mongo_db_name]
        self.tracks_coll_name = "tracks"

    def close(self) -> None:
        self.logger.debug("Closing MongoDB client connection")
        self.mongo_client.close()

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
            # Create indexes now that we know the DB is up
            self.logger.debug("Ensuring indexes on %s", self.tracks_coll_name)
            self.mongo_db[self.tracks_coll_name].create_index("uri", unique=True)
            self.mongo_db[self.tracks_coll_name].create_index("played_at")
            self.mongo_db[self.tracks_coll_name].create_index("artists._id")
        except Exception:
            self.logger.exception("MongoDB is not available", exc_info=True)
            is_up = False
        return is_up

    def get_tracks_coll(self) -> Collection[CollType]:
        self.logger.debug("Retrieving collection: %s", self.tracks_coll_name)
        return self.mongo_db[self.tracks_coll_name]

    def count_track(self, mongo_filters: Mapping[str, Any]) -> int:
        """Delegate to tracks collection count for testing convenience."""
        self.logger.debug("Counting documents in 'tracks' with filters=%s", mongo_filters)
        return self.get_tracks_coll().count_documents(mongo_filters)

    def sync_tracks(self, tracks: list[dict[str, Any]]) -> None:
        self.logger.debug("Syncing tracks to MongoDB: sum=%d", len(tracks))

        existing_uris_cursor = self.get_tracks_coll().find({}, {"uri": 1})
        existing_uris = {doc.get("uri") for doc in existing_uris_cursor if doc.get("uri")}
        incoming_uris = {t.get("uri") for t in tracks if t.get("uri")}

        uris_to_delete = existing_uris - incoming_uris
        if uris_to_delete:
            self.logger.info("Deleting %d missing tracks from DB", len(uris_to_delete))
            self.get_tracks_coll().delete_many({"uri": {"$in": list(uris_to_delete)}})

        operations = []
        for t in tracks:
            # Upsert track metadata, preserve or initialize played_at
            update_doc = {"$set": t, "$setOnInsert": {"played_at": None}}
            operations.append(UpdateOne({"uri": t["uri"]}, update_doc, upsert=True))

        if operations:
            batch_size = 500
            max_retries = 5
            for i in range(0, len(operations), batch_size):
                batch = operations[i : i + batch_size]
                for attempt in range(max_retries):
                    try:
                        self.get_tracks_coll().bulk_write(batch)
                        break
                    except AutoReconnect:
                        if attempt == max_retries - 1:
                            raise
                        self.logger.warning(
                            "AutoReconnect in bulk_write (Docker idle timeout). Retrying batch."
                        )
            self.logger.info("Upserted %d tracks into DB", len(operations))

    def reset_collection(self, collection_name: str) -> None:
        self.logger.debug("Resetting collection: %s", collection_name)
        if collection_name == self.tracks_coll_name:
            self.logger.warning("tracks collection is no longer reset; use sync_tracks instead")
        else:
            raise ValueError("Invalid collection name")

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
        with Path(filename).open("w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=4)

        self.logger.info("Exported %d tracks to %s", len(export_data), filename)

    def validate_item_count(self, no_items: int) -> None:
        self.logger.debug("Validating requested item count: no_items=%s", no_items)
        if not isinstance(no_items, int):
            raise ValueError("Number of items must be an integer")
        if no_items < 1:
            raise ValueError("Number of items must be greater than 0")
        if no_items > self.MAX_PLAYLIST_ITEMS:
            raise ValueError(
                f"Number of items must be less than or equal to {self.MAX_PLAYLIST_ITEMS}"
            )
        # Use DB-level count_documents to align with test mocks.
        max_no_item = self.count_track({})
        self.logger.debug("Max items available according to DB: %s", max_no_item)

        if max_no_item and no_items > max_no_item:
            raise ValueError(f"Number of items must be less than {max_no_item}")

    def generate_random_tracks(self, no_items: int) -> list[str]:
        self.logger.debug("Building random track pipeline: no_items=%d", no_items)
        self.logger.info(
            "Generating a playlist with %d items using Least-Recently-Played logic", no_items
        )

        window_size = max(no_items * self.RATIO_WINDOW, self.MAX_SIZE_WINDOW)
        pipeline: Sequence[Mapping[str, Any]] = [
            {"$sort": {"played_at": 1}},
            {"$limit": window_size},
            {"$sample": {"size": no_items}},
            {
                "$group": {
                    "_id": ObjectId(),
                    "tracks": {"$push": "$$ROOT"},
                    "created_at": {"$first": datetime.now(UTC)},
                }
            },
        ]

        cursor = self.get_tracks_coll().aggregate(pipeline)
        result = list(cursor)
        cursor.close()

        latest_uris = [track.get("uri") for track in result[0].get("tracks", [])] if result else []

        if latest_uris:
            self.get_tracks_coll().update_many(
                {"uri": {"$in": latest_uris}}, {"$set": {"played_at": datetime.now(UTC)}}
            )
            self.logger.debug("Marked %d tracks as played", len(latest_uris))

        return latest_uris

    def generate_random_playlist(self, item_type: RandomnessType, no_items: int) -> list[str]:
        self.logger.debug(
            "Dispatching generate_random_playlist: type=%s no_items=%d", item_type, no_items
        )
        self.validate_item_count(no_items)
        if item_type == "track":
            return self.generate_random_tracks(no_items)
        else:
            raise ValueError("Invalid item type")

import json
import logging
import random
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from os import environ
from typing import Any

from bson import ObjectId
from pymongo import MongoClient
from pymongo.collection import Collection

from spotify.types import RandomnessType


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
        self.artist_sampling_ratio = 0.25

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

    def _randomize(self, whole_sample: list[str]) -> list[str]:
        self.logger.debug(
            "Randomizing sample: input_len=%d randomness_percentage=%.2f",
            len(whole_sample) if isinstance(whole_sample, list) else -1,
            self.artist_sampling_ratio,
        )
        if not isinstance(whole_sample, list):
            raise ValueError("'whole_sample' must be a list")
        if not whole_sample:
            raise ValueError("'whole_sample' must not be empty")
        max_no_item = len(whole_sample)
        no_of_item = int(max_no_item * self.artist_sampling_ratio)
        self.logger.debug("Sampling without replacement: max=%d pick=%d", max_no_item, no_of_item)
        return random.sample(whole_sample, no_of_item)

    def count_track(self, mongo_filters: Mapping[str, Any]) -> int:
        """Delegate to tracks collection count for testing convenience."""
        self.logger.debug("Counting documents in 'tracks' with filters=%s", mongo_filters)
        return self.get_tracks_coll().count_documents(mongo_filters)

    def insert_tracks(self, tracks: list[dict[str, Any]]) -> None:
        self.logger.debug("Saving tracks to MongoDB: count=%d", len(tracks))
        self.get_tracks_coll().insert_many(tracks)

    def get_latest_playlist_uris(self) -> list[str]:
        self.logger.debug("Reading playlist from DB")
        uri_list = []
        playlist = self.get_playlist_coll().find_one(
            sort=[("created_at", -1)], projection={"tracks.uri": 1, "_id": 0}
        )
        if playlist:
            uri_list = [track["uri"] for track in playlist["tracks"]]
        self.logger.info("Read %d tracks from the playlist", len(uri_list))
        return uri_list

    def reset_collection(self, collection_name: str) -> None:
        self.logger.debug("Resetting collection: %s", collection_name)
        if collection_name == self.tracks_coll_name:
            self.get_tracks_coll().delete_many({})
        elif collection_name == self.playlist_coll_name:
            self.get_playlist_coll().delete_many({})
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
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=4)

        self.logger.info("Exported %d tracks to %s", len(export_data), filename)

    def get_artist_ids(self) -> list[str]:
        self.logger.debug("Aggregating distinct artist IDs from tracks collection")
        pipeline: Sequence[Mapping[str, Any]] = [
            {"$unwind": "$artists"},
            {"$group": {"_id": "$artists._id"}},
            {"$project": {"_id": 1}},
        ]
        cursor = self.get_tracks_coll().aggregate(pipeline)
        result = [doc["_id"] for doc in cursor]
        cursor.close()
        self.logger.debug("Found %d distinct artist IDs", len(result))
        return result

    def validate_item_count(self, no_items: int) -> None:
        self.logger.debug("Validating requested item count: no_items=%s", no_items)
        if not isinstance(no_items, int):
            raise ValueError("Number of items must be an integer")
        if no_items < 1:
            raise ValueError("Number of items must be greater than 0")
        if no_items > 100:
            raise ValueError("Number of items must be less than or equal to 100")
        # Use DB-level count_documents to align with test mocks.
        max_no_item = self.count_track({})
        self.logger.debug("Max items available according to DB: %s", max_no_item)

        if max_no_item and no_items > max_no_item:
            raise ValueError(f"Number of items must be less than {max_no_item}")

    def get_recent_playlist_uris(self, limit: int = 3) -> list[str]:
        """Get URIs from the last `limit` playlists to avoid repetition."""
        self.logger.debug("Fetching last %d playlists for exclusion", limit)
        recent_playlists = self.get_playlist_coll().find(
            {},
            projection={"tracks.uri": 1, "_id": 0},
            sort=[("created_at", -1)],
            limit=limit,
        )
        excluded_uris = []
        for playlist in recent_playlists:
            # Extract URIs from nested tracks list
            excluded_uris.extend([t.get("uri") for t in playlist.get("tracks", []) if t.get("uri")])
        self.logger.info("Found %d tracks to exclude from recent playlists", len(excluded_uris))
        return excluded_uris

    def generate_random_tracks(self, no_items: int) -> None:
        self.logger.debug(
            "Building random track pipeline: no_items=%d out_collection=%s",
            no_items,
            self.playlist_coll_name,
        )
        self.logger.info("Generating a playlist with %d items and by random tracks", no_items)

        excluded_uris = self.get_recent_playlist_uris()

        pipeline: Sequence[Mapping[str, Any]] = [
            {"$match": {"uri": {"$nin": excluded_uris}}},
            {"$sample": {"size": no_items}},
            {
                "$group": {
                    "_id": ObjectId(),
                    "tracks": {"$push": "$$ROOT"},
                    "created_at": {"$first": datetime.now(timezone.utc)},
                }
            },
            {
                "$merge": {
                    "into": self.playlist_coll_name,
                    "whenMatched": "keepExisting",
                    "whenNotMatched": "insert",
                }
            },
        ]

        cursor = self.get_tracks_coll().aggregate(pipeline)
        cursor.close()

    def generate_random_artists(self, no_items: int) -> None:
        self.logger.debug("Selecting random artists to build playlist: no_items=%d", no_items)
        self.logger.info("Generating a playlist with %d items and by random artists", no_items)
        all_artists = self.get_artist_ids()
        some_artists = self._randomize(all_artists)
        self.logger.debug(
            "Artist sampling: total_artists=%d selected=%d", len(all_artists), len(some_artists)
        )
        pipeline: Sequence[Mapping[str, Any]] = [
            {"$match": {"artists._id": {"$in": some_artists}}},
            {"$sample": {"size": no_items}},
            {
                "$group": {
                    "_id": ObjectId(),
                    "tracks": {"$push": "$$ROOT"},
                    "created_at": {"$first": datetime.now(timezone.utc)},
                }
            },
            {
                "$merge": {
                    "into": self.playlist_coll_name,
                    "whenMatched": "keepExisting",
                    "whenNotMatched": "insert",
                }
            },
        ]

        cursor = self.get_tracks_coll().aggregate(pipeline)
        cursor.close()

    def generate_random_playlist(self, item_type: RandomnessType, no_items: int) -> None:
        self.logger.debug(
            "Dispatching generate_random_playlist: type=%s no_items=%d", item_type, no_items
        )
        self.validate_item_count(no_items)
        if item_type == "track":
            self.generate_random_tracks(no_items)
        elif item_type == "artist":
            self.generate_random_artists(no_items)
        else:
            raise ValueError("Invalid item type")

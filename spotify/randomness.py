import logging
import random
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from spotify.db import DB
from spotify.types import RandomnessType


class Randomness:
    def __init__(self, my_mongo: DB) -> None:
        self.logger = logging.getLogger(__name__)
        self.db = my_mongo
        self.tracks_coll = my_mongo.get_tracks_coll()
        self.playlist_coll = my_mongo.get_playlist_coll()
        self.artist_sampling_ratio = 0.25
        self.logger.debug(
            "Initialized Randomness: percentage=%.2f tracks=%s playlist=%s out_collection=%s",
            self.artist_sampling_ratio,
            self.tracks_coll.name,
            self.playlist_coll.name,
            self.db.playlist_coll_name,
        )

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

    def get_artist_ids(self) -> list[str]:
        self.logger.debug("Aggregating distinct artist IDs from tracks collection")
        pipeline: Sequence[Mapping[str, Any]] = [
            {"$unwind": "$artists"},
            {"$group": {"_id": "$artists._id"}},
            {"$project": {"_id": 1}},
        ]
        cursor = self.tracks_coll.aggregate(pipeline)
        result = [doc["_id"] for doc in cursor]
        cursor.close()
        self.logger.debug("Found %d distinct artist IDs", len(result))
        return result

    def get_random_tracks(self, no_items: int) -> None:
        self.logger.debug(
            "Building random track pipeline: no_items=%d out_collection=%s",
            no_items,
            self.db.playlist_coll_name,
        )
        self.logger.info("Generating a playlist with %d items and by random tracks", no_items)
        pipeline: Sequence[Mapping[str, Any]] = [
            {"$sample": {"size": no_items}},
            {
                "$group": {
                    "_id": ObjectId(),
                    "tracks": {"$push": "$$ROOT"},
                    "created_at": {"$first": datetime.now(timezone.utc)},
                }
            },
            {"$out": self.db.playlist_coll_name},
        ]

        cursor = self.tracks_coll.aggregate(pipeline)
        cursor.close()

    def get_random_artists(self, no_items: int) -> None:
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
            {"$out": self.db.playlist_coll_name},
        ]

        cursor = self.tracks_coll.aggregate(pipeline)
        cursor.close()

    def validate_item_count(self, no_items: int) -> None:
        self.logger.debug("Validating requested item count: no_items=%s", no_items)
        if not isinstance(no_items, int):
            raise ValueError("Number of items must be an integer")
        if no_items < 1:
            raise ValueError("Number of items must be greater than 0")
        # Use DB-level count_documents to align with test mocks.
        max_no_item = self.db.count_track({})
        self.logger.debug("Max items available according to DB: %s", max_no_item)

        if max_no_item and no_items > max_no_item:
            raise ValueError(f"Number of items must be less than {max_no_item}")

    def generate_random_playlist(self, item_type: RandomnessType, no_items: int) -> None:
        self.logger.debug(
            "Dispatching generate_random_playlist: type=%s no_items=%d", item_type, no_items
        )
        self.validate_item_count(no_items)
        if item_type == "track":
            self.get_random_tracks(no_items)
        elif item_type == "artist":
            self.get_random_artists(no_items)
        else:
            raise ValueError("Invalid item type")

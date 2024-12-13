import random
from datetime import datetime, timezone
from os import environ
from typing import Any, Literal

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

from src.logger import Logger


randomness_types = Literal["track", "artist"]


class Randomness:
    def __init__(self) -> None:
        load_dotenv()
        self.logger = Logger().get_logger()
        mongo_user = environ["MONGO_INITDB_ROOT_USERNAME"]
        mongo_password = environ["MONGO_INITDB_ROOT_PASSWORD"]
        mongo_db_name = environ["MONGO_INITDB_DATABASE"]
        mongo_collection_name = environ["MONGO_COLLECTION_NAME"]
        mongo_uri = f"mongodb://{mongo_user}:{mongo_password}@localhost:27017"
        self.mongo_client: MongoClient[dict[str, Any]] = MongoClient(mongo_uri)
        self.mongo_db = self.mongo_client[mongo_db_name]
        self.mongo_tracks_collection = self.mongo_db[mongo_collection_name]
        self.mongo_playlist_collection = self.mongo_db["playlist"]
        self.randomness_percentage = 0.25

    def _randomize(self, whole_sample: list[str]) -> list[str]:
        if not isinstance(whole_sample, list):
            raise ValueError("'whole_sample' must be a list")
        if not whole_sample:
            raise ValueError("'whole_sample' must not be empty")
        max_no_item = len(whole_sample)
        no_of_item = int(max_no_item * self.randomness_percentage)
        return random.sample(whole_sample, no_of_item)

    def get_artist_ids(self) -> list[str]:
        pipeline: list[dict[str, Any]] = [
            {"$unwind": "$artists"},
            {"$group": {"_id": "$artists._id"}},
            {"$project": {"_id": 1}},
        ]
        cursor = self.mongo_tracks_collection.aggregate(pipeline)
        result = [doc["_id"] for doc in cursor]
        cursor.close()
        return result

    def run_query(self, pipeline: list[dict[str, Any]]) -> None:
        cursor = self.mongo_tracks_collection.aggregate(pipeline)
        cursor.close()

    def get_random_track(self, no_items: int) -> None:
        self.logger.info(f"Generating a playlist with {no_items} items and by random tracks")
        pipeline: list[dict[str, Any]] = [
            {"$sample": {"size": no_items}},
            {
                "$group": {
                    "_id": ObjectId(),
                    "tracks": {"$push": "$$ROOT"},
                    "created_at": {"$first": datetime.now(timezone.utc)},
                }
            },
            {"$out": self.mongo_playlist_collection.name},
        ]

        self.run_query(pipeline)

    def get_random_artist(self, no_items: int) -> None:
        self.logger.info(f"Generating a playlist with {no_items} items and by random artists")
        all_artists = self.get_artist_ids()
        some_artists = self._randomize(all_artists)
        pipeline: list[dict[str, Any]] = [
            {"$match": {"artists._id": {"$in": some_artists}}},
            {"$sample": {"size": no_items}},
            {
                "$group": {
                    "_id": ObjectId(),
                    "tracks": {"$push": "$$ROOT"},
                    "created_at": {"$first": datetime.now(timezone.utc)},
                }
            },
            {"$out": self.mongo_playlist_collection.name},
        ]

        self.run_query(pipeline)

    def check_no_items(self, no_items: int) -> None:
        if not isinstance(no_items, int):
            raise ValueError("Number of items must be an integer")
        if no_items < 1:
            raise ValueError("Number of items must be greater than 0")
        max_no_item = self.mongo_tracks_collection.count_documents({})
        max_no_item = int(max_no_item * 0.05)
        if no_items > max_no_item:
            raise ValueError(f"Number of items must be less than {max_no_item}")

    def get_random_item(self, item_type: randomness_types, no_items: int) -> None:
        self.check_no_items(no_items)
        if item_type == "track":
            self.get_random_track(no_items)
        elif item_type == "artist":
            self.get_random_artist(no_items)
        else:
            raise ValueError("Invalid item type")

from os import environ
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection


COLL_TYPE = dict[str, Any]


class DB:
    def __init__(self) -> None:
        mongo_user = environ["MONGO_INITDB_ROOT_USERNAME"]
        mongo_password = environ["MONGO_INITDB_ROOT_PASSWORD"]
        mongo_db_name = environ["MONGO_INITDB_DATABASE"]
        mongo_uri = f"mongodb://{mongo_user}:{mongo_password}@localhost:27017"
        self.mongo_client: MongoClient[COLL_TYPE] = MongoClient(mongo_uri)
        self.mongo_db = self.mongo_client[mongo_db_name]

    def check_connection(self) -> bool:
        is_up = True
        try:
            info = self.mongo_client.server_info()
            print(f"MongoDB version: {info["version"]}")
            print(f"MongoDB connection status: {self.mongo_client.is_primary}")
        except Exception:
            print("MongoDB is not available")
            is_up = False
        return is_up

    def get_tracks_collection(self) -> Collection[COLL_TYPE]:
        return self.mongo_db["tracks"]

    def get_playlist_collection(self) -> Collection[COLL_TYPE]:
        return self.mongo_db["playlist"]

    def close(self) -> None:
        self.mongo_client.close()

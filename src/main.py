#! /usr/bin/env python
import sys

from dotenv import load_dotenv

from src.auth import SpotifyAuth
from src.client import SpotifyClient
from src.db_client import DBClient
from src.randomness import Randomness


def main() -> None:
    load_dotenv()
    my_mongo = DBClient()
    if my_mongo.check_connection():
        raise ConnectionError("MongoDB is not available")
    sp_auth = SpotifyAuth()
    sp_client = SpotifyClient(sp_auth, my_mongo)
    randomness = Randomness(my_mongo)
    # sp_client.get_all_liked_tracks()
    randomness.get_random_item("track", 300)
    # print(randomness.get_random_item("artist", 5))
    sp_client.delete_playlist_content()
    sp_client.generate_content()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
    else:
        sys.exit(0)

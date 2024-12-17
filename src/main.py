#! /usr/bin/env python
import sys

from src.spotify import DB, Auth, Client, Randomness


def main() -> None:
    my_mongo = DB()
    if not my_mongo.check_connection():
        raise ConnectionError("MongoDB is not available")
    sp_auth = Auth()
    sp_client = Client(sp_auth, my_mongo)
    randomness = Randomness(my_mongo)
    # sp_client.get_all_liked_tracks()
    randomness.get_random_item("track", 350)
    # print(randomness.get_random_item("artist", 5))
    sp_client.delete_playlist_content()
    sp_client.generate_content()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        print(e)
        sys.exit(1)
    else:
        sys.exit(0)

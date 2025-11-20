#! /usr/bin/env python
import sys
import logging
import argparse

from dotenv import load_dotenv

from spotify import DB, Auth, Client, Randomness


def run(args: argparse.Namespace, logger: logging.Logger) -> None:
    my_mongo = DB()
    if not my_mongo.check_connection():
        raise ConnectionError("MongoDB is not available")

    sp_auth = Auth()
    sp_client = Client(sp_auth, my_mongo)
    randomness = Randomness(my_mongo)

    if args.update_cache or my_mongo.count_track({}) == 0:
        logger.info("Updating local cache of liked tracks from Spotify API...")
        sp_client.get_all_liked_tracks()
    else:
        logger.info("Skipping cache update; using existing liked tracks from DB")

    if args.export:
        my_mongo.export_to_json()
        my_mongo.close()
        return

    sp_client.delete_all_playlist_tracks()
    randomness.generate_random_playlist("track", 100)
    sp_client.populate_playlist_from_db()
    my_mongo.close()


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("urllib3").setLevel(logging.INFO)
    logging.getLogger("pymongo").setLevel(logging.INFO)
    logger = logging.getLogger("main")
    parser = argparse.ArgumentParser(description="Refresh Spotify playlist with randomness.")
    parser.add_argument(
        "--update-cache",
        action="store_true",
        default=False,
        help="Refresh liked tracks from Spotify before generating the playlist (defaults to False)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        default=False,
        help="Export liked tracks to a JSON file and exit",
    )
    args = parser.parse_args()
    try:
        run(args, logger)
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        logger.error("An error occurred: %s", e)
        sys.exit(1)
    else:
        logger.info("Completed successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()

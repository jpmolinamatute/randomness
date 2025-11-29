#! /usr/bin/env python
import sys
import logging
import argparse
import asyncio

from dotenv import load_dotenv

from spotify import DB, Auth, Client


async def run(args: argparse.Namespace, logger: logging.Logger) -> None:
    my_mongo = DB()
    if not my_mongo.check_connection():
        raise ConnectionError("MongoDB is not available")

    sp_auth = Auth()
    sp_client = Client(sp_auth, my_mongo)

    if args.get_all_playlists:
        await sp_client.get_all_playlists()
        return

    if args.update_cache:
        logger.info("Updating local cache of liked tracks")
        my_mongo.reset_collection(my_mongo.tracks_coll_name)
        await sp_client.get_all_liked_tracks()
    elif my_mongo.count_track({}) == 0:
        logger.info("Populating local cache of liked tracks")
        await sp_client.get_all_liked_tracks()
    else:
        logger.info("Skipping cache update; using existing liked tracks from DB")

    if args.export:
        my_mongo.export_to_json()
        my_mongo.close()
        return

    await sp_client.delete_all_playlist_tracks()
    my_mongo.generate_random_playlist("track", 100)
    await sp_client.populate_playlist_from_db()
    await sp_client.update_queue()
    my_mongo.close()


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("urllib3").setLevel(logging.INFO)
    logging.getLogger("pymongo").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.INFO)
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
    parser.add_argument(
        "--get-all-playlists",
        action="store_true",
        default=False,
        help="Get all playlists from Spotify",
    )
    args = parser.parse_args()
    try:
        asyncio.run(run(args, logger))
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

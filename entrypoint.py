#! /usr/bin/env python

from os import path
import sys
import logging
import requests
from dotenv import load_dotenv
from handlers.db_handler import DB_Handler
from handlers.spotify_handler import Spotify_Handler


def sync_playlist(db: DB_Handler, spotify: Spotify_Handler):
    playlist_obj = db.get_active_tracks()
    track_list = []
    playlist_id = None
    if playlist_obj["empty"]:
        playlist_id = spotify.get_playlist()
        if playlist_id:
            track_list = spotify.get_tracks(True)
            db.insert_data(playlist_id, track_list)
    else:
        playlist_id = playlist_obj["playlist_id"]
        track_list = playlist_obj["uri_list"]
        try:
            spotify.set_playlist_id(playlist_id)
        except ValueError:
            playlist_id = ""
            track_list = []
        except requests.HTTPError as e:
            logging.exception("Synchronizing playlist failed")
            logging.error(e)
            sys.exit(2)

    if not playlist_id:
        playlist_id = spotify.create_playlist()

    return playlist_id, track_list


def save_data(
    db: DB_Handler, spotify: Spotify_Handler, sample_list: list, playlist_id: str
) -> bool:
    spotify.save_tracks_to_playlist(sample_list)
    db.insert_data(playlist_id, sample_list)


def main():
    try:
        logging.basicConfig(level=logging.INFO)
        logging.info("Application just started")
        file_path = path.realpath(__file__)
        file_path = path.dirname(file_path)
        db = DB_Handler(file_path)
        spotify = Spotify_Handler()
        playlist_id, old_track_list = sync_playlist(db, spotify)
        track_list = spotify.get_tracks()
        sample_list = spotify.get_random_track(track_list)
        save_data(db, spotify, sample_list, playlist_id)
        if old_track_list:
            spotify.del_tracks_from_playlist(old_track_list)
    except Exception:
        logging.exception("Errors")
        sys.exit(2)
    else:
        logging.info("Application just finished")
        sys.exit(0)


if __name__ == "__main__":
    load_dotenv()
    main()

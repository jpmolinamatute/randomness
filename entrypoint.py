#! /usr/bin/env python
from os import environ
import sys
import math
import random
import logging
import json
from typing import Dict, List, Text
import requests
from dotenv import load_dotenv

PLAYLIST_SIZE = 100
PLAYLIST_NAME = "A Random randomness"
BASE_URL = "https://api.spotify.com"
PLAYLIST_URL = f"{BASE_URL}/v1/me/playlists"
Track_List = List[Text]
Break_Track_list = List[Track_List]


def get_session():
    if "SPOTIFY_OAUTH_TOKEN" not in environ:
        raise ValueError("environment variable 'SPOTIFY_OAUTH_TOKEN' is undefined")
    session = requests.Session()
    session.headers.update(
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {environ['SPOTIFY_OAUTH_TOKEN']}",
        }
    )
    return session


def check_token(session) -> None:
    headers = {"Accept": "application/json"}
    logging.info("Checking if 'SPOTIFY_OAUTH_TOKEN' is still alive")
    response = session.get(PLAYLIST_URL, headers=headers)
    response.raise_for_status()


def save_tracks(session, playlist_id: str, track_list: Track_List) -> None:
    headers = {"Accept": "application/json"}
    data = {"uris": track_list}
    tracks_url = f"{BASE_URL}/v1/playlists/{playlist_id}/tracks"
    response = session.post(tracks_url, headers=headers, data=json.dumps(data))
    response.raise_for_status()


def break_list(track_list: Track_List, size: int = 0) -> Break_Track_list:
    broken_track_list = []
    if size:
        playlist_size = size
    else:
        playlist_size = PLAYLIST_SIZE

    if len(track_list) <= playlist_size:
        broken_track_list.append(track_list)
    else:
        length = len(track_list)
        turns = math.ceil(length / playlist_size)
        for item in range(turns):
            start = item * playlist_size
            end = (item + 1) * playlist_size
            end = end if end <= len(track_list) else len(track_list)
            broken_track_list.append(track_list[start:end])
    return broken_track_list


def del_tracks(session, playlist_id: str, track_list: Track_List) -> None:
    data: Dict[Text, List[Dict]] = {"tracks": []}
    for track in track_list:
        data["tracks"].append({"uri": track})
    tracks_url = f"{BASE_URL}/v1/playlists/{playlist_id}/tracks"
    response = session.delete(tracks_url, data=json.dumps(data))
    response.raise_for_status()


def playlist_exists(session, playlist_id: str) -> bool:
    exists = False
    url = f"{BASE_URL}/v1/playlists/{playlist_id}"
    headers = {"Accept": "application/json"}
    logging.info(f"Checking if playlist '{playlist_id}' exists")
    response = session.get(url, headers=headers)
    response.raise_for_status()
    if response.status_code == 200:
        exists = True
    return exists


def get_playlist(session) -> str:
    next_url = f"{PLAYLIST_URL}?limit=50"
    playlist_id = ""
    headers = {"Accept": "application/json"}
    while next_url and not playlist_id:
        logging.info("Getting user's playlist list")
        response = session.get(next_url, headers=headers)
        response.raise_for_status()
        if response.status_code == 200:
            response_dict = response.json()
            next_url = response_dict["next"]
            for item in response_dict["items"]:
                if item["name"] == PLAYLIST_NAME:
                    playlist_id = item["id"]
        else:
            next_url = ""
    return playlist_id


def create_playlist(session) -> str:
    data = {
        "name": PLAYLIST_NAME,
        "public": False,
        "description": "This play list was created by a bot",
    }
    playlist_id = ""
    logging.info("Creating new playlist")
    response = session.post(PLAYLIST_URL, data=json.dumps(data))
    response.raise_for_status()
    if response.status_code == 200 or response.status_code == 201:
        response_dict = response.json()
        playlist_id = response_dict["id"]
    return playlist_id


def del_tracks_from_playlist(session, playlist_id: str, track_list: Track_List) -> None:
    if isinstance(track_list, list) and track_list:
        logging.info(f"Deleting {len(track_list)} tracks from playlist '{playlist_id}'")
        broken_list = break_list(track_list)
        for item in broken_list:
            del_tracks(session, playlist_id, item)


def save_tracks_to_playlist(session, playlist_id: str, track_list: Track_List) -> None:
    if isinstance(track_list, list) and track_list:
        logging.info(f"Saving {len(track_list)} tracks to playlist '{playlist_id}'")
        broken_list = break_list(track_list)
        for item in broken_list:
            save_tracks(session, playlist_id, item)


def get_random_track(track_list: Track_List) -> Track_List:
    random_list = []
    if isinstance(track_list, list) and track_list:
        size = PLAYLIST_SIZE * 2
        logging.info(f"{size} tracks were randomly generated")
        random_list = random.sample(track_list, k=size)
    else:
        raise TypeError("get_random_track() was called with the wrong value")
    return random_list


def get_tracks(session, playlist_id: str = "") -> Track_List:
    track_list = []
    headers = {"Accept": "application/json"}
    if playlist_id:
        tracks_url = f"{BASE_URL}/v1/playlists/{playlist_id}/tracks"
        next_url = f"{tracks_url}?fields=next,items(track.uri)&limit=100"
        logging.info(f"Getting tracks from playlist '{playlist_id}'")
    else:
        next_url = f"{BASE_URL}/v1/me/tracks?limit=50"
        logging.info("Getting new load of tracks from Spotify Library...")
    total = 0
    while next_url:
        response = session.get(next_url, headers=headers)
        response.raise_for_status()
        if response.status_code == 200:
            response_dict = response.json()
            next_url = response_dict["next"]
            for item in response_dict["items"]:
                total += 1
                track_list.append(item["track"]["uri"])
        else:
            next_url = ""
    logging.info(f"tracks count is {total}")
    return track_list


def main() -> None:
    try:
        logging.basicConfig(level=logging.INFO)
        logging.info("I just started")
        session = get_session()
        check_token(session)
        playlist_id = get_playlist(session)
        if not playlist_id:
            playlist_id = create_playlist(session)
        old_track_list = get_tracks(session, playlist_id)
        all_track_list = get_tracks(session)
        new_track_list = get_random_track(all_track_list)
        save_tracks_to_playlist(session, playlist_id, new_track_list)
        del_tracks_from_playlist(session, playlist_id, old_track_list)
    except Exception:
        logging.exception("I failed :-(")
        sys.exit(2)
    else:
        logging.info("Bye! :-)")
        sys.exit(0)


if __name__ == "__main__":
    load_dotenv()
    main()

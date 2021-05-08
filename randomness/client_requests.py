#! /usr/bin/env python

import math
import time
import logging
import json
from typing import Dict, Text, List
import requests
from .config import load_config
from .common import (
    Track_List,
    str_to_base64,
    Break_Track_list,
    BASE_URL,
    TOKEN_URL,
    PLAYLIST_URL,
    SpotifyToken,
)
from .client_aouth import OAuth
from .db_library import Library


def renew_access_token(refresh: str, settings: dict) -> SpotifyToken:
    logging.info("Getting new access_token")
    client_id = settings["credentials"]["spotipy_client_id"]
    client_secret = settings["credentials"]["spotipy_client_secret"]
    cred = f"{client_id}:{client_secret}"
    cred_encoded = str_to_base64(cred)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {cred_encoded}",
    }
    data = {"grant_type": "refresh_token", "refresh_token": refresh}
    try:
        response = requests.post(TOKEN_URL, data=data, headers=headers)
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        logging.error(response.reason)
        raise
    else:
        respose_dict = response.json()
        if (
            "access_token" not in respose_dict
            or "refresh_token" not in respose_dict
            or "expires_in" not in respose_dict
        ):
            msg = "Error: we couldn't get one or more of "
            msg += "[access_token, refresh_token, expires_in] "
            msg += "from call to spotify"
            raise Exception(msg)
    return respose_dict


def get_session(filepath: str):
    session = requests.Session()
    settings = load_config(filepath)
    uid = settings["user"]["id"]
    db = OAuth(filepath, uid)
    expire = db.get_field("expires_in")
    now = time.time()
    if expire - 300 <= now:
        refresh = db.get_field("refresh_token")
        new_token = renew_access_token(refresh, settings)
        db.save_access_token(new_token)
    access_token = db.get_field("access_token")
    session.headers.update(
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
    )
    db.close()
    return session


def save_tracks(session, playlist_id: str, track_list: Track_List) -> None:
    headers = {"Accept": "application/json"}
    data = {"position": 0, "uris": track_list}
    tracks_url = f"{BASE_URL}/v1/playlists/{playlist_id}/tracks"
    try:
        response = session.post(tracks_url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        logging.error(response.reason)
        raise


def break_list(track_list: Track_List, playlist_size: int) -> Break_Track_list:
    broken_track_list = []

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
    try:
        response = session.delete(tracks_url, data=json.dumps(data))
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        logging.error(response.reason)
        raise


def get_playlist(session, playlist_name: str) -> str:
    next_url = f"{PLAYLIST_URL}?limit=50"
    playlist_id = ""
    headers = {"Accept": "application/json"}
    while next_url and not playlist_id:
        logging.info("Getting user's playlist list")
        try:
            response = session.get(next_url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            logging.error(response.reason)
            raise
        else:
            if response.status_code == 200:
                response_dict = response.json()
                next_url = response_dict["next"]
                for item in response_dict["items"]:
                    if item["name"] == playlist_name:
                        playlist_id = item["id"]
            else:
                next_url = ""
    return playlist_id


def create_playlist(session, playlist_name: str) -> str:
    data = {
        "name": playlist_name,
        "public": False,
        "description": "This playlist was created by a bot BUT coded by human",
    }
    playlist_id = ""
    logging.info("Creating new playlist")
    try:
        response = session.post(PLAYLIST_URL, data=json.dumps(data))
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        logging.error(response.reason)
        raise
    else:
        if response.status_code == 200 or response.status_code == 201:
            response_dict = response.json()
            playlist_id = response_dict["id"]
    return playlist_id


def del_tracks_from_playlist(session, playlist_id: str, track_list: Track_List) -> None:
    if isinstance(track_list, list) and track_list:
        logging.info(f"Deleting {len(track_list)} tracks from playlist '{playlist_id}'")
        broken_list = break_list(track_list, 100)
        for item in broken_list:
            del_tracks(session, playlist_id, item)


def save_tracks_to_playlist(session, playlist_id: str, track_list: Track_List) -> None:
    if isinstance(track_list, list) and track_list:
        logging.info(f"Saving {len(track_list)} tracks to playlist '{playlist_id}'")
        broken_list = break_list(track_list, 100)
        for item in broken_list:
            save_tracks(session, playlist_id, item)


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
        try:
            response = session.get(next_url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            logging.error(response.reason)
            raise
        else:
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


def get_library(session) -> list:
    headers = {"Accept": "application/json"}
    next_url = f"{BASE_URL}/v1/me/tracks?limit=50"
    logging.info("Getting library from Spotify Library...")
    total = 0
    track_list = []
    while next_url:
        try:
            response = session.get(next_url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            logging.error(response.reason)
            raise
        else:
            if response.status_code == 200:
                response_dict = response.json()
                next_url = response_dict["next"]
                for item in response_dict["items"]:
                    total += 1
                    track_list.append(
                        (
                            item["track"]["uri"],
                            item["track"]["name"].lower(),
                            item["added_at"],
                            int(item["track"]["duration_ms"]),
                            item["track"]["album"]["uri"],
                            item["track"]["album"]["name"].lower(),
                            item["track"]["artists"][0]["uri"],
                            item["track"]["artists"][0]["name"].lower(),
                        )
                    )
            else:
                next_url = ""
    logging.info(f"tracks count is {total}")
    return track_list


def reset_library(lib, session) -> None:
    lib.reset_table()
    whole_library = get_library(session)
    columns = (
        "uri",
        "name",
        "added_at",
        "duration_ms",
        "album_uri",
        "album_name",
        "artists_uri",
        "artists_name",
    )
    lib.insert_many(whole_library, columns)


def generate_playlist(filepath: str) -> None:
    logging.info("Analysis is starting")
    lib = Library(filepath)
    session = get_session(filepath)
    reset_library(lib, session)
    config = load_config(filepath)
    playlist_name = config["playlist"]["name"]
    playlist_size = config["playlist"]["size"]
    playlist_id = get_playlist(session, playlist_name)
    if not playlist_id:
        playlist_id = create_playlist(session, playlist_name)
    old_track_list = get_tracks(session, playlist_id)
    new_track_list = lib.get_sample(playlist_size)
    save_tracks_to_playlist(session, playlist_id, new_track_list)
    del_tracks_from_playlist(session, playlist_id, old_track_list)

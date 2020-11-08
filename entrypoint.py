#! /usr/bin/env python
import random
import datetime
import json
from os import environ
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

SPOTIFY_URL = "https://api.spotify.com"


def get_mongodb_db():
    user = environ["MONGO_USER"]
    password = environ["MONGO_PASS"]
    db = environ["MONGO_DB"]
    myclient = MongoClient(f"mongodb://{user}:{password}@home-in.com:57017/{db}")
    return myclient[db]


def del_tracks_from_playlist(session: requests.Session, playlist_id: str, track_list: list):
    url = f"{SPOTIFY_URL}/v1/playlists/{playlist_id}/tracks"
    data = {"tracks": track_list}
    response = session.delete(url, data=json.dumps(data))
    if response.status_code != 200:
        raise Exception(response.reason)


def get_tracks_from_db() -> list:
    mydb = get_mongodb_db()
    col = mydb["backup"]
    trackslist = col.find_one({"active": True}, {"_id": False, "list": True})
    return trackslist["list"]


def save_playlist_to_db(playlist_id: str):
    mydb = get_mongodb_db()
    col = mydb["playlist"]
    obj = col.insert_one({"_id": playlist_id})
    print(obj.inserted_id)


def create_playlist(session: requests.Session) -> str:
    url = f"{SPOTIFY_URL}/v1/me/playlists"
    data = {
        "name": "A Random randomness",
        "public": False,
        "description": "This play list was created by a bot",
    }
    playlist_id = None
    response = session.post(url, data=json.dumps(data))
    if response.status_code == 200 or response.status_code == 201:
        response_dict = response.json()
        playlist_id = response_dict["id"]
    else:
        raise Exception(response.reason)
    return playlist_id


def check_playlist_exist() -> str:
    mydb = get_mongodb_db()
    col = mydb["playlist"]
    result = col.find_one()
    result = result["_id"] if result else ""
    return result


def add_tracks_to_playlist(session: requests.Session, playlist_id: str, track_list: list):
    url = f"{SPOTIFY_URL}/v1/playlists/{playlist_id}/tracks"
    headers = {"Accept": "application/json"}
    formatter = lambda element: element["uri"]
    data = {"uris": list(map(formatter, track_list))}
    response = session.post(url, headers=headers, data=json.dumps(data))
    if response.status_code != 201:
        raise Exception(response.reason)


def save_tracks_to_db(track_list: list):
    mydb = get_mongodb_db()
    col = mydb["backup"]
    obj = col.insert_one({"date": datetime.datetime.utcnow(), "list": track_list, "active": True})
    print(obj.inserted_id)


def get_random_track(track_list: list) -> list:
    return random.sample(track_list, k=100)


def get_tracks_from_api(session: requests.Session) -> list:
    track_list = []
    next_url = f"{SPOTIFY_URL}/v1/me/tracks?limit=50"
    headers = {"Accept": "application/json"}
    while next_url:
        response = session.get(next_url, headers=headers)
        if response.status_code == 200:
            response_dict = response.json()
            next_url = response_dict["next"]
            for item in response_dict["items"]:
                track_list.append({"uri": item["track"]["uri"]})
        else:
            next_url = False
    return track_list


def get_spotify_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {environ['SPOTIFY_TOKEN']}",
        }
    )
    return session


def main():
    session = get_spotify_session()
    print("1")
    playlist_id = check_playlist_exist()
    if playlist_id:
        print("2a")
        track_list = get_tracks_from_db()
        del_tracks_from_playlist(session, playlist_id, track_list)
    else:
        print("2b")
        playlist_id = create_playlist(session)
        save_playlist_to_db(playlist_id)
    print("3")
    track_list = get_tracks_from_api(session)
    print("4")
    random_track_list = get_random_track(track_list)
    print("5")
    save_tracks_to_db(random_track_list)
    print("6")
    add_tracks_to_playlist(session, playlist_id, random_track_list)
    print("7")


if __name__ == "__main__":
    load_dotenv()
    main()

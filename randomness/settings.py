import json
from os import path
from .common import isWritable, PLAYLIST_NAME, PLAYLIST_SIZE, DEFAULT_SETTINGS


def create_settings(filepath: str) -> None:
    if isWritable(filepath):
        complete_path = path.join(filepath, DEFAULT_SETTINGS)
        data = {
            "playlist": {"name": PLAYLIST_NAME, "size": PLAYLIST_SIZE * 2},
            "user": {"id": False, "username": False},
            "server": {"port": 5842, "hostname": "localhost"},
            "credentials": {
                "spotipy_client_id": "CHANGE ME!",
                "spotipy_client_secret": "CHANGE ME!",
            },
            "security": {"secret": "CHANGE ME!"},
        }

        with open(complete_path, "w") as f:
            json.dump(data, fp=f, indent=4, skipkeys=True)
    else:
        msg = f"Settings path '{filepath}' is not writable "
        msg += "or doesn't exists. "
        msg += "Please change it and try again"
        raise Exception(msg)


def validate_settings(filepath: str) -> bool:
    # try:
    valid = True
    complete_path = path.join(filepath, DEFAULT_SETTINGS)
    try:
        with open(complete_path, "r") as f:
            data = json.load(fp=f)
    except json.decoder.JSONDecodeError:
        valid = False
    else:
        if "credentials" in data:
            if "spotipy_client_id" in data["credentials"]:
                if (
                    not isinstance(data["credentials"]["spotipy_client_id"], str)
                    or not data["credentials"]["spotipy_client_id"]
                ):
                    valid = False
            else:
                valid = False
            if "spotipy_client_secret" in data["credentials"]:
                pass
            else:
                valid = False
        else:
            valid = False

    return valid


def load_settings(filepath: str) -> dict:
    complete_path = path.join(filepath, DEFAULT_SETTINGS)
    with open(complete_path, "r") as f:
        data = json.load(fp=f)
    return data

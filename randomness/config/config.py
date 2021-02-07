from os import path
import yaml
from jsonschema import validate, ValidationError
from .schema import (
    CONFIG_SCHEMA,
    DEFAULT_CONFIG_NAME,
    PLAYLIST_NAME,
    PLAYLIST_SIZE,
    DEFAULT_DB,
    DEFAULT_WEB_PORT,
    DEFAULT_WEB_HOST,
    DEFAULT_CONFIG,
)
from ..common import isWritable


def create_config(filepath: str) -> None:
    if isWritable(filepath):
        complete_path = path.join(filepath, DEFAULT_CONFIG_NAME)
        data = {
            "playlist": {"name": PLAYLIST_NAME, "size": PLAYLIST_SIZE},
            "user": {"id": "CHANGE ME!", "username": ""},
            "server": {"port": DEFAULT_WEB_PORT, "hostname": DEFAULT_WEB_HOST},
            "credentials": {
                "spotipy_client_id": "CHANGE ME!",
                "spotipy_client_secret": "CHANGE ME!",
            },
            "security": {"secret": "CHANGE ME!"},
            "database": {"filename": DEFAULT_DB},
        }

        with open(complete_path, "w") as f:
            yaml.dump(data, f, sort_keys=True)
    else:
        msg = f"Settings path '{filepath}' is not writable "
        msg += "or doesn't exists. "
        msg += "Please change it and try again"
        raise Exception(msg)


def fill_default(default_values: dict, values: dict) -> dict:
    for d in default_values.keys():
        if d in values:
            if isinstance(default_values[d], dict):
                fill_default(default_values[d], values[d])
        else:
            values[d] = default_values[d]
    return values


def load_config(filepath: str) -> dict:
    complete_path = path.join(filepath, DEFAULT_CONFIG_NAME)
    if not path.isfile(complete_path):
        create_config(filepath)
        raise FileNotFoundError(f"File '{complete_path}' doesn't exist")
    with open(complete_path, "r") as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
    validate(instance=data, schema=CONFIG_SCHEMA)
    return fill_default(DEFAULT_CONFIG, data)

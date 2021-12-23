from os import path
from copy import deepcopy
import logging
import yaml
from jsonschema import validate
from .schema import (
    CONFIG_SCHEMA,
    DEFAULT_CONFIG_NAME,
    DEFAULT_CONFIG,
)
from ..common import isWritable


def create_config(filepath: str) -> None:
    complete_path = path.join(filepath, DEFAULT_CONFIG_NAME)
    if isWritable(filepath) and not path.isfile(complete_path):
        data = deepcopy(DEFAULT_CONFIG)
        data["user"] = {"id": "CHANGE ME!"}
        data["credentials"] = {
            "spotipy_client_id": "CHANGE ME!",
            "spotipy_client_secret": "CHANGE ME!",
        }

        with open(complete_path, "w") as f:
            yaml.dump(data, f, sort_keys=True)
        msg = f"{complete_path} file has been created. "
        msg += "Please change the values according to your needs"
        logging.info(msg)
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

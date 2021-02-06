from os import path
import yaml
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from .schema import CONFIG_SCHEMA

# from ..common import isWritable, PLAYLIST_NAME, PLAYLIST_SIZE

DEFAULT_CONFIG_NAME = "config.yaml"
# def create_settings(filepath: str) -> None:
#     if isWritable(filepath):
#         complete_path = path.join(filepath, DEFAULT_CONFIG_NAME)
#         data = {
#             "playlist": {"name": PLAYLIST_NAME, "size": PLAYLIST_SIZE * 2},
#             "user": {"id": False, "username": False},
#             "server": {"port": 5842, "hostname": "localhost"},
#             "credentials": {
#                 "spotipy_client_id": "CHANGE ME!",
#                 "spotipy_client_secret": "CHANGE ME!",
#             },
#             "security": {"secret": "CHANGE ME!"},
#         }

#         with open(complete_path, "w") as f:
#             json.dump(data, fp=f, indent=4, skipkeys=True)
#     else:
#         msg = f"Settings path '{filepath}' is not writable "
#         msg += "or doesn't exists. "
#         msg += "Please change it and try again"
#         raise Exception(msg)


def validate_data(data: dict) -> bool:
    try:
        validate(instance=data, schema=CONFIG_SCHEMA)
    except ValidationError as err:
        print(err)
        err = "Given JSON data is InValid"
        valid = False
    else:
        valid = True
    return valid


def load_config(filepath: str) -> dict:
    complete_path = path.join(filepath, DEFAULT_CONFIG_NAME)
    if not path.isfile(complete_path):
        raise FileNotFoundError(f"File '{complete_path}' doesn't exist")
    with open(complete_path, "r") as f:
        data = yaml.load(f, Loader=yaml.FullLoader)

    if not validate_data(data):
        raise Exception("Error: config file is invalid or is missing some parameters")
    return data

from os import environ, path
import sqlite3
import requests

BASE_URL = "https://api.spotify.com"


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


def get_connection():
    file_path = path.realpath(__file__)
    file_path = path.dirname(file_path)
    filename = path.join(file_path, "storage.db")
    return sqlite3.connect(filename, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)

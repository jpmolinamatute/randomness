from os import environ
import base64
from typing import TypedDict, Text
import requests
from randomness.oauth import OAuth


PORT_NUMBER = 5842
BASE_URL = "https://api.spotify.com"
TOKEN_URL = "https://accounts.spotify.com/api/token"
PLAYLIST_SIZE = 100
PLAYLIST_NAME = "A Random randomness"
PLAYLIST_URL = f"{BASE_URL}/v1/me/playlists"


class SpotifyToken(TypedDict):
    access_token: Text
    refresh_token: Text
    expires_in: int


def str_to_base64(line: str) -> str:
    byte_line = line.encode("utf-8")
    encoded_line = base64.b64encode(byte_line)
    return encoded_line.decode("utf-8")


def get_session():
    session = requests.Session()
    uri = environ["SPOTIPY_USER"]
    u = OAuth(uri)
    access_token = u.get_field("access_token")
    session.headers.update(
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
    )
    return session


def get_spotify_user() -> str:
    url = f"{BASE_URL}/v1/me"
    uri = ""
    session = get_session()
    response = session.get(url)
    response.raise_for_status()
    response_dict = response.json()
    if "uri" in response_dict:
        uri = response_dict["uri"]
    else:
        raise Exception("ERROR: ")
    return uri


def save_access_token(response: SpotifyToken) -> str:
    uri = get_spotify_user()
    db = OAuth(uri)
    db.save_access_token(
        response["access_token"], response["refresh_token"], response["expires_in"]
    )
    db.get_field("*")
    return uri


def get_access_token(code: str, verifier: str) -> SpotifyToken:
    callback_link = f"http://{environ['SERVER_NAME']}:{PORT_NUMBER}/callback"
    cred = f"{environ['SPOTIPY_CLIENT_ID']}:{environ['SPOTIPY_CLIENT_SECRET']}"
    cred_encoded = str_to_base64(cred)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {cred_encoded}",
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": callback_link,
        "code_verifier": verifier,
    }
    response = requests.post(TOKEN_URL, data=data, headers=headers)
    response.raise_for_status()
    if response.status_code != 200:
        raise Exception("We received a status code different than 200")
    return response.json()


def client_start(code: str, verifier: str) -> None:
    response = get_access_token(code, verifier)
    save_access_token(response)

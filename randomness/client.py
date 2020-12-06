from os import environ
import base64
import requests
from randomness.oauth import OAuth

PORT_NUMBER = 5842
BASE_URL = "https://api.spotify.com"


def str_to_base64(line: str) -> str:
    byte_line = line.encode("utf-8")
    encoded_line = base64.b64encode(byte_line)
    return encoded_line.decode("utf-8")


def get_session(access_token: str):
    session = requests.Session()
    session.headers.update(
        {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
    )
    return session


def get_spotify_user(session) -> str:
    url = f"{BASE_URL}/v1/me"
    response = session.get(url)
    response.raise_for_status()
    response_dict = response.json()
    return response_dict["uri"]


def get_access_token(code: str, verifier: str):
    url = "https://accounts.spotify.com/api/token"
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
    response = requests.post(url, data=data, headers=headers)
    response.raise_for_status()
    response_dict = response.json()
    if response.status_code == 200:
        db = OAuth()
        db.save_access_token(
            response_dict["access_token"],
            response_dict["refresh_token"],
            response_dict["expires_in"],
        )
        session = get_session(response_dict["access_token"])
        uri = get_spotify_user(session)
        db.save_uri(uri)
        db.get_all()
    else:
        raise Exception("We received a status code different than 200")

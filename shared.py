from os import environ
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

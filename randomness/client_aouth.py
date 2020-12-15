import requests
from .common import TOKEN_URL, SpotifyToken
from .db_oauth import OAuth


def save_access_token(response: SpotifyToken, filepath: str, uid: str):
    db = OAuth(filepath, uid)
    db.save_access_token(response)
    db.close()


def get_access_token(
    code: str, verifier: str, callback_link: str, cred_encoded: str
) -> SpotifyToken:
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

import base64
import threading
import time
import webbrowser
from os import getenv
from typing import TypedDict

import pkce
import requests

from src.spotify.helpers import CustomHTTPServer, RequestHandler
from src.spotify.logger import Logger
from src.spotify.token import Token, TokenError


class SpotifyError(TypedDict):
    status: int
    message: str


TIMEOUT = 15


class Auth:
    def __init__(self) -> None:
        self.logger = Logger().get_logger()
        self.client_id = getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = getenv("SPOTIFY_CLIENT_SECRET")
        self.server_address = ("localhost", 5000)
        self.redirect_uri = f"http://{self.server_address[0]}:{self.server_address[1]}/callback"
        self.token_url = "https://accounts.spotify.com/api/token"
        self.scope = "user-library-read playlist-modify-public playlist-modify-private"
        verifier, challenge = pkce.generate_pkce_pair()
        self.code_verifier = verifier
        self.code_challenge = challenge
        self.state = getenv("SPOTIFY_STATE")
        self.auth_event: threading.Event
        self.access_token = ""
        self.refresh_token = ""
        self.token_expires_at = 0.0
        self.initialize_token_data()

    def initialize_token_data(self) -> None:
        try:
            token_data = Token()
            token_data.load_tokens()
            self.access_token = token_data.access_token
            self.refresh_token = token_data.refresh_token
            self.token_expires_at = token_data.token_expires_at
            if self.is_token_expired():
                self.get_refresh_access_token()
        except TokenError:
            self.authenticate()

    def _encode_client_credentials(self) -> str:
        client_creds = f"{self.client_id}:{self.client_secret}"
        return base64.b64encode(client_creds.encode()).decode()

    def get_authorization_url(self) -> str:
        auth_url = (
            "https://accounts.spotify.com/authorize"
            "?response_type=code"
            "&code_challenge_method=S256"
            f"&client_id={self.client_id}"
            f"&scope={self.scope}"
            f"&redirect_uri={self.redirect_uri}"
            f"&state={self.state}"
            f"&code_challenge={self.code_challenge}"
        )
        return auth_url

    def get_access_token(self, authorization_code: str) -> Token:
        headers = {
            "Authorization": f"Basic {self._encode_client_credentials()}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "authorization_code",
            "state": self.state,
            "code": authorization_code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": self.code_verifier,
        }
        response = requests.post(self.token_url, headers=headers, data=data, timeout=TIMEOUT)
        response_data = response.json()
        if response.status_code != 200:
            raise Exception(f"Error obtaining access token: {response_data}")

        token = Token(
            access_token=response_data["access_token"],
            refresh_token=response_data.get("refresh_token", self.refresh_token),
            token_type=response_data["token_type"],
            token_expires_at=time.time() + response_data["expires_in"],
        )
        token.store_tokens()
        self.access_token = token.access_token
        self.refresh_token = token.refresh_token
        self.token_expires_at = token.token_expires_at
        return token

    def get_refresh_access_token(self) -> Token:
        self.logger.info("Refreshing access token")
        if not self.refresh_token:
            raise Exception("No refresh token available")

        headers = {
            "Authorization": f"Basic {self._encode_client_credentials()}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "refresh_token", "refresh_token": self.refresh_token}
        response = requests.post(self.token_url, headers=headers, data=data, timeout=TIMEOUT)
        response_data = response.json()
        if response.status_code == 200:
            token = Token(
                access_token=response_data["access_token"],
                refresh_token=response_data.get("refresh_token", self.refresh_token),
                token_type=response_data["token_type"],
                token_expires_at=time.time() + response_data["expires_in"],
            )
            token.store_tokens()
            self.access_token = token.access_token
            self.refresh_token = token.refresh_token
            self.token_expires_at = token.token_expires_at
        elif response_data.get("error") == "invalid_grant":
            self.logger.error("Refresh token revoked, re-authenticating...")
            self.authenticate()
        else:
            raise Exception(f"Error refreshing access token: {response_data}")
        return token

    def is_token_expired(self) -> bool:
        return time.time() >= self.token_expires_at

    def get_valid_access_token(self) -> str:
        self.logger.info("Getting valid access token")
        if self.is_token_expired():
            self.get_refresh_access_token()
        return self.access_token

    def callback(self, code: str) -> None:
        self.get_access_token(code)
        self.auth_event.set()

    def authenticate(self) -> None:
        self.auth_event = threading.Event()
        httpd = CustomHTTPServer(self.server_address, RequestHandler, self.callback)
        thread = threading.Thread(target=httpd.serve_forever)
        thread.daemon = True
        thread.start()
        self.logger.info("Please go to the browser to authorize the app.")
        self.logger.info("Listening for authorization callback...")
        webbrowser.open(self.get_authorization_url())
        self.auth_event.wait()

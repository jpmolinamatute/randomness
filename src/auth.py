import base64
import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from os import getenv
from pathlib import Path
from typing import Any, Callable, TypedDict
from urllib.parse import parse_qs, urlparse

import pkce
import requests
from dotenv import load_dotenv

from src.logger import Logger


_AfInetAddress = tuple[str, int]


class SpotifyError(TypedDict):
    status: int
    message: str


class TokenData(TypedDict):
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str | None


TIMEOUT = 15


class CustomHTTPServer(HTTPServer):
    def __init__(
        self,
        server_address: _AfInetAddress,
        request_class: type[BaseHTTPRequestHandler],
        callback: Callable[[str], Any],
    ) -> None:
        super().__init__(server_address, request_class)
        self.callback = callback


class RequestHandler(BaseHTTPRequestHandler):
    server: CustomHTTPServer

    def do_GET(self) -> None:
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/callback":
            query_params = parse_qs(parsed_path.query)
            code = query_params.get("code", [None])[0]
            state = query_params.get("state", [None])[0]
            if code and state == getenv("SPOTIFY_STATE"):
                self.send_response(200)
                self.end_headers()
                self.server.callback(code)
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"State mismatch error")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")


class SpotifyAuth:
    def __init__(self) -> None:
        load_dotenv()
        self.logger = Logger().get_logger()
        self.client_id = getenv("SPOTIFY_CLIENT_ID")
        self.client_secret = getenv("SPOTIFY_CLIENT_SECRET")
        self.server_address = ("localhost", 5000)
        self.redirect_uri = f"http://{self.server_address[0]}:{self.server_address[1]}/callback"
        self.token_url = "https://accounts.spotify.com/api/token"
        self.access_token: str = ""
        self.refresh_token: str = ""
        self.token_expires_at: float = 0.00
        self.file_path = Path(__name__).parent.joinpath("tokens.json")
        self.scope = "user-library-read playlist-modify-public playlist-modify-private"

        if self.file_path.exists():
            self.load_tokens()
        else:
            verifier, challenge = pkce.generate_pkce_pair()
            self.code_verifier = verifier
            self.code_challenge = challenge
            self.state = getenv("SPOTIFY_STATE")
            self.auth_event = threading.Event()
            self.start_listening()

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

    def get_access_token(self, authorization_code: str) -> TokenData:
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

        self.access_token = response_data["access_token"]
        self.refresh_token = response_data.get("refresh_token")
        self.token_expires_at = time.time() + response_data["expires_in"]
        self.store_tokens()
        return response_data

    def refresh_access_token(self) -> None:
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
            self.access_token = response_data["access_token"]
            self.token_expires_at = time.time() + response_data["expires_in"]
            self.store_tokens()
        else:
            raise Exception(f"Error refreshing access token: {response_data}")

    def is_token_expired(self) -> bool:
        return time.time() >= self.token_expires_at

    def get_valid_access_token(self) -> str:
        self.logger.info("Getting valid access token")
        if self.is_token_expired():
            self.refresh_access_token()
        return self.access_token

    def store_tokens(self) -> None:
        token_data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expires_at": self.token_expires_at,
        }
        with open(self.file_path, "w", encoding="utf-8") as file:
            json.dump(token_data, file)

    def load_tokens(self) -> None:
        self.logger.info("Loading tokens from file")
        with open(self.file_path, "r", encoding="utf-8") as file:
            token_data = json.load(file)
            self.access_token = token_data["access_token"]
            self.refresh_token = token_data["refresh_token"]
            self.token_expires_at = token_data["token_expires_at"]

    def callback(self, code: str) -> None:
        self.get_access_token(code)
        self.auth_event.set()

    def start_listening(self) -> None:
        httpd = CustomHTTPServer(self.server_address, RequestHandler, self.callback)
        thread = threading.Thread(target=httpd.serve_forever)
        thread.daemon = True
        thread.start()
        self.logger.info("Please go to the browser to authorize the app.")
        self.logger.info("Listening for authorization callback...")
        webbrowser.open(self.get_authorization_url())
        self.auth_event.wait()

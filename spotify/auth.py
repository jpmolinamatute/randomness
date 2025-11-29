import asyncio
import logging
import threading
import time
import webbrowser
from os import environ
from typing import Any, TypedDict

import httpx
import pkce

from spotify.helpers import CustomHTTPServer, RequestHandler
from spotify.schema import SpotifyCredentials, SpotifySecrets
from spotify.token import Token, TokenError


class SpotifyError(TypedDict):
    status: int
    message: str


class Auth:
    """
    Manage Spotify OAuth tokens with PKCE.
    """

    REFRESH_LEEWAY_SECONDS = 60
    AUTH_TIMEOUT_SECONDS = 300
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    SERVER_ADDRESS: tuple[str, int] = ("127.0.0.1", 5000)
    TIMEOUT = 15
    SCOPE = (
        "user-library-read playlist-modify-public playlist-modify-private "
        "user-modify-playback-state user-read-playback-state"
    )

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.logger.debug("Initializing Auth with PKCE")
        code_verifier, code_challenge = pkce.generate_pkce_pair()
        # Group secrets (client_id, client_secret, state)
        self.secrets = SpotifySecrets(
            client_id=environ["SPOTIFY_CLIENT_ID"],
            client_secret=environ["SPOTIFY_CLIENT_SECRET"],
            state=environ["SPOTIFY_STATE"],
            code_verifier=code_verifier,
            code_challenge=code_challenge,
        )

        # Group credentials (access/refresh/scope/texp window)
        self.credentials = SpotifyCredentials(
            access_token="",
            refresh_token="",
            scope=self.SCOPE,
        )

        # Event is created when starting auth flow
        self.auth_event: threading.Event

        self.logger.debug(
            "Auth configured: redirect_uri=%s scope=%s state_set=%s",
            self.redirect_uri,
            self.SCOPE,
            bool(self.secrets.state),
        )

    @property
    def redirect_uri(self) -> str:
        host, port = self.SERVER_ADDRESS
        return f"http://{host}:{port}/callback"

    def is_token_expired(self) -> bool:
        now = time.time()
        try:
            token_data = Token()
            token_data.load_tokens()
            expires_at = token_data.token_expires_at
        except TokenError:
            # If we cannot read expiry, force a refresh
            self.logger.debug("Token expiry unknown; treating as expired")
            return True
        remaining = (expires_at - self.REFRESH_LEEWAY_SECONDS) - now
        self.logger.debug(
            "Checking token expiration: now=%.0f expires_at=%.0f leeway=%ds remaining=%.0fs",
            now,
            expires_at,
            self.REFRESH_LEEWAY_SECONDS,
            remaining,
        )
        return now >= (expires_at - self.REFRESH_LEEWAY_SECONDS)

    def build_and_store_token(
        self, data: dict[str, Any], previous_refresh_token: str | None = None
    ) -> Token:
        """Create and persist a Token from raw response JSON."""
        self.logger.debug(
            "Building Token from response: has_refresh=%s expires_in=%s ",
            "refresh_token" in data,
            data.get("expires_in"),
        )
        token = Token(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", previous_refresh_token or ""),
            token_expires_at=time.time() + data["expires_in"],
        )
        token.store_tokens()

        # Update grouped credentials snapshot
        self.credentials = SpotifyCredentials(
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_in=max(0.0, token.token_expires_at - time.time()),
            scope=self.credentials.scope,
        )

        self.logger.debug(
            "Stored tokens: access_len=%d refresh_present=%s expires_at=%.0f",
            len(self.credentials.access_token or ""),
            bool(self.credentials.refresh_token),
            token.token_expires_at,
        )
        return token

    def get_authorization_url(self) -> str:
        self.logger.debug(
            "Generating authorization URL with  redirect_uri=%s scope=%s state_set=%s",
            self.redirect_uri,
            self.credentials.scope,
            bool(self.secrets.state),
        )

        return (
            "https://accounts.spotify.com/authorize"
            "?response_type=code"
            "&code_challenge_method=S256"
            f"&client_id={self.secrets.client_id}"
            f"&scope={self.credentials.scope}"
            f"&redirect_uri={self.redirect_uri}"
            f"&state={self.secrets.state}"
            f"&code_challenge={self.secrets.code_challenge}"
        )

    async def exchange_code_for_token(self, authorization_code: str) -> Token:
        self.logger.debug(
            "Exchanging authorization code for access token: code_len=%d redirect_uri=%s",
            len(authorization_code or ""),
            self.redirect_uri,
        )

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.secrets.client_id,
            "code_verifier": self.secrets.code_verifier,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL, headers=headers, data=data, timeout=self.TIMEOUT
            )
        response_data = response.json()
        if response.status_code != 200:
            raise TokenError(f"Error obtaining access token: {response_data}")
        return self.build_and_store_token(response_data, self.credentials.refresh_token)

    def handle_oauth(self, code: str) -> None:
        self.logger.debug("Received OAuth callback")
        # Run async exchange in sync callback
        asyncio.run(self.exchange_code_for_token(code))
        self.auth_event.set()

    def start_auth_flow(self) -> None:
        """Perform interactive OAuth code grant, blocking until completion or timeout."""
        self.logger.debug(
            "Starting authentication server: addr=%s redirect_uri=%s timeout=%ss",
            self.SERVER_ADDRESS,
            self.redirect_uri,
            self.AUTH_TIMEOUT_SECONDS,
        )
        # Generate PKCE pair for this auth session

        self.auth_event = threading.Event()
        httpd = CustomHTTPServer(self.SERVER_ADDRESS, RequestHandler, self.handle_oauth)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            self.logger.info("Authorize the app in your browser.")
            self.logger.info("Listening for authorization callback...")
            if not webbrowser.open(self.get_authorization_url()):
                self.logger.warning(
                    "Could not open browser automatically. Visit URL manually: %s",
                    self.get_authorization_url(),
                )
            if not self.auth_event.wait(timeout=self.AUTH_TIMEOUT_SECONDS):
                raise TokenError("Timeout waiting for user authorization")
        finally:
            self.logger.debug("Shutting down authentication server")
            httpd.shutdown()
            thread.join(timeout=2)

    async def refresh_access_token(self) -> Token | None:
        self.logger.debug(
            "Refreshing access token: token_url=%s has_refresh=%s",
            self.TOKEN_URL,
            bool(self.credentials.refresh_token),
        )
        if not self.credentials.refresh_token:
            raise TokenError("No refresh token available")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.credentials.refresh_token,
            "client_id": self.secrets.client_id,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL, headers=headers, data=data, timeout=self.TIMEOUT
            )
        response_data = response.json()
        if response.status_code == 200:
            return self.build_and_store_token(response_data, self.credentials.refresh_token)
        if response_data.get("error") == "invalid_grant":
            self.logger.error("Refresh token revoked, re-authenticating...")
            self.start_auth_flow()
            return None
        raise TokenError(f"Error refreshing access token: {response_data}")

    async def load_or_authenticate_tokens(self) -> None:
        self.logger.debug("Initializing token data: attempting to load stored tokens")
        try:
            token_data = Token()
            token_data.load_tokens()
            # Update in-memory credentials from persisted token store
            self.credentials.access_token = token_data.access_token
            self.credentials.refresh_token = token_data.refresh_token
            # Set a snapshot of remaining time for logging/initial check
            self.credentials.expires_in = max(0.0, token_data.token_expires_at - time.time())
            self.logger.debug(
                "Loaded tokens: expires_at=%.0f now=%.0f",
                token_data.token_expires_at,
                time.time(),
            )
            if self.is_token_expired():
                # Run async refresh in sync context
                await self.refresh_access_token()
        except TokenError:
            self.logger.debug("No valid stored tokens found; starting authentication flow")
            self.start_auth_flow()

    async def get_valid_access_token(self) -> str:
        self.logger.debug("Ensuring valid access token; will refresh if expired")
        if self.is_token_expired():
            await self.refresh_access_token()
        self.logger.debug("Returning access token")
        return self.credentials.access_token

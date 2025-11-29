# pylint: disable=redefined-outer-name
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from spotify.auth import Auth
from spotify.client import Client
from spotify.db import DB


def _setup_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mock environment variables."""
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "fake_client_id")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "fake_client_secret")
    monkeypatch.setenv("SPOTIFY_STATE", "fake_state")
    monkeypatch.setenv("SPOTIFY_PLAYLIST_ID", "fake_playlist_id")
    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("MONGO_DB_NAME", "test_db")


@pytest.fixture
def mock_db() -> MagicMock:
    """Mock the DB class."""
    db = MagicMock(spec=DB)
    db.get_latest_playlist_uris.return_value = ["spotify:track:1", "spotify:track:2"]
    return db


@pytest.fixture
def mock_auth(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Mock the Auth class."""
    _setup_env(monkeypatch)
    # We mock the internal secrets and credentials to avoid real init logic if possible,
    # or just mock the methods.
    # Since Auth.__init__ does some work (pkce generation), we might want to mock that too
    # or just let it run if it's side-effect free (it generates random strings).
    # However, it reads env vars, so mock_env is needed.

    # For unit testing Auth methods, we might want a real instance with mocked network calls.
    # For testing Client, we want a mocked Auth instance.

    auth = MagicMock(spec=Auth)
    auth.get_valid_access_token = AsyncMock(return_value="fake_access_token")
    auth.redirect_uri = "http://localhost:5000/callback"
    return auth


@pytest.fixture
def client_instance(
    mock_auth: MagicMock, mock_db: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> Client:
    """Mock the Client class or return a real instance with mocked dependencies."""
    _setup_env(monkeypatch)
    # For testing Client methods, we want a real Client instance with mocked Auth and DB.
    client = Client(auth=mock_auth, my_mongo=mock_db)
    return client


@pytest.fixture
def auth_instance(monkeypatch: pytest.MonkeyPatch) -> Auth:
    """Return a real Auth instance with mocked env and suppressed auto-auth."""
    _setup_env(monkeypatch)
    with patch("spotify.auth.Auth.load_or_authenticate_tokens"):
        return Auth()

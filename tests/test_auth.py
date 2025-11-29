import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from spotify.auth import Auth
from spotify.token import TokenError


def test_auth_init(auth_instance: Auth) -> None:
    """Test Auth initialization."""
    assert auth_instance.secrets.client_id == "fake_client_id"
    assert auth_instance.secrets.client_secret == "fake_client_secret"
    assert auth_instance.secrets.state == "fake_state"


def test_get_authorization_url(auth_instance: Auth) -> None:
    """Test generation of authorization URL."""
    url = auth_instance.get_authorization_url()
    assert "https://accounts.spotify.com/authorize" in url
    assert "client_id=fake_client_id" in url
    assert "redirect_uri=http://127.0.0.1:5000/callback" in url
    assert "response_type=code" in url


@pytest.mark.asyncio
async def test_exchange_code_for_token(auth_instance: Auth) -> None:
    """Test exchanging code for token."""
    mock_response_data = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
        "expires_in": 3600,
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_post.return_value = mock_response

        # Mock Token.store_tokens to avoid file I/O
        with patch("spotify.token.Token.store_tokens") as mock_store:
            token = await auth_instance.exchange_code_for_token("fake_code")

            assert token.access_token == "new_access_token"
            assert token.refresh_token == "new_refresh_token"
            assert auth_instance.credentials.access_token == "new_access_token"
            mock_store.assert_called_once()


@pytest.mark.asyncio
async def test_exchange_code_for_token_failure(auth_instance: Auth) -> None:
    """Test exchanging code for token failure."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "invalid_grant"}
        mock_post.return_value = mock_response

        with pytest.raises(TokenError):
            await auth_instance.exchange_code_for_token("bad_code")


@pytest.mark.asyncio
async def test_refresh_access_token(auth_instance: Auth) -> None:
    """Test refreshing access token."""
    auth_instance.credentials.refresh_token = "valid_refresh_token"
    mock_response_data = {
        "access_token": "refreshed_access_token",
        "expires_in": 3600,
        # refresh_token might not be returned if it hasn't changed
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_post.return_value = mock_response

        with patch("spotify.token.Token.store_tokens") as mock_store:
            token = await auth_instance.refresh_access_token()

            assert token is not None
            assert token.access_token == "refreshed_access_token"
            # Should keep old refresh token if not provided
            assert token.refresh_token == "valid_refresh_token"
            mock_store.assert_called_once()


def test_is_token_expired(auth_instance: Auth) -> None:
    """Test token expiration check."""
    # Mock Token.load_tokens
    with patch("spotify.token.Token.load_tokens"):
        # load_tokens doesn't return, it sets attributes on self instance in real code,
        # but here we are patching the method on the class or instance.
        # Wait, is_token_expired creates a NEW Token() instance.
        # So we need to patch Token class or its method.

        with patch("spotify.auth.Token") as mock_token_class:
            instance = mock_token_class.return_value
            # Case 1: Expired
            instance.token_expires_at = time.time() - 100
            assert auth_instance.is_token_expired() is True

            # Case 2: Not expired
            instance.token_expires_at = time.time() + 3600
            assert auth_instance.is_token_expired() is False

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
    # Case 1: Expired
    auth_instance.credentials.expires_at = time.time() - 100
    assert auth_instance.is_token_expired() is True

    # Case 2: Not expired
    auth_instance.credentials.expires_at = time.time() + 3600
    assert auth_instance.is_token_expired() is False


def test_handle_oauth(auth_instance: Auth) -> None:
    """Test handle_oauth invokes async token exchange and sets event."""
    auth_instance.auth_event = MagicMock()

    with patch("asyncio.run") as mock_asyncio_run:
        with patch.object(
            auth_instance, "exchange_code_for_token", new_callable=MagicMock
        ) as mock_exchange:
            mock_exchange.return_value = "fake_coroutine_object"
            auth_instance.handle_oauth("test_code")

            mock_exchange.assert_called_once_with("test_code")
            mock_asyncio_run.assert_called_once()
            auth_instance.auth_event.set.assert_called_once()


def test_start_auth_flow_timeout(auth_instance: Auth) -> None:
    """Test start_auth_flow gracefully handles timeout wait."""
    with patch("spotify.auth.CustomHTTPServer") as mock_server:
        mock_httpd = MagicMock()
        mock_server.return_value = mock_httpd

        with patch("threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread

            with patch("webbrowser.open", return_value=True):
                # We patch AUTH_TIMEOUT_SECONDS to be extremely low, but patching Event is cleaner
                with patch("threading.Event") as mock_event_cls:
                    mock_event = MagicMock()
                    mock_event.wait.return_value = False  # Simulate timeout
                    mock_event_cls.return_value = mock_event

                    with pytest.raises(TokenError, match="Timeout waiting for user authorization"):
                        auth_instance.start_auth_flow()

                    mock_httpd.shutdown.assert_called_once()
                    mock_thread.join.assert_called_once()


@pytest.mark.asyncio
async def test_load_or_authenticate_tokens(auth_instance: Auth) -> None:
    """Test token loader orchestrates properly."""
    # Test path 1: load fails -> triggers start_auth_flow
    with patch("spotify.token.Token.load_tokens", side_effect=TokenError("no token")):
        with patch.object(auth_instance, "start_auth_flow") as mock_start_flow:
            await auth_instance.load_or_authenticate_tokens()
            mock_start_flow.assert_called_once()

    # Test path 2: load succeeds, but expired -> triggers refresh
    auth_instance.credentials.expires_at = time.time() - 1000
    with patch("spotify.token.Token.load_tokens"):
        with patch.object(
            auth_instance, "refresh_access_token", new_callable=AsyncMock
        ) as mock_refresh:
            await auth_instance.load_or_authenticate_tokens()
            mock_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_get_valid_access_token(auth_instance: Auth) -> None:
    """Test that accessing tokens automatically refreshes if expired."""
    auth_instance.credentials.access_token = "valid_tok"
    auth_instance.credentials.expires_at = time.time() - 1000  # expired

    with patch.object(
        auth_instance, "refresh_access_token", new_callable=AsyncMock
    ) as mock_refresh:
        # We can simulate refresh modifying the access_token
        async def fake_refresh() -> None:
            auth_instance.credentials.access_token = "refreshed_tok"

        mock_refresh.side_effect = fake_refresh

        token = await auth_instance.get_valid_access_token()
        mock_refresh.assert_called_once()
        assert token == "refreshed_tok"


@pytest.mark.asyncio
async def test_refresh_access_token_invalid_grant(auth_instance: Auth) -> None:
    """Test refreshing catching 'invalid_grant' falls back to start_auth_flow."""
    auth_instance.credentials.refresh_token = "bad_refresh"
    mock_response_data = {"error": "invalid_grant"}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        r = MagicMock()
        r.status_code = 400
        r.json.return_value = mock_response_data
        mock_post.return_value = r

        with patch.object(auth_instance, "start_auth_flow") as mock_start_flow:
            result = await auth_instance.refresh_access_token()

            assert result is None
            mock_start_flow.assert_called_once()

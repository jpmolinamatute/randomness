import json
from unittest.mock import mock_open, patch

import pytest

from spotify.token import Token, TokenError

MOCK_EXPIRES_AT = 123.0


def test_load_tokens_missing_file() -> None:
    """Test load_tokens when the token file does not exist."""
    token = Token()
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(TokenError, match="Token file not found"):
            token.load_tokens()


def test_load_tokens_json_decode_error() -> None:
    """Test load_tokens when the file contains invalid JSON."""
    token = Token()
    with patch("pathlib.Path.exists", return_value=True):
        m = mock_open(read_data="{invalid_json")
        with patch("pathlib.Path.open", m):
            with pytest.raises(TokenError, match="Failed reading token file"):
                token.load_tokens()


def test_load_tokens_missing_keys() -> None:
    """Test load_tokens when valid JSON is missing required fields."""
    token = Token()
    with patch("pathlib.Path.exists", return_value=True):
        bad_data = '{"access_token": "valid", "refresh_token": "valid"}'  # Missing token_expires_at
        m = mock_open(read_data=bad_data)
        with patch("pathlib.Path.open", m):
            with pytest.raises(TokenError, match="Token file missing key"):
                token.load_tokens()


def test_load_tokens_success() -> None:
    """Test load_tokens loading all keys successfully."""
    token = Token()
    with patch("pathlib.Path.exists", return_value=True):
        valid_data = f'{{"access_token": "acc", "refresh_token": "ref", "token_expires_at": {MOCK_EXPIRES_AT}}}'
        m = mock_open(read_data=valid_data)
        with patch("pathlib.Path.open", m):
            token.load_tokens()
            assert token.access_token == "acc"
            assert token.refresh_token == "ref"
            assert token.token_expires_at == MOCK_EXPIRES_AT


def test_store_tokens_success() -> None:
    """Test store_tokens writes correctly to disk."""
    token = Token(access_token="acc", refresh_token="ref", token_expires_at=MOCK_EXPIRES_AT)
    m = mock_open()
    with patch("pathlib.Path.open", m):
        token.store_tokens()
        m.assert_called_once_with("w", encoding="utf-8")

        # Verify JSON dump call
        # the argument to mock_open's write might be called multiple times due to indent=4
        handle = m()
        written = "".join(call.args[0] for call in handle.write.call_args_list)
        data = json.loads(written)
        assert data["access_token"] == "acc"
        assert data["refresh_token"] == "ref"
        assert data["token_expires_at"] == MOCK_EXPIRES_AT


def test_store_tokens_permission_error() -> None:
    """Test store_tokens handling write exceptions."""
    token = Token()
    m = mock_open()
    # Mock raising exception on open
    m.side_effect = PermissionError("Permission denied")
    with patch("pathlib.Path.open", m):
        with pytest.raises(TokenError, match="Failed storing token file"):
            token.store_tokens()

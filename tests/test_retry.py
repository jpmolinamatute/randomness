from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from spotify.client import Client


@pytest.mark.asyncio
async def test_fetch_tracks_batch_retries(client_instance: Client) -> None:
    """Test that fetch_tracks_batch retries on 429."""
    expected_calls = 2
    batch_data = {
        "tracks": {
            "items": [],
            "total": 0,
            "next": None,
            "href": "http://spotify.com",
            "limit": 20,
            "offset": 0,
            "previous": None,
        }
    }

    mock_client = AsyncMock(spec=httpx.AsyncClient)

    # First response: 429
    r429 = MagicMock()
    r429.status_code = 429
    r429.headers = {"Retry-After": "1"}

    # Second response: 200
    r200 = MagicMock()
    r200.status_code = 200
    r200.json.return_value = batch_data

    mock_client.get.side_effect = [r429, r200]

    # Patch asyncio.sleep to avoid waiting during test
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await client_instance.fetch_tracks_batch(
            mock_client, "http://example.com/test?offset=0&limit=50", "test"
        )

    # Verify it was called twice
    assert mock_client.get.call_count == expected_calls


@pytest.mark.asyncio
async def test_delete_with_sem_retries(client_instance: Client) -> None:
    """Test that delete_with_sem retries on 429."""
    expected_calls = 2
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    sem = AsyncMock()

    # First response: 429
    r429 = MagicMock()
    r429.status_code = 429
    r429.headers = {"Retry-After": "1"}

    # Second response: 200
    r200 = MagicMock()
    r200.status_code = 200

    # Mock the request method (used by _make_delete_request)
    mock_client.request.side_effect = [r429, r200]

    url = "http://example.com/delete"
    data: dict[str, Any] = {"tracks": []}

    # Patch asyncio.sleep to avoid waiting during test
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await client_instance.delete_with_sem(mock_client, sem, url, data)

    # Verify it was called twice
    assert mock_client.request.call_count == expected_calls

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from spotify.client import Client
from spotify.schema import LikedTrackItem, LikedTracksResponse

EXPECTED_TRACKS_COUNT = 2
EXPECTED_DELETE_COUNT = 3
EXPECTED_FETCH_CALLS = 2


@pytest.mark.asyncio
async def test_get_available_device_id(client_instance: Client) -> None:
    """Test getting available device ID."""
    mock_response_data = {
        "devices": [{"id": "device_1", "is_active": True}, {"id": "device_2", "is_active": False}]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response

        device_id = await client_instance.get_available_device_id()
        assert device_id == "device_1"

        # Test no devices
        mock_response_empty = MagicMock()
        mock_response_empty.status_code = 200
        mock_response_empty.json.return_value = {"devices": []}
        mock_get.return_value = mock_response_empty
        device_id = await client_instance.get_available_device_id()
        assert device_id is None


def get_valid_track_data(uri: str = "spotify:track:1", name: str = "Track 1") -> dict[str, Any]:
    return {
        "track": {
            "uri": uri,
            "name": name,
            "type": "track",
            "id": uri.split(":")[-1],
            "duration_ms": 1000,
            "explicit": False,
            "popularity": 50,
            "disc_number": 1,
            "track_number": 1,
            "external_urls": {"spotify": "http://spotify.com"},
            "external_ids": {"isrc": "isrc"},
            "available_markets": ["US"],
            "album": {
                "uri": "spotify:album:1",
                "name": "Album 1",
                "type": "album",
                "id": "album1",
                "album_type": "album",
                "total_tracks": 10,
                "available_markets": ["US"],
                "external_urls": {"spotify": "http://spotify.com"},
                "href": "http://spotify.com",
                "images": [],
                "release_date": "2023",
                "release_date_precision": "year",
                "artists": [
                    {
                        "uri": "spotify:artist:1",
                        "name": "Artist 1",
                        "type": "artist",
                        "id": "artist1",
                        "external_urls": {"spotify": "http://spotify.com"},
                        "href": "http://spotify.com",
                    }
                ],
            },
            "artists": [
                {
                    "uri": "spotify:artist:1",
                    "name": "Artist 1",
                    "type": "artist",
                    "id": "artist1",
                    "external_urls": {"spotify": "http://spotify.com"},
                    "href": "http://spotify.com",
                }
            ],
            "href": "http://spotify.com",
        },
        "added_at": "2023-01-01T00:00:00Z",
    }


@pytest.mark.asyncio
async def test_get_all_liked_tracks(client_instance: Client) -> None:
    """Test retrieving all liked tracks."""
    # Mock first batch response
    first_batch_data = {
        "total": 2,
        "items": [
            get_valid_track_data("spotify:track:1", "Track 1"),
            get_valid_track_data("spotify:track:2", "Track 2"),
        ],
        "next": None,
        "href": "http://spotify.com",
        "limit": 20,
        "offset": 0,
        "previous": None,
    }

    # Let's mock httpx to return data for fetch_tracks_batch to parse.

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = first_batch_data
        mock_get.return_value = mock_response

        await client_instance.get_all_liked_tracks()

        # Verify DB insertion
        # Cast to MagicMock to satisfy MyPy
        mock_db_insert = cast(MagicMock, client_instance.db.insert_tracks)
        assert mock_db_insert.called
        # We expect 2 tracks to be inserted
        _, _ = mock_db_insert.call_args
        assert len(mock_db_insert.call_args[0][0]) == EXPECTED_TRACKS_COUNT
        assert mock_db_insert.call_args[0][0][0]["uri"] == "spotify:track:1"


@pytest.mark.asyncio
async def test_delete_all_playlist_tracks(client_instance: Client) -> None:
    """Test deleting all tracks from playlist in batches."""
    # Mock responses for fetch_tracks_batch
    # Batch 1: Full batch
    track1 = get_valid_track_data("spotify:track:1", "Track 1")["track"]
    track2 = get_valid_track_data("spotify:track:2", "Track 2")["track"]

    batch_1_tracks = [track1, track2]
    # We need to return a LikedTracksResponse object

    response_batch_1 = LikedTracksResponse(
        href="http://href",
        limit=100,
        offset=0,
        total=2,
        items=[LikedTrackItem(track=t, added_at="2023-01-01T00:00:00Z") for t in batch_1_tracks],
    )

    # Batch 2: Empty
    response_batch_2 = LikedTracksResponse(
        href="http://href", limit=100, offset=0, total=0, items=[]
    )

    # Patch fetch_tracks_batch on the instance
    with patch.object(client_instance, "fetch_tracks_batch", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.side_effect = [response_batch_1, response_batch_2]

        # Patch delete_with_sem
        with patch.object(
            client_instance, "delete_with_sem", new_callable=AsyncMock
        ) as mock_delete:
            # Patch BATCH_SIZE to 2 so that valid full batch (2 items) triggers next loop
            with patch.object(Client, "BATCH_SIZE", 2):
                await client_instance.delete_all_playlist_tracks()

            # Verify fetch was called twice (once for tracks, once getting empty)
            assert mock_fetch.call_count == EXPECTED_FETCH_CALLS

        # Verify delete was called once (for the first batch). Second batch fetch was empty so no delete.
        assert mock_delete.call_count == 1
        args, _ = mock_delete.call_args
        # client, sem, url, json_data are positional args
        json_data = args[3]
        assert "tracks" in json_data
        deleted_uris = [t["uri"] for t in json_data["tracks"]]
        assert deleted_uris == ["spotify:track:1", "spotify:track:2"]


@pytest.mark.asyncio
async def test_populate_playlist_from_db(client_instance: Client) -> None:
    """Test populating playlist from DB."""
    # Cast to MagicMock to satisfy MyPy
    mock_db_get = cast(MagicMock, client_instance.db.get_latest_playlist_uris)
    mock_db_get.return_value = ["uri1", "uri2"]

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        await client_instance.populate_playlist_from_db()

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert "uris" in kwargs["json"]
        assert kwargs["json"]["uris"] == ["uri1", "uri2"]


@pytest.mark.asyncio
async def test_update_queue(client_instance: Client) -> None:
    """Test updating the queue."""
    # Mock get_available_device_id
    # Use monkeypatch or patch.object instead of assignment to satisfy MyPy
    with patch.object(
        client_instance, "get_available_device_id", new_callable=AsyncMock
    ) as mock_get_device:
        mock_get_device.return_value = "device_123"

        with patch("httpx.AsyncClient.put", new_callable=AsyncMock) as mock_put:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_put.return_value = mock_response

            await client_instance.update_queue()

            mock_put.assert_called_once()
            _, kwargs = mock_put.call_args
            assert "device_id=device_123" in mock_put.call_args[0][0]
            assert (
                kwargs["json"]["context_uri"]
                == f"spotify:playlist:{client_instance.spotify_playlist_id}"
            )

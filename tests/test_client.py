from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import ValidationError

from spotify.client import Client
from spotify.schema import LikedTrackItem, LikedTracksResponse

EXPECTED_TRACKS_COUNT = 2
EXPECTED_DELETE_COUNT = 3
EXPECTED_FETCH_CALLS = 1
EXPECTED_PLAYLIST_PAGES_CALLS = 2
EXPECTED_LIKED_TRACKS_BATCHES = 3
EXPECTED_TOTAL_LIKED_TRACKS = 150
EXPECTED_CHUNKED_POST_CALLS = 3


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
            "id": uri.rsplit(":", maxsplit=1)[-1],
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
        mock_db_insert = cast(MagicMock, client_instance.db.sync_tracks)
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
        assert "items" in json_data
        deleted_uris = [t["uri"] for t in json_data["items"]]
        assert deleted_uris == ["spotify:track:1", "spotify:track:2"]


@pytest.mark.asyncio
async def test_populate_playlist_with_uris(client_instance: Client) -> None:
    """Test populating playlist directly with uris."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        test_uris = ["uri1", "uri2"]
        await client_instance.populate_playlist_with_uris(test_uris)

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


@pytest.mark.asyncio
async def test_get_all_playlists(client_instance: Client) -> None:
    """Test retrieving all playlists with pagination."""
    mock_response_1 = {
        "items": [{"name": "P1", "id": "1", "tracks": {"total": 5}}],
        "next": "http://next_url?offset=50&limit=50",
    }
    mock_response_2 = {
        "items": [{"name": "P2", "id": "2", "tracks": {"total": 3}}],
        "next": None,
    }
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        r1 = MagicMock()
        r1.status_code = 200
        r1.json.return_value = mock_response_1
        r2 = MagicMock()
        r2.status_code = 200
        r2.json.return_value = mock_response_2
        mock_get.side_effect = [r1, r2]

        await client_instance.get_all_playlists()
        assert mock_get.call_count == EXPECTED_PLAYLIST_PAGES_CALLS


def test_describe_paging_window_invalid(client_instance: Client) -> None:
    """Test describe_paging_window raises ValueError on invalid url."""
    with pytest.raises(ValueError, match="Invalid URL"):
        client_instance.describe_paging_window("http://spotify.com/playlists?bad=1")


@pytest.mark.asyncio
async def test_get_available_device_id_exception(client_instance: Client) -> None:
    """Test get_available_device_id raises exception on network error."""
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.RequestError("Network error")
        with pytest.raises(httpx.RequestError):
            await client_instance.get_available_device_id()


@pytest.mark.asyncio
async def test_get_available_device_id_none_active(client_instance: Client) -> None:
    """Test get_available_device_id returns None if no devices are active."""
    mock_response_data = {
        "devices": [{"id": "device_1", "is_active": False}, {"id": "device_2", "is_active": False}]
    }
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = mock_response_data
        mock_get.return_value = r

        device_id = await client_instance.get_available_device_id()
        assert device_id is None


@pytest.mark.asyncio
async def test_get_all_liked_tracks_multiple_batches(client_instance: Client) -> None:
    """Test retrieving liked tracks spanning multiple batches using gather."""
    # First batch returns total=150
    first_batch_data = {
        "total": 150,
        "items": [get_valid_track_data(f"spotify:track:{i}", f"Track {i}") for i in range(50)],
        "next": "url",
        "href": "http",
        "limit": 50,
        "offset": 0,
        "previous": None,
    }
    # Subsequent batches
    second_batch_data = dict(first_batch_data)
    second_batch_data["items"] = [
        get_valid_track_data(f"spotify:track:{i}", f"Track {i}") for i in range(50, 100)
    ]
    third_batch_data = dict(first_batch_data)
    third_batch_data["items"] = [
        get_valid_track_data(f"spotify:track:{i}", f"Track {i}") for i in range(100, 150)
    ]

    # Mock fetch_tracks_batch instead of pure httpx.get to safely bypass retries handling complexity over batches
    with patch.object(client_instance, "fetch_tracks_batch", new_callable=AsyncMock) as mock_fetch:
        # fetch_tracks_batch is called first for total, then gather for remaining
        mock_fetch.side_effect = [
            LikedTracksResponse.model_validate(first_batch_data),
            LikedTracksResponse.model_validate(second_batch_data),
            LikedTracksResponse.model_validate(third_batch_data),
        ]

        with patch.object(client_instance, "ME_BATCH_SIZE", 50):
            await client_instance.get_all_liked_tracks()

        assert mock_fetch.call_count == EXPECTED_LIKED_TRACKS_BATCHES
        mock_db_insert = cast(MagicMock, client_instance.db.sync_tracks)
        assert mock_db_insert.called
        args, _ = mock_db_insert.call_args
        assert len(args[0]) == EXPECTED_TOTAL_LIKED_TRACKS


@pytest.mark.asyncio
async def test_delete_all_playlist_tracks_exception(client_instance: Client) -> None:
    """Test exception during delete batch bubbles out securely."""
    track1 = get_valid_track_data("spotify:track:1", "Track 1")["track"]
    response_batch = LikedTracksResponse(
        href="http",
        limit=100,
        offset=0,
        total=10,
        items=[LikedTrackItem(track=track1, added_at="2023-01-01T00:00:00Z")],
    )
    with patch.object(client_instance, "fetch_tracks_batch", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = response_batch

        with patch.object(
            client_instance, "delete_with_sem", new_callable=AsyncMock
        ) as mock_delete:
            mock_delete.side_effect = Exception("Delete failed!")

            with pytest.raises(Exception, match="Delete failed!"):
                await client_instance.delete_all_playlist_tracks()


@pytest.mark.asyncio
async def test_populate_playlist_with_uris_chunks(client_instance: Client) -> None:
    """Test chunking logic when more uris than batch size are supplied."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        r = MagicMock()
        r.status_code = 201
        mock_post.return_value = r

        # Give 250 URIs, batch size 100 -> expect 3 post calls
        test_uris = [f"uri{i}" for i in range(250)]
        with patch.object(client_instance, "BATCH_SIZE", 100):
            await client_instance.populate_playlist_with_uris(test_uris)

        assert mock_post.call_count == EXPECTED_CHUNKED_POST_CALLS


@pytest.mark.asyncio
async def test_update_queue_no_device(client_instance: Client) -> None:
    """Test update_queue aborts correctly if device ID proves none."""
    with patch.object(
        client_instance, "get_available_device_id", new_callable=AsyncMock
    ) as mock_get_dev:
        mock_get_dev.return_value = None

        with patch("httpx.AsyncClient.put", new_callable=AsyncMock) as mock_put:
            await client_instance.update_queue()
            mock_put.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_tracks_batch_exception(client_instance: Client) -> None:
    """Test fetch_tracks_batch bubbling up validation errors."""
    mock_client = AsyncMock()
    with patch.object(client_instance, "_make_get_request", new_callable=AsyncMock) as mock_req:
        r = MagicMock()
        r.status_code = 200
        # Passing invalid object without 'items' to trigger Pydantic ValidationError
        r.json.return_value = {"invalid_data": True}
        mock_req.return_value = r

        with pytest.raises(ValidationError):
            await client_instance.fetch_tracks_batch(
                mock_client, "http://uri?offset=0&limit=5", "test"
            )

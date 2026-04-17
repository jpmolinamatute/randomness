# pylint: disable=redefined-outer-name
from typing import cast
from unittest.mock import ANY, MagicMock, mock_open, patch

import pytest
from pymongo.errors import AutoReconnect

from spotify.db import DB

EXPECTED_RANDOM_COUNT = 2
TEST_PLAYLIST_SIZE = 5
EXPECTED_TRACK_PIPELINE_SIZE = 4
EXPECTED_ARTIST_PIPELINE_SIZE = 5
EXPECTED_SUCCESS_RETRIES = 3
EXPECTED_MAX_RETRIES = 5
EXPECTED_EXPORT_COUNT = 2
EXPECTED_INDEX_COUNT = 3


@pytest.fixture
def db_instance(monkeypatch: pytest.MonkeyPatch) -> DB:
    monkeypatch.setenv("MONGO_INITDB_ROOT_USERNAME", "user")
    monkeypatch.setenv("MONGO_INITDB_ROOT_PASSWORD", "pass")
    monkeypatch.setenv("MONGO_INITDB_DATABASE", "test_db")
    # Mock MongoClient to avoid real connection
    with patch("spotify.db.MongoClient") as mock_client_cls:
        # Setup the mock client instance
        mock_client = mock_client_cls.return_value
        # Setup the mock db
        _ = mock_client.__getitem__.return_value

        db = DB()
        # Ensure the mocked client and db are attached to the instance
        # (The __init__ does this, but we want to be sure our mocks are the ones being used)
        return db


def test_init(db_instance: DB) -> None:
    """Test DB initialization."""
    assert db_instance.mongo_client is not None
    assert db_instance.mongo_db is not None
    assert db_instance.tracks_coll_name == "tracks"


def test_check_connection_success(db_instance: DB) -> None:
    """Test check_connection when successful."""
    mock_client = cast(MagicMock, db_instance.mongo_client)
    mock_client.server_info.return_value = {"version": "4.4"}
    assert db_instance.check_connection() is True


def test_check_connection_failure(db_instance: DB) -> None:
    """Test check_connection when it fails."""
    mock_client = cast(MagicMock, db_instance.mongo_client)
    mock_client.server_info.side_effect = Exception("Connection failed")
    assert db_instance.check_connection() is False


def test_get_tracks_coll(db_instance: DB) -> None:
    """Test retrieving tracks collection."""
    coll = db_instance.get_tracks_coll()
    # verify that we got the collection from the db
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.assert_called_with("tracks")
    assert coll == mock_db.__getitem__.return_value


def test_count_track(db_instance: DB) -> None:
    """Test count_track method."""
    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    filters = {"artist": "Test"}
    db_instance.count_track(filters)

    mock_coll.count_documents.assert_called_with(filters)


def test_sync_tracks(db_instance: DB) -> None:
    """Test sync_tracks method."""
    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    mock_coll.find.return_value = [{"uri": "old_uri"}]
    tracks = [{"uri": "new_uri"}]
    db_instance.sync_tracks(tracks)

    mock_coll.delete_many.assert_called_with({"uri": {"$in": ["old_uri"]}})
    mock_coll.bulk_write.assert_called_once()


def test_reset_collection(db_instance: DB) -> None:
    """Test reset_collection method."""
    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    with patch.object(db_instance, "logger") as mock_logger:
        db_instance.reset_collection("tracks")
        mock_logger.warning.assert_called_with(
            "tracks collection is no longer reset; use sync_tracks instead"
        )
        mock_coll.delete_many.assert_not_called()

    mock_coll.reset_mock()

    with pytest.raises(ValueError, match="Invalid collection name"):
        db_instance.reset_collection("invalid")


def test_export_to_json(db_instance: DB) -> None:
    """Test export_to_json method."""
    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    # Mock find return value
    mock_coll.find.return_value = [
        {"_id": "id1", "href": "href1", "name": "Track 1", "artists": [{"name": "Artist 1"}]}
    ]

    with patch("pathlib.Path.open", mock_open()) as mock_file:
        with patch("json.dump") as mock_json_dump:
            db_instance.export_to_json()

            mock_file.assert_called_once()
            mock_json_dump.assert_called_once()
            args, _ = mock_json_dump.call_args
            data = args[0]
            assert len(data) == 1
            assert data[0]["artist_name"] == "Artist 1"


def test_validate_item_count(db_instance: DB) -> None:
    """Test validate_item_count method."""
    # Mock count_track to return 200 (enough for max check)
    with patch.object(db_instance, "count_track", return_value=200):
        # Valid count
        db_instance.validate_item_count(TEST_PLAYLIST_SIZE)

        # Invalid types/values
        with pytest.raises(ValueError, match="must be an integer"):
            db_instance.validate_item_count("5")  # type: ignore

        with pytest.raises(ValueError, match="must be greater than 0"):
            db_instance.validate_item_count(0)

        with pytest.raises(ValueError, match="Number of items must be less than or equal to 100"):
            db_instance.validate_item_count(101)

        with pytest.raises(ValueError, match="must be less than"):
            db_instance.validate_item_count(250)


def test_generate_random_playlist_track(db_instance: DB) -> None:
    """Test generate_random_playlist with track type."""
    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    mock_cursor = MagicMock()
    mock_cursor.__iter__.return_value = [{"tracks": [{"uri": "uri_ex1"}, {"uri": "uri_ex2"}]}]
    mock_coll.aggregate.return_value = mock_cursor

    with patch.object(db_instance, "validate_item_count"):
        result_uris = db_instance.generate_random_playlist(TEST_PLAYLIST_SIZE)

        mock_coll.aggregate.assert_called_once()
        pipeline = mock_coll.aggregate.call_args[0][0]

        assert pipeline[0]["$sort"]["played_at"] == 1
        assert pipeline[2]["$sample"]["size"] == TEST_PLAYLIST_SIZE
        assert len(pipeline) == EXPECTED_TRACK_PIPELINE_SIZE  # $sort, $limit, $sample, $group

        mock_coll.update_many.assert_called_once_with(
            {"uri": {"$in": ["uri_ex1", "uri_ex2"]}}, {"$set": {"played_at": ANY}}
        )
        assert result_uris == ["uri_ex1", "uri_ex2"]


def test_generate_random_playlist_invalid(db_instance: DB) -> None:
    """Test generate_random_playlist with invalid item count."""
    with patch.object(
        db_instance, "validate_item_count", side_effect=ValueError("Invalid item type")
    ):
        with pytest.raises(ValueError, match="Invalid item type"):
            db_instance.generate_random_playlist(TEST_PLAYLIST_SIZE)


def test_sync_tracks_auto_reconnect_success(db_instance: DB) -> None:
    """Test sync_tracks retries bulk_write on AutoReconnect and eventually succeeds."""
    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    mock_coll.find.return_value = []

    # Fail 2 times then succeed
    mock_coll.bulk_write.side_effect = [
        AutoReconnect("timeout"),
        AutoReconnect("timeout"),
        MagicMock(),  # success
    ]

    tracks = [{"uri": "new_uri"}]
    db_instance.sync_tracks(tracks)

    # Should be called EXPECTED_SUCCESS_RETRIES times total
    assert mock_coll.bulk_write.call_count == EXPECTED_SUCCESS_RETRIES


def test_sync_tracks_auto_reconnect_failure(db_instance: DB) -> None:
    """Test sync_tracks retries bulk_write and eventually gives up."""
    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    mock_coll.find.return_value = []

    # Fail continuously
    mock_coll.bulk_write.side_effect = AutoReconnect("timeout")

    tracks = [{"uri": "new_uri"}]
    with pytest.raises(AutoReconnect):
        db_instance.sync_tracks(tracks)

    assert mock_coll.bulk_write.call_count == EXPECTED_MAX_RETRIES


def test_export_to_json_fallback(db_instance: DB) -> None:
    """Test export_to_json falls back if artists array is empty or missing."""
    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    mock_coll.find.return_value = [
        {"_id": "id1", "href": "href1", "name": "Track 1", "artists": []},
        {"_id": "id2", "href": "href2", "name": "Track 2"},  # Missing artists entirely
    ]

    with patch("pathlib.Path.open", mock_open()):
        with patch("json.dump") as mock_json_dump:
            db_instance.export_to_json()
            args, _ = mock_json_dump.call_args
            data = args[0]
            assert len(data) == EXPECTED_EXPORT_COUNT
            assert data[0]["artist_name"] == "Unknown"
            assert data[1]["artist_name"] == "Unknown"


def test_generate_random_playlist_empty_aggregate(db_instance: DB) -> None:
    """Test generate_random_playlist when aggregate returns empty."""
    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    mock_cursor = MagicMock()
    mock_cursor.__iter__.return_value = []
    mock_coll.aggregate.return_value = mock_cursor

    with patch.object(db_instance, "validate_item_count"):
        result_uris = db_instance.generate_random_playlist(TEST_PLAYLIST_SIZE)

        mock_coll.aggregate.assert_called_once()
        mock_coll.update_many.assert_not_called()
        assert result_uris == []


def test_check_connection_indexes(db_instance: DB) -> None:
    """Test check_connection initializes DB indexes."""
    mock_client = cast(MagicMock, db_instance.mongo_client)
    mock_client.server_info.return_value = {"version": "4.4"}

    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    assert db_instance.check_connection() is True

    assert mock_coll.create_index.call_count == EXPECTED_INDEX_COUNT
    # check that we called create_index with expected keys
    calls = mock_coll.create_index.call_args_list
    assert calls[0][0][0] == "uri"
    assert calls[1][0][0] == "played_at"
    assert calls[2][0][0] == "artists._id"

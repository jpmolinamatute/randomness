# pylint: disable=redefined-outer-name
from typing import cast
from unittest.mock import MagicMock, mock_open, patch

import pytest

from spotify.db import DB

EXPECTED_RANDOM_COUNT = 2
TEST_PLAYLIST_SIZE = 5


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
    assert db_instance.playlist_coll_name == "playlist"
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


def test_get_playlist_coll(db_instance: DB) -> None:
    """Test retrieving playlist collection."""
    coll = db_instance.get_playlist_coll()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.assert_called_with("playlist")
    assert coll == mock_db.__getitem__.return_value


def test_randomize(db_instance: DB) -> None:
    """Test _randomize method."""
    # pylint: disable=protected-access
    sample = ["a", "b", "c", "d", "e", "f", "g", "h"]
    # ratio is 0.25, so 8 * 0.25 = 2 items
    result = db_instance._randomize(sample)
    assert len(result) == EXPECTED_RANDOM_COUNT
    for item in result:
        assert item in sample


def test_randomize_errors(db_instance: DB) -> None:
    """Test _randomize error handling."""
    # pylint: disable=protected-access
    with pytest.raises(ValueError, match="must be a list"):
        db_instance._randomize("not a list")  # type: ignore

    with pytest.raises(ValueError, match="must not be empty"):
        db_instance._randomize([])


def test_count_track(db_instance: DB) -> None:
    """Test count_track method."""
    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    filters = {"artist": "Test"}
    db_instance.count_track(filters)

    mock_coll.count_documents.assert_called_with(filters)


def test_insert_tracks(db_instance: DB) -> None:
    """Test insert_tracks method."""
    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    tracks = [{"id": 1}, {"id": 2}]
    db_instance.insert_tracks(tracks)

    mock_coll.insert_many.assert_called_with(tracks)


def test_get_latest_playlist_uris(db_instance: DB) -> None:
    """Test get_latest_playlist_uris method."""
    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    # Mock find_one return value
    mock_coll.find_one.return_value = {"tracks": [{"uri": "uri1"}, {"uri": "uri2"}]}

    uris = db_instance.get_latest_playlist_uris()
    assert uris == ["uri1", "uri2"]

    # Test empty playlist
    mock_coll.find_one.return_value = None
    uris = db_instance.get_latest_playlist_uris()
    assert uris == []


def test_reset_collection(db_instance: DB) -> None:
    """Test reset_collection method."""
    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    db_instance.reset_collection("tracks")
    mock_coll.delete_many.assert_called_with({})

    db_instance.reset_collection("playlist")
    mock_coll.delete_many.assert_called_with({})

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


def test_get_artist_ids(db_instance: DB) -> None:
    """Test get_artist_ids method."""
    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    # Mock aggregate return value
    mock_cursor = MagicMock()
    mock_cursor.__iter__.return_value = [{"_id": "artist1"}, {"_id": "artist2"}]
    mock_coll.aggregate.return_value = mock_cursor

    ids = db_instance.get_artist_ids()
    assert ids == ["artist1", "artist2"]
    mock_coll.aggregate.assert_called_once()


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

    with patch.object(db_instance, "validate_item_count"):
        with patch.object(
            db_instance, "get_recent_playlist_uris", return_value=["uri_ex1", "uri_ex2"]
        ):
            db_instance.generate_random_playlist("track", TEST_PLAYLIST_SIZE)

            # Verify aggregate called on tracks collection
            # Note: get_tracks_coll is called, which calls mongo_db['tracks']
            # We need to ensure the mock returned by getitem is used
            mock_coll.aggregate.assert_called_once()
            pipeline = mock_coll.aggregate.call_args[0][0]

            # Verify exclusion logic
            assert pipeline[0]["$match"]["uri"]["$nin"] == ["uri_ex1", "uri_ex2"]
            assert pipeline[1]["$sample"]["size"] == TEST_PLAYLIST_SIZE
            assert pipeline[3]["$merge"]["into"] == "playlist"


def test_generate_random_playlist_artist(db_instance: DB) -> None:
    """Test generate_random_playlist with artist type."""
    mock_coll = MagicMock()
    mock_db = cast(MagicMock, db_instance.mongo_db)
    mock_db.__getitem__.return_value = mock_coll

    with patch.object(db_instance, "validate_item_count"):
        with patch.object(db_instance, "get_artist_ids", return_value=["a1", "a2", "a3", "a4"]):
            # Mock _randomize to return a subset
            with patch.object(db_instance, "_randomize", return_value=["a1", "a2"]):
                db_instance.generate_random_playlist("artist", TEST_PLAYLIST_SIZE)

                mock_coll.aggregate.assert_called_once()
                pipeline = mock_coll.aggregate.call_args[0][0]
                assert pipeline[0]["$match"]["artists._id"]["$in"] == ["a1", "a2"]
                assert pipeline[1]["$sample"]["size"] == TEST_PLAYLIST_SIZE


def test_generate_random_playlist_invalid(db_instance: DB) -> None:
    """Test generate_random_playlist with invalid type."""
    with patch.object(db_instance, "validate_item_count"):
        with pytest.raises(ValueError, match="Invalid item type"):
            db_instance.generate_random_playlist("invalid", TEST_PLAYLIST_SIZE)  # type: ignore

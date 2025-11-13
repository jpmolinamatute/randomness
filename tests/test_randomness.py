from collections.abc import Generator
from unittest.mock import ANY, MagicMock, patch

import pytest

from spotify import DB, Randomness


# pylint: disable=redefined-outer-name
@pytest.fixture
def mock_db() -> Generator[MagicMock, None, None]:
    with patch("pymongo.MongoClient") as _:
        mock_db_instance = MagicMock(spec=DB)
        mock_db_instance.mongo_db = MagicMock()
        mock_db_instance.mongo_db["tracks"] = MagicMock()
        mock_db_instance.mongo_db["playlist"] = MagicMock()
        yield mock_db_instance


def test_execute_aggregation_pipeline(mock_db: MagicMock) -> None:
    randomness = Randomness(mock_db)
    randomness.mongo_tracks_collection = mock_db.mongo_db["tracks"]

    pipeline = [{"$match": {"artists._id": {"$in": ["artist1", "artist2"]}}}]
    randomness.execute_aggregation_pipeline(pipeline)

    mock_db.mongo_db["tracks"].aggregate.assert_called_once_with(pipeline)
    mock_db.mongo_db["tracks"].aggregate.return_value.close.assert_called_once()


def test_get_artist_ids(mock_db: MagicMock) -> None:
    randomness = Randomness(mock_db)
    randomness.mongo_tracks_collection = mock_db.mongo_db["tracks"]

    mock_cursor = MagicMock()
    mock_db.mongo_db["tracks"].aggregate.return_value = mock_cursor
    mock_cursor.__iter__.return_value = [{"_id": "artist1"}, {"_id": "artist2"}]

    result = randomness.get_artist_ids()

    mock_db.mongo_db["tracks"].aggregate.assert_called_once_with(
        [
            {"$unwind": "$artists"},
            {"$group": {"_id": "$artists._id"}},
            {"$project": {"_id": 1}},
        ]
    )
    assert result == ["artist1", "artist2"]
    mock_cursor.close.assert_called_once()


def test_get_random_tracks(mock_db: MagicMock) -> None:
    randomness = Randomness(mock_db)
    randomness.mongo_tracks_collection = mock_db.mongo_db["tracks"]
    randomness.mongo_playlist_collection = mock_db.mongo_db["playlist"]

    no_items = 10
    randomness.get_random_tracks(no_items)

    expected_pipeline = [
        {"$sample": {"size": no_items}},
        {
            "$group": {
                "_id": ANY,
                "tracks": {"$push": "$$ROOT"},
                "created_at": {"$first": ANY},
            }
        },
        {"$out": mock_db.playlist_name},
    ]

    mock_db.mongo_db["tracks"].aggregate.assert_called_once_with(expected_pipeline)


def test_get_random_artists(mock_db: MagicMock) -> None:
    randomness = Randomness(mock_db)
    randomness.mongo_tracks_collection = mock_db.mongo_db["tracks"]
    randomness.mongo_playlist_collection = mock_db.mongo_db["playlist"]

    all_artists = ["artist1", "artist2", "artist3", "artist4"]
    with patch.object(randomness, "get_artist_ids", return_value=all_artists):
        with patch("random.sample", return_value=["artist1", "artist2"]):
            no_items = 10
            randomness.get_random_artists(no_items)

            expected_pipeline = [
                {"$match": {"artists._id": {"$in": ["artist1", "artist2"]}}},
                {"$sample": {"size": no_items}},
                {
                    "$group": {
                        "_id": ANY,
                        "tracks": {"$push": "$$ROOT"},
                        "created_at": {"$first": ANY},
                    }
                },
                {"$out": mock_db.playlist_name},
            ]

            mock_db.mongo_db["tracks"].aggregate.assert_called_once_with(expected_pipeline)


def test_validate_item_count(mock_db: MagicMock) -> None:
    randomness = Randomness(mock_db)
    randomness.mongo_tracks_collection = mock_db.mongo_db["tracks"]

    mock_db.count_track.return_value = 1000

    with pytest.raises(ValueError, match="Number of items must be an integer"):
        randomness.validate_item_count("10")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Number of items must be greater than 0"):
        randomness.validate_item_count(0)

    randomness.validate_item_count(10)  # Should not raise an exception


def test_generate_random_playlist(mock_db: MagicMock) -> None:
    randomness = Randomness(mock_db)
    randomness.mongo_tracks_collection = mock_db.mongo_db["tracks"]
    randomness.mongo_playlist_collection = mock_db.mongo_db["playlist"]

    with patch.object(randomness, "get_random_tracks") as mock_get_random_tracks:
        with patch.object(randomness, "get_random_artists") as mock_get_random_artists:
            with patch.object(randomness, "validate_item_count") as mock_validate_item_count:
                randomness.generate_random_playlist("track", 10)
                mock_validate_item_count.assert_called_once_with(10)
                mock_get_random_tracks.assert_called_once_with(10)

                randomness.generate_random_playlist("artist", 10)
                mock_validate_item_count.assert_called_with(10)
                mock_get_random_artists.assert_called_once_with(10)

                with pytest.raises(ValueError, match="Invalid item type"):
                    randomness.generate_random_playlist("invalid", 10)  # type: ignore[arg-type]

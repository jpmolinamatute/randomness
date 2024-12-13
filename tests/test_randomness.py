from typing import Generator
from unittest.mock import MagicMock, patch, ANY

import pytest

from src.randomness import Randomness


@pytest.fixture
def mock_mongo() -> Generator[MagicMock, None, None]:
    with patch("pymongo.MongoClient") as mock_client:
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection
        yield mock_collection


def test_run_query(mock_mongo: MagicMock) -> None:
    randomness = Randomness()
    randomness.mongo_tracks_collection = mock_mongo

    pipeline = [{"$match": {"artists._id": {"$in": ["artist1", "artist2"]}}}]
    randomness.run_query(pipeline)

    mock_mongo.aggregate.assert_called_once_with(pipeline)
    mock_mongo.aggregate.return_value.close.assert_called_once()


def test_get_artist_ids(mock_mongo: MagicMock) -> None:
    randomness = Randomness()
    randomness.mongo_tracks_collection = mock_mongo

    mock_cursor = MagicMock()
    mock_mongo.aggregate.return_value = mock_cursor
    mock_cursor.__iter__.return_value = [{"_id": "artist1"}, {"_id": "artist2"}]

    result = randomness.get_artist_ids()

    mock_mongo.aggregate.assert_called_once_with(
        [
            {"$unwind": "$artists"},
            {"$group": {"_id": "$artists._id"}},
            {"$project": {"_id": 1}},
        ]
    )
    assert result == ["artist1", "artist2"]
    mock_cursor.close.assert_called_once()


def test_get_random_track(mock_mongo: MagicMock) -> None:
    randomness = Randomness()
    randomness.mongo_tracks_collection = mock_mongo
    randomness.mongo_playlist_collection = mock_mongo

    no_items = 10
    randomness.get_random_track(no_items)

    expected_pipeline = [
        {"$sample": {"size": no_items}},
        {
            "$group": {
                "_id": ANY,
                "tracks": {"$push": "$$ROOT"},
                "created_at": {"$first": ANY},
            }
        },
        {"$out": mock_mongo.name},
    ]

    mock_mongo.aggregate.assert_called_once_with(expected_pipeline)


def test_get_random_artist(mock_mongo: MagicMock) -> None:
    randomness = Randomness()
    randomness.mongo_tracks_collection = mock_mongo
    randomness.mongo_playlist_collection = mock_mongo

    all_artists = ["artist1", "artist2", "artist3", "artist4"]
    with patch.object(randomness, "get_artist_ids", return_value=all_artists):
        with patch("random.sample", return_value=["artist1", "artist2"]):
            no_items = 10
            randomness.get_random_artist(no_items)

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
                {"$out": mock_mongo.name},
            ]

            mock_mongo.aggregate.assert_called_once_with(expected_pipeline)


def test_check_no_items(mock_mongo: MagicMock) -> None:
    randomness = Randomness()
    randomness.mongo_tracks_collection = mock_mongo

    mock_mongo.count_documents.return_value = 1000

    with pytest.raises(ValueError, match="Number of items must be an integer"):
        randomness.check_no_items("10")

    with pytest.raises(ValueError, match="Number of items must be greater than 0"):
        randomness.check_no_items(0)

    with pytest.raises(ValueError, match="Number of items must be less than 50"):
        randomness.check_no_items(51)

    randomness.check_no_items(10)  # Should not raise an exception


def test_get_random_item(mock_mongo: MagicMock) -> None:
    randomness = Randomness()
    randomness.mongo_tracks_collection = mock_mongo
    randomness.mongo_playlist_collection = mock_mongo

    with patch.object(randomness, "get_random_track") as mock_get_random_track:
        with patch.object(randomness, "get_random_artist") as mock_get_random_artist:
            with patch.object(randomness, "check_no_items") as mock_check_no_items:
                randomness.get_random_item("track", 10)
                mock_check_no_items.assert_called_once_with(10)
                mock_get_random_track.assert_called_once_with(10)

                randomness.get_random_item("artist", 10)
                mock_check_no_items.assert_called_with(10)
                mock_get_random_artist.assert_called_once_with(10)

                with pytest.raises(ValueError, match="Invalid item type"):
                    randomness.get_random_item("invalid", 10)

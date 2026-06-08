from datetime import UTC, datetime

import pytest

from spotify.schema import Album, parse_release_date


@pytest.mark.parametrize(
    "release_date_str, precision, expected",
    [
        # Matching precision
        ("2023-05-15", "day", datetime(2023, 5, 15, tzinfo=UTC)),
        ("2023-05", "month", datetime(2023, 5, 1, tzinfo=UTC)),
        ("2023", "year", datetime(2023, 1, 1, tzinfo=UTC)),
        # Precision mismatch fallback
        ("2023-05", "day", datetime(2023, 5, 1, tzinfo=UTC)),
        ("2023", "day", datetime(2023, 1, 1, tzinfo=UTC)),
        ("2023-05-15", "month", datetime(2023, 5, 15, tzinfo=UTC)),
        ("2023", "month", datetime(2023, 1, 1, tzinfo=UTC)),
        ("2023-05-15", "year", datetime(2023, 5, 15, tzinfo=UTC)),
        ("2023-05", "year", datetime(2023, 5, 1, tzinfo=UTC)),
        # Unknown/invalid precision fallback
        ("2023-05-15", "decade", datetime(2023, 5, 15, tzinfo=UTC)),
        ("2023-05", "decade", datetime(2023, 5, 1, tzinfo=UTC)),
        ("2023", "decade", datetime(2023, 1, 1, tzinfo=UTC)),
        # Leap year edge case
        ("2020-02-29", "day", datetime(2020, 2, 29, tzinfo=UTC)),
    ],
)
def test_parse_release_date_valid_parameterized(release_date_str, precision, expected):
    assert parse_release_date(release_date_str, precision) == expected


@pytest.mark.parametrize(
    "release_date_str, precision",
    [
        ("not-a-date", "day"),
        ("", "day"),
        ("2023-02-29", "day"),  # non-leap year
        ("2023-13-15", "day"),
        ("2023-05-32", "day"),
        ("2023/05/15", "day"),
        ("15-05-2023", "day"),
    ],
)
def test_parse_release_date_invalid_parameterized(release_date_str, precision):
    with pytest.raises(ValueError) as exc_info:
        parse_release_date(release_date_str, precision)
    assert f"Failed to parse release date '{release_date_str}'" in str(exc_info.value)


def test_album_validation_converts_release_date():
    album_data = {
        "album_type": "album",
        "total_tracks": 10,
        "available_markets": ["US"],
        "external_urls": {"spotify": "http://foo"},
        "href": "http://bar",
        "id": "123",
        "images": [],
        "name": "Test Album",
        "release_date": "2023-05-15",
        "release_date_precision": "day",
        "type": "album",
        "uri": "spotify:album:123",
        "artists": [],
    }
    album = Album.model_validate(album_data)
    assert album.release_date == datetime(2023, 5, 15, tzinfo=UTC)


def test_album_validation_fails_on_invalid_types():
    album_data = {
        "album_type": "album",
        "total_tracks": 10,
        "available_markets": ["US"],
        "external_urls": {"spotify": "http://foo"},
        "href": "http://bar",
        "id": "123",
        "images": [],
        "name": "Test Album",
        "release_date": 12345,  # invalid type
        "release_date_precision": "day",
        "type": "album",
        "uri": "spotify:album:123",
        "artists": [],
    }
    with pytest.raises(ValueError):
        Album.model_validate(album_data)

import pytest
from pydantic import ValidationError

from spotify.schema import Album, Artist, ItemV2, Owner, PlaylistResponse


def test_artist_type_validation():
    artist_data = {
        "artist_id": "123",
        "external_urls": {"spotify": "http://foo"},
        "href": "http://bar",
        "name": "Test Artist",
        "type": "artist",
        "uri": "spotify:artist:123",
    }
    # Valid type passes
    assert Artist.model_validate(artist_data).type == "artist"

    # Invalid type fails
    artist_data["type"] = "invalid"
    with pytest.raises(ValidationError):
        Artist.model_validate(artist_data)


def test_album_type_validation():
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
    # Valid type passes
    assert Album.model_validate(album_data).type == "album"

    # Invalid type fails
    album_data["type"] = "invalid"
    with pytest.raises(ValidationError):
        Album.model_validate(album_data)


def test_item_type_validation():
    item_data = {
        "album": {
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
        },
        "artists": [],
        "available_markets": ["US"],
        "disc_number": 1,
        "duration_ms": 1000,
        "explicit": False,
        "external_ids": {},
        "external_urls": {"spotify": "http://foo"},
        "href": "http://bar",
        "id": "123",
        "name": "Test Track",
        "popularity": 80,
        "track_number": 1,
        "type": "track",
        "uri": "spotify:track:123",
    }
    # Valid types pass
    for valid_type in ["track", "episode", "show", "audiobook"]:
        item_data["type"] = valid_type
        assert ItemV2.model_validate(item_data).type == valid_type

    # Invalid type fails
    item_data["type"] = "invalid"
    with pytest.raises(ValidationError):
        ItemV2.model_validate(item_data)


def test_owner_type_validation():
    owner_data = {
        "external_urls": {"spotify": "http://foo"},
        "href": "http://bar",
        "id": "123",
        "type": "user",
        "uri": "spotify:user:123",
    }
    # Valid type passes
    assert Owner.model_validate(owner_data).type == "user"

    # Invalid type fails
    owner_data["type"] = "invalid"
    with pytest.raises(ValidationError):
        Owner.model_validate(owner_data)


def test_playlist_response_type_validation():
    playlist_data = {
        "collaborative": False,
        "description": "Test Playlist",
        "external_urls": {"spotify": "http://foo"},
        "href": "http://bar",
        "id": "123",
        "images": [],
        "name": "Test Playlist",
        "owner": {
            "external_urls": {"spotify": "http://foo"},
            "href": "http://bar",
            "id": "123",
            "type": "user",
            "uri": "spotify:user:123",
        },
        "public": True,
        "snapshot_id": "123",
        "items": {
            "href": "http://bar",
            "limit": 100,
            "offset": 0,
            "total": 0,
            "items": [],
        },
        "type": "playlist",
        "uri": "spotify:playlist:123",
        "tracks": {
            "href": "http://bar",
            "limit": 100,
            "offset": 0,
            "total": 0,
            "items": [],
        },
        "followers": {"total": 0},
    }
    # Valid type passes
    assert PlaylistResponse.model_validate(playlist_data).type == "playlist"

    # Invalid type fails
    playlist_data["type"] = "invalid"
    with pytest.raises(ValidationError):
        PlaylistResponse.model_validate(playlist_data)

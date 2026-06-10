import pytest
from pydantic import TypeAdapter, ValidationError

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
    # Valid track passes
    assert TypeAdapter(ItemV2).validate_python(item_data).type == "track"

    # Invalid type fails
    item_data["type"] = "invalid"
    with pytest.raises(ValidationError):
        TypeAdapter(ItemV2).validate_python(item_data)


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


def test_polymorphic_item_v2_validation():
    # 1. Track Payload (has album and artists)
    track_data = {
        "id": "track_123",
        "name": "Test Track",
        "uri": "spotify:track:123",
        "href": "https://api.spotify.com/v1/tracks/123",
        "external_urls": {"spotify": "https://open.spotify.com/track/123"},
        "type": "track",
        "album": {
            "album_type": "album",
            "total_tracks": 10,
            "available_markets": ["US"],
            "external_urls": {"spotify": "http://foo"},
            "href": "http://bar",
            "id": "album_123",
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
        "popularity": 80,
        "track_number": 1,
        "is_local": False,
    }

    # 2. Episode Payload (no album or artists, contains show info)
    episode_data = {
        "id": "episode_123",
        "name": "Test Episode",
        "uri": "spotify:episode:123",
        "href": "https://api.spotify.com/v1/episodes/123",
        "external_urls": {"spotify": "https://open.spotify.com/episode/123"},
        "type": "episode",
        "description": "An episode description",
        "html_description": "<p>An episode description</p>",
        "duration_ms": 3600000,
        "explicit": False,
        "images": [],
        "is_externally_hosted": False,
        "is_playable": True,
        "languages": ["en"],
        "release_date": "2023-05-15",
        "release_date_precision": "day",
        "show": {
            "id": "show_123",
            "name": "Test Show",
            "uri": "spotify:show:123",
            "href": "https://api.spotify.com/v1/shows/123",
            "external_urls": {"spotify": "https://open.spotify.com/show/123"},
            "available_markets": ["US"],
            "copyrights": [],
            "description": "Show description",
            "html_description": "Show description",
            "explicit": False,
            "images": [],
            "languages": ["en"],
            "media_type": "audio",
            "publisher": "Test Publisher",
        },
    }

    # 3. Audiobook Payload (no album/artists, contains authors/narrators)
    audiobook_data = {
        "id": "audiobook_123",
        "name": "Test Audiobook",
        "uri": "spotify:audiobook:123",
        "href": "https://api.spotify.com/v1/audiobooks/123",
        "external_urls": {"spotify": "https://open.spotify.com/audiobook/123"},
        "type": "audiobook",
        "authors": [{"name": "Author Name"}],
        "available_markets": ["US"],
        "copyrights": [{"text": "Copyright 2026", "type": "C"}],
        "description": "Audiobook description",
        "html_description": "Audiobook description",
        "explicit": False,
        "images": [],
        "languages": ["en"],
        "media_type": "audio",
        "narrators": [{"name": "Narrator Name"}],
        "publisher": "Book Publisher",
    }

    # Validate track
    track_item = TypeAdapter(ItemV2).validate_python(track_data)
    assert track_item.type == "track"
    assert track_item.track is True

    # Validate episode
    episode_item = TypeAdapter(ItemV2).validate_python(episode_data)
    assert episode_item.type == "episode"
    assert episode_item.episode is True

    # Validate audiobook
    audiobook_item = TypeAdapter(ItemV2).validate_python(audiobook_data)
    assert audiobook_item.type == "audiobook"

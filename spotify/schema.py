from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spotify.types import ReasonType, TypeType


# Spotify response sample for GET https://api.spotify.com/v1/me/tracks requests
# {
#   "href": "https://api.spotify.com/v1/me/shows?offset=0&limit=20",
#   "limit": 20,
#   "next": "https://api.spotify.com/v1/me/shows?offset=1&limit=1",
#   "offset": 0,
#   "previous": "https://api.spotify.com/v1/me/shows?offset=1&limit=1",
#   "total": 4,
#   "items": [
#     {
#       "added_at": "string",
#       "track": {
#         "album": {
#           "album_type": "compilation",
#           "total_tracks": 9,
#           "available_markets": [
#             "CA",
#             "BR",
#             "IT"
#           ],
#           "external_urls": {
#             "spotify": "string"
#           },
#           "href": "string",
#           "id": "2up3OPMp9Tb4dAKM2erWXQ",
#           "images": [
#             {
#               "url": "https://i.scdn.co/image/ab67616d00001e02ff9ca10b55ce82ae553c8228",
#               "height": 300,
#               "width": 300
#             }
#           ],
#           "name": "string",
#           "release_date": "1981-12",
#           "release_date_precision": "year",
#           "restrictions": {
#             "reason": "market"
#           },
#           "type": "album",
#           "uri": "spotify:album:2up3OPMp9Tb4dAKM2erWXQ",
#           "artists": [
#             {
#               "external_urls": {
#                 "spotify": "string"
#               },
#               "href": "string",
#               "id": "string",
#               "name": "string",
#               "type": "artist",
#               "uri": "string"
#             }
#           ]
#         },
#         "artists": [
#           {
#             "external_urls": {
#               "spotify": "string"
#             },
#             "href": "string",
#             "id": "string",
#             "name": "string",
#             "type": "artist",
#             "uri": "string"
#           }
#         ],
#         "available_markets": [
#           "string"
#         ],
#         "disc_number": 0,
#         "duration_ms": 0,
#         "explicit": false,
#         "external_ids": {
#           "isrc": "string",
#           "ean": "string",
#           "upc": "string"
#         },
#         "external_urls": {
#           "spotify": "string"
#         },
#         "href": "string",
#         "id": "string",
#         "is_playable": false,
#         "linked_from": {},
#         "restrictions": {
#           "reason": "string"
#         },
#         "name": "string",
#         "popularity": 0,
#         "preview_url": "string",
#         "track_number": 0,
#         "type": "track",
#         "uri": "string",
#         "is_local": false
#       }
#     }
#   ]
# }


class ExternalUrls(BaseModel):
    spotify: str = Field("", description="Canonical Spotify Web API URL for this object")

    model_config = ConfigDict(title="ExternalUrls", extra="forbid")


class Image(BaseModel):
    height: int = Field(..., description="Image height in pixels")
    url: str = Field(..., description="Source URL of the image")
    width: int = Field(..., description="Image width in pixels")

    model_config = ConfigDict(title="Image", extra="forbid")


class MongoIdMixin(BaseModel):
    """Mixin to accept either 'id' or '_id' in raw payload and always expose alias '_id'."""

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_id(cls, data: Any) -> Any:
        if isinstance(data, dict) and "id" in data and "_id" not in data:
            data["_id"] = data.pop("id")
        return data


class Artist(MongoIdMixin):
    artist_id: str = Field(..., alias="_id", description="Spotify ID of the artist")
    external_urls: ExternalUrls = Field(
        ..., description="External URLs for this artist (Spotify link)"
    )
    href: str = Field(..., description="Spotify Web API endpoint for this artist")
    name: str = Field(..., description="Artist name")
    type: str = Field(..., description="Object type, should be 'artist'")
    uri: str = Field(..., description="Spotify URI for the artist")

    model_config = ConfigDict(title="Artist", extra="forbid", populate_by_name=True)

    @property
    def _id(self) -> str:
        return self.artist_id

    @_id.setter
    def _id(self, value: str) -> None:
        self.artist_id = value


class Album(MongoIdMixin):
    album_id: str = Field(..., alias="_id", description="Spotify ID of the album")
    artists: list[Artist] = Field(..., description="List of artists for the album")
    album_type: str = Field(..., description="Album type: album, single, compilation, etc.")
    available_markets: list[str] = Field(
        ..., description="ISO 3166-1 alpha-2 country codes where the album is available"
    )
    external_urls: ExternalUrls = Field(
        ..., description="External URLs for this album (Spotify link)"
    )
    is_playable: bool | None = Field(
        default=None, description="Whether the album is playable in the user's market"
    )
    href: str = Field(..., description="Spotify Web API endpoint for this album")
    images: list[Image] = Field(..., description="Cover art images in various sizes")
    name: str = Field(..., description="Album name")
    release_date: str = Field(
        ..., description="Date the album was first released (may be year, year-month, or full date)"
    )
    release_date_precision: str = Field(
        ..., description="Precision of release_date: year, month, or day"
    )
    restrictions: Restrictions | None = Field(
        None, description="Market or content restrictions for the album, if any"
    )
    total_tracks: int = Field(..., description="Total number of tracks on the album")
    type: str = Field(..., description="Object type, should be 'album'")
    uri: str = Field(..., description="Spotify URI for the album")

    model_config = ConfigDict(title="Album", extra="forbid", populate_by_name=True)

    @property
    def _id(self) -> str:
        return self.album_id

    @_id.setter
    def _id(self, value: str) -> None:
        self.album_id = value


class ExternalIds(BaseModel):
    isrc: str = Field("", description="International Standard Recording Code identifying the track")
    ean: str = Field("", description="International Article Number (if provided)")
    upc: str = Field("", description="Universal Product Code of the album or track (if provided)")

    model_config = ConfigDict(title="ExternalIds", extra="forbid")


class LinkedFrom(MongoIdMixin):
    linked_from_id: str = Field(
        ...,
        alias="_id",
        description="Original track ID this track is linked from (e.g., replaced version)",
    )
    external_urls: ExternalUrls | None = Field(
        None, description="External URLs for the original track if available"
    )
    href: str = Field(..., description="API endpoint for the original track")
    type: str = Field(..., description="Object type, should be 'track'")
    uri: str = Field(..., description="Spotify URI of the original track")

    model_config = ConfigDict(title="LinkedFrom", extra="forbid", populate_by_name=True)

    @property
    def _id(self) -> str:
        return self.linked_from_id

    @_id.setter
    def _id(self, value: str) -> None:
        self.linked_from_id = value


class Restrictions(BaseModel):
    reason: ReasonType = Field(
        ..., description="Reason for restriction: market, product, or explicit content"
    )

    model_config = ConfigDict(title="Restrictions", extra="forbid")


class Track(MongoIdMixin):
    track_id: str = Field(..., alias="_id", description="Spotify ID of the track")
    available_markets: list[str] = Field(
        ..., description="Country codes where the track can be streamed"
    )
    disc_number: int = Field(..., description="Disc number (for albums with multiple discs)")
    duration_ms: int = Field(..., description="Track length in milliseconds")
    explicit: bool = Field(..., description="True if the track has explicit lyrics/content")
    external_ids: ExternalIds = Field(
        ..., description="External identifier set for the track (ISRC, EAN, UPC)"
    )
    external_urls: ExternalUrls = Field(
        ..., description="External URLs for this track (Spotify link)"
    )
    href: str = Field(..., description="Spotify Web API endpoint for this track")
    is_playable: bool | None = Field(
        None, description="Whether the track is playable in the user's market"
    )
    restrictions: Restrictions | None = Field(
        None, description="Market or content restrictions for the track, if any"
    )
    name: str = Field(..., description="Track name")
    popularity: int = Field(..., description="Popularity (0-100) based on Spotify play metrics")
    preview_url: str | None = Field(None, description="30-second MP3 preview URL if available")
    track_number: int = Field(..., description="Position of the track on its disc")
    type: str = Field(..., description="Object type, should be 'track'")
    uri: str = Field(..., description="Spotify URI for the track")
    is_local: bool = Field(False, description="True if the track is a local file added by the user")
    album: Album = Field(..., description="Album object that the track belongs to")
    artists: list[Artist] = Field(..., description="List of artists who performed the track")
    linked_from: LinkedFrom | None = Field(
        None, description="Linking information if this track is a replacement of another"
    )
    # Some playlist endpoints include union discriminator booleans
    # alongside the track payload (e.g., { episode: false, track: true }).
    # Make them optional so we don't reject valid Spotify responses.
    episode: bool | None = Field(
        None, description="True if this payload represents an episode (playlist union flag)"
    )
    track: bool | None = Field(
        None, description="True if this payload represents a track (playlist union flag)"
    )

    model_config = ConfigDict(title="Track", extra="forbid", populate_by_name=True)

    @property
    def _id(self) -> str:
        return self.track_id

    @_id.setter
    def _id(self, value: str) -> None:
        self.track_id = value


class Followers(BaseModel):
    href: str = Field(
        ..., description="(Currently deprecated) Endpoint for followers data, often null"
    )
    total: int = Field(..., description="Total number of followers")

    model_config = ConfigDict(title="Followers", extra="forbid")


class Owner(MongoIdMixin):
    external_urls: ExternalUrls = Field(
        ..., description="External URLs for this user (Spotify link)"
    )
    followers: Followers | None = Field(None, description="Follower count data if available")
    href: str = Field(..., description="Spotify Web API endpoint for this user")
    user_id: str = Field(..., alias="_id", description="User's Spotify ID")
    type: TypeType = Field(..., description="Object type, always 'user'")
    uri: str = Field(..., description="Spotify URI for the user")
    display_name: str = Field("", description="User's display name")

    model_config = ConfigDict(title="Owner", extra="forbid", populate_by_name=True)

    @property
    def _id(self) -> str:
        return self.user_id

    @_id.setter
    def _id(self, value: str) -> None:
        self.user_id = value


class VideoThumbnail(BaseModel):
    url: str | None = Field(None, description="URL of the video thumbnail if available")

    model_config = ConfigDict(title="VideoThumbnail", extra="forbid")


class LikedTrackItem(BaseModel):
    added_at: str = Field(
        ..., description="Timestamp when the track was saved to the user's library (ISO 8601)"
    )
    track: Track = Field(..., description="Full track object for the saved item")
    # Playlist endpoints may include these optional fields on each item
    # even when we're parsing a liked-tracks response shape.
    added_by: Owner | None = Field(None, description="User who added the item to the playlist")
    is_local: bool | None = Field(
        None, description="True if the item is a local file on the user's device"
    )
    primary_color: str | None = Field(
        None, description="Primary color associated with the item artwork (if provided)"
    )
    video_thumbnail: VideoThumbnail | None = Field(
        None, description="Video thumbnail metadata for the item (if provided)"
    )

    model_config = ConfigDict(title="LikedTrackItem", extra="forbid")


class LikedTracksResponse(BaseModel):
    href: str = Field(..., description="API endpoint for this page of saved tracks")
    limit: int = Field(..., description="Maximum number of items returned per page")
    next: str | None = Field(None, description="URL to the next page of results, or null if none")
    offset: int = Field(..., description="Index of the first item returned")
    previous: str | None = Field(
        None, description="URL to the previous page of results, or null if none"
    )
    total: int = Field(..., description="Total number of saved tracks in the user's library")
    items: list[LikedTrackItem] = Field(..., description="List of saved track items")

    model_config = ConfigDict(title="LikedTracksResponse", extra="forbid", populate_by_name=True)


class Playlist(MongoIdMixin):
    collaborative: bool = Field(
        ..., description="True if the playlist is collaborative (other users can modify)"
    )
    description: str = Field(..., description="Playlist description text")
    external_urls: ExternalUrls = Field(
        ..., description="External URLs for this playlist (Spotify link)"
    )
    followers: Followers = Field(..., description="Playlist follower count data")
    href: str = Field(..., description="Spotify Web API endpoint for this playlist")
    playlist_id: str = Field(..., alias="_id", description="Spotify ID of the playlist")
    images: list[Image] = Field(..., description="Cover art images for the playlist")
    name: str = Field(..., description="Playlist name")
    owner: Owner = Field(..., description="Owner user object of the playlist")
    public: bool = Field(..., description="True if the playlist is public")
    snapshot_id: str = Field(..., description="Version identifier for the playlist's contents")
    tracks: LikedTracksResponse = Field(
        ..., description="Track listing object with pagination data"
    )
    type: TypeType = Field(..., description="Object type, always 'playlist'")
    uri: str = Field(..., description="Spotify URI for the playlist")

    model_config = ConfigDict(title="Playlist", extra="forbid", populate_by_name=True)

    @property
    def _id(self) -> str:
        return self.playlist_id

    @_id.setter
    def _id(self, value: str) -> None:
        self.playlist_id = value


class SpotifyCredentials(BaseModel):
    access_token: str = Field(..., description="OAuth access token for Spotify API")
    expires_in: float = Field(default=0.0, description="Time in seconds until the token expires")
    refresh_token: str = Field(..., description="OAuth refresh token to obtain new access tokens")
    scope: str = Field(
        default="user-library-read playlist-modify-public playlist-modify-private",
        description="Space-separated list of scopes granted to the token",
    )

    model_config = ConfigDict(title="SpotifyCredentials", extra="forbid")


class SpotifySecrets(BaseModel):
    client_id: str = Field(..., description="Spotify application client ID")
    client_secret: str = Field(..., description="Spotify application client secret")
    state: str = Field(..., description="CSRF protection state string for OAuth flow")
    code_verifier: str = Field(..., description="PKCE code verifier string for OAuth flow")
    code_challenge: str = Field(..., description="PKCE code challenge string for OAuth flow")
    model_config = ConfigDict(title="SpotifySecrets", extra="forbid")

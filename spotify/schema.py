from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

type HeadersType = dict[str, str]
type ReasonType = Literal["market", "product", "explicit"]
type ArtistType = Literal["artist"]
type AlbumType = Literal["album"]
type ItemType = Literal["track", "episode", "show", "audiobook"]
type OwnerType = Literal["user"]
type PlaylistType = Literal["playlist"]
type CopyrightType = Literal["C", "P"]


class Copyright(BaseModel):
    text: str = Field(..., description="The copyright text for this content.")
    type: CopyrightType = Field(
        ...,
        description="The type of copyright: C = the copyright, P = the sound recording (performance) copyright.",
    )
    model_config = ConfigDict(title="Copyright", extra="forbid")


class ResumePoint(BaseModel):
    fully_played: bool = Field(
        ..., description="Whether the episode has been fully played by the user."
    )
    resume_position_ms: int = Field(
        ..., description="The user's most recent position in the episode in milliseconds."
    )
    model_config = ConfigDict(title="ResumePoint", extra="forbid")


class Author(BaseModel):
    name: str = Field(..., description="The name of the author.")
    model_config = ConfigDict(title="Author", extra="forbid")


class Narrator(BaseModel):
    name: str = Field(..., description="The name of the narrator.")
    model_config = ConfigDict(title="Narrator", extra="forbid")


def parse_release_date(release_date_str: str, precision: str) -> datetime:
    """Parses Spotify release_date string into a UTC datetime object based on precision."""
    try:
        if precision == "day":
            return datetime.strptime(release_date_str, "%Y-%m-%d").replace(tzinfo=UTC)
        elif precision == "month":
            return datetime.strptime(release_date_str, "%Y-%m").replace(tzinfo=UTC)
        elif precision == "year":
            return datetime.strptime(release_date_str, "%Y").replace(tzinfo=UTC)
        else:
            raise ValueError(f"Unknown precision: {precision}")
    except ValueError as e:
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                return datetime.strptime(release_date_str, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
        raise ValueError(
            f"Failed to parse release date '{release_date_str}' with precision '{precision}'"
        ) from e


class DeletePlaylistItem(TypedDict):
    uri: str


class DeletePlaylistPayload(TypedDict):
    items: list[DeletePlaylistItem]


class AddPlaylistPayload(TypedDict):
    uris: list[str]


class SpotifyCredentials(BaseModel):
    access_token: str = Field(..., description="OAuth access token for Spotify API")
    expires_at: float = Field(default=0.0, description="Absolute timestamp when the token expires")
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


class ExternalUrls(BaseModel):
    spotify: str = Field("", description="Canonical Spotify Web API URL for this object")

    model_config = ConfigDict(title="ExternalUrls", extra="forbid")


class Image(BaseModel):
    height: int | None = Field(None, description="Image height in pixels")
    url: str = Field(..., description="Source URL of the image")
    width: int | None = Field(None, description="Image width in pixels")

    model_config = ConfigDict(title="Image", extra="forbid")


class MongoIdMixin(BaseModel):
    """Mixin to accept either 'id' or '_id' in raw payload and always expose alias '_id'."""

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _normalize_id(cls, data: dict[str, Any]) -> dict[str, Any]:
        if "id" in data and "_id" not in data:
            data["_id"] = data.pop("id")
        return data


class Artist(MongoIdMixin):
    artist_id: str = Field(..., alias="_id", description="Spotify ID of the artist")
    external_urls: ExternalUrls = Field(
        ..., description="External URLs for this artist (Spotify link)"
    )
    href: str = Field(..., description="Spotify Web API endpoint for this artist")
    name: str = Field(..., description="Artist name")
    type: ArtistType = Field(..., description="Object type, should be 'artist'")
    uri: str = Field(..., description="Spotify URI for the artist")

    model_config = ConfigDict(title="Artist", extra="forbid", populate_by_name=True)


class Album(MongoIdMixin):
    album_type: str = Field(..., description="Album type: album, single, compilation, etc.")
    total_tracks: int = Field(..., description="Total number of tracks on the album")
    available_markets: list[str] = Field(
        ..., description="ISO 3166-1 alpha-2 country codes where the album is available"
    )
    external_urls: ExternalUrls = Field(
        ..., description="External URLs for this album (Spotify link)"
    )
    href: str = Field(..., description="Spotify Web API endpoint for this album")
    id: str = Field(..., alias="_id", description="Spotify ID of the album")
    images: list[Image] = Field(..., description="Cover art images in various sizes")
    name: str = Field(..., description="Album name")
    release_date: datetime = Field(
        ...,
        description="Date the album was first released (may be year, year-month, or full date)",
    )
    release_date_precision: str = Field(
        ..., description="Precision of release_date: year, month, or day"
    )
    type: AlbumType = Field(..., description="Object type, should be 'album'")
    uri: str = Field(..., description="Spotify URI for the album")
    artists: list[Artist] = Field(..., description="List of artists for the album")
    is_playable: bool | None = Field(
        default=None, description="Whether the album is playable in the user's market"
    )

    model_config = ConfigDict(title="Album", extra="forbid", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _parse_release_date(cls, data: Any) -> Any:
        if isinstance(data, dict):
            release_date = data.get("release_date", "")
            precision = data.get("release_date_precision", "")

            # If already a datetime (e.g. loaded from DB), allow it
            if isinstance(release_date, datetime):
                return data

            # If string, require string precision and parse it
            if isinstance(release_date, str):
                if not isinstance(precision, str):
                    raise ValueError(
                        f"release_date is a string but release_date_precision is not a string (value: {precision})"
                    )
                data["release_date"] = parse_release_date(release_date, precision)
            else:
                raise ValueError(
                    f"release_date must be a datetime, date, or string (value: {release_date})"
                )
        return data


class ExternalIds(BaseModel):
    isrc: str | None = Field(
        None, description="International Standard Recording Code identifying the track"
    )
    ean: str | None = Field(None, description="International Article Number (if provided)")
    upc: str | None = Field(
        None, description="Universal Product Code of the album or track (if provided)"
    )

    model_config = ConfigDict(title="ExternalIds", extra="forbid")


class Restrictions(BaseModel):
    reason: ReasonType | None = Field(
        None, description="Reason for restriction: market, product, or explicit content"
    )

    model_config = ConfigDict(title="Restrictions", extra="forbid")


class Item(MongoIdMixin):
    album: Album = Field(..., description="Album object that the track belongs to")
    artists: list[Artist] = Field(..., description="List of artists who performed the track")
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
    id: str = Field(..., alias="_id", description="Spotify ID of the track")
    name: str = Field(..., description="Track name")
    popularity: int = Field(..., description="Popularity (0-100) based on Spotify play metrics")
    preview_url: str | None = Field(None, description="30-second MP3 preview URL if available")
    track_number: int = Field(..., description="Position of the track on its disc")
    type: ItemType = Field(
        ..., description="Object type, should be 'track', 'episode', 'show', or 'audiobook'"
    )
    uri: str = Field(..., description="Spotify URI for the track")
    is_local: bool = Field(
        default=False, description="True if the track is a local file added by the user"
    )
    is_playable: bool | None = Field(
        default=None, description="Whether the track is playable in the user's market"
    )


class SpotifyItem(MongoIdMixin):
    id: str = Field(..., alias="_id", description="Spotify ID of the item")
    name: str = Field(..., description="Name of the item")
    uri: str = Field(..., description="Spotify URI for the item")
    href: str = Field(..., description="Spotify Web API endpoint for this item")
    external_urls: ExternalUrls = Field(..., description="External URLs for this item")
    model_config = ConfigDict(populate_by_name=True)


class Track(Item):
    type: Literal["track"] = Field("track", description="Object type, should be 'track'")

    # Playlist-specific flags
    episode: Literal[False] = Field(False, description="Whether the track is an episode")
    track: Literal[True] = Field(True, description="Whether the track is a track")

    model_config = ConfigDict(title="Track", extra="forbid", populate_by_name=True)


class SimplifiedShow(SpotifyItem):
    type: Literal["show"] = Field("show", description="Object type, always 'show'")
    available_markets: list[str] = Field(
        ..., description="Country codes where the show can be played"
    )
    copyrights: list[Copyright] = Field(..., description="The copyrights for the show")
    description: str = Field(..., description="A description of the show")
    html_description: str = Field(..., description="A description of the show in HTML format")
    explicit: bool = Field(..., description="Whether the show has explicit content")
    images: list[Image] = Field(..., description="The cover art for the show in various sizes")
    is_externally_hosted: bool | None = Field(
        None, description="True if the show is hosted outside of Spotify"
    )
    languages: list[str] = Field(..., description="The languages used in the show")
    media_type: str = Field(..., description="The media type of the show")
    publisher: str = Field(..., description="The publisher of the show")
    total_episodes: int | None = Field(None, description="The total number of episodes in the show")

    model_config = ConfigDict(title="SimplifiedShow", extra="forbid", populate_by_name=True)


class Episode(SpotifyItem):
    type: Literal["episode"] = Field("episode", description="Object type, always 'episode'")
    audio_preview_url: str | None = Field(
        None, description="A URL to a 30-second preview of the episode in MP3 format"
    )
    description: str = Field(..., description="A description of the episode")
    html_description: str = Field(..., description="A description of the episode in HTML format")
    duration_ms: int = Field(..., description="The episode length in milliseconds")
    explicit: bool = Field(..., description="True if the episode has explicit content")
    images: list[Image] = Field(..., description="The cover art for the episode in various sizes")
    is_externally_hosted: bool = Field(
        ..., description="True if the episode is hosted outside of Spotify"
    )
    is_playable: bool = Field(
        ..., description="True if the episode is playable in the user's market"
    )
    languages: list[str] = Field(..., description="A list of languages used in the episode")
    release_date: datetime | str = Field(..., description="The date the episode was released")
    release_date_precision: str = Field(
        ..., description="The precision with which release_date is known"
    )
    resume_point: ResumePoint | None = Field(
        None, description="The user's most recent position in the episode"
    )
    show: SimplifiedShow = Field(..., description="The show on which the episode belongs")
    restrictions: Restrictions | None = Field(
        None, description="Why the episode is restricted, if applicable"
    )

    # Playlist-specific flags
    episode: Literal[True] = Field(True, description="Whether the track is an episode")
    track: Literal[False] = Field(False, description="Whether the track is a track")

    model_config = ConfigDict(title="Episode", extra="forbid", populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _parse_release_date(cls, data: Any) -> Any:
        if isinstance(data, dict):
            release_date = data.get("release_date")
            precision = data.get("release_date_precision")

            # If already a datetime or date (e.g. loaded from DB), allow it
            if isinstance(release_date, (datetime, date)):
                return data

            # If string, require string precision and parse it
            if isinstance(release_date, str):
                if not isinstance(precision, str):
                    raise ValueError(
                        f"release_date is a string but release_date_precision is not a string (value: {precision})"
                    )
                data["release_date"] = parse_release_date(release_date, precision)
            else:
                raise ValueError(
                    f"release_date must be a datetime, date, or string (value: {release_date})"
                )
        return data


class Show(SimplifiedShow):
    episodes: Any = Field(default=None, description="The episodes of the show")
    model_config = ConfigDict(title="Show", extra="forbid", populate_by_name=True)


class Audiobook(SpotifyItem):
    type: Literal["audiobook"] = Field("audiobook", description="Object type, always 'audiobook'")
    authors: list[Author] = Field(..., description="The authors of the audiobook")
    available_markets: list[str] = Field(
        ..., description="Country codes where the audiobook is available"
    )
    copyrights: list[Copyright] = Field(..., description="The copyrights for the audiobook")
    description: str = Field(..., description="A description of the audiobook")
    html_description: str = Field(..., description="A description of the audiobook in HTML format")
    edition: str | None = Field(None, description="The edition of the audiobook")
    explicit: bool = Field(..., description="True if the audiobook has explicit content")
    images: list[Image] = Field(..., description="The cover art for the audiobook in various sizes")
    languages: list[str] = Field(..., description="The languages used in the audiobook")
    media_type: str = Field(..., description="The media type of the audiobook")
    narrators: list[Narrator] = Field(..., description="The narrators of the audiobook")
    publisher: str = Field(..., description="The publisher of the audiobook")
    total_chapters: int | None = Field(
        None, description="The total number of chapters in the audiobook"
    )

    model_config = ConfigDict(title="Audiobook", extra="forbid", populate_by_name=True)


ItemV2 = Annotated[Track | Episode | Audiobook, Field(discriminator="type")]


class Followers(BaseModel):
    href: str | None = Field(
        None, description="A link to the Web API endpoint providing full details of the followers."
    )
    total: int = Field(..., description="The total number of followers.")

    model_config = ConfigDict(title="Followers", extra="forbid")


class Owner(MongoIdMixin):
    external_urls: ExternalUrls = Field(
        ..., description="External URLs for this user (Spotify link)"
    )
    href: str = Field(..., description="Spotify Web API endpoint for this user")
    id: str = Field(..., alias="_id", description="User's Spotify ID")
    type: OwnerType = Field(..., description="Object type, always 'user'")
    uri: str = Field(..., description="Spotify URI for the user")
    display_name: str | None = Field(None, description="User's display name")

    model_config = ConfigDict(title="Owner", extra="forbid", populate_by_name=True)


class VideoThumbnail(BaseModel):
    url: str | None = Field(None, description="URL of the video thumbnail if available")

    model_config = ConfigDict(title="VideoThumbnail", extra="forbid")


class PlaylistItem(BaseModel):
    added_at: str = Field(..., description="The date and time the track was saved.")
    added_by: Owner | None = Field(default=None, description="The user who added the track.")
    is_local: bool = Field(..., description="Whether the track is local.")
    item: ItemV2 | None = Field(default=None, description="Information about the item.")
    track: ItemV2 | None = Field(
        default=None, description="Information about the track.", deprecated=True
    )
    primary_color: str | None = Field(default=None, description="Primary color.")
    video_thumbnail: VideoThumbnail | None = Field(default=None, description="Video thumbnail.")

    model_config = ConfigDict(title="PlaylistItem", extra="forbid")


class LikedItems(BaseModel):
    added_at: str = Field(..., description="The date and time the track was saved.")
    track: ItemV2 = Field(..., description="Information about the track.")

    model_config = ConfigDict(title="LikedItems", extra="forbid")


class PlaylistItems(BaseModel):
    href: str
    limit: int
    next: str | None = None
    offset: int
    previous: str | None = None
    total: int
    items: list[PlaylistItem]

    model_config = ConfigDict(title="PlaylistItems", extra="forbid")


class LikedTracksResponse(PlaylistItems):
    items: list[LikedItems]

    model_config = ConfigDict(title="LikedTracksResponse", extra="forbid")


class PlaylistResponse(MongoIdMixin):
    collaborative: bool = Field(
        ..., description="True if the owner allows other users to modify the playlist."
    )
    description: str = Field(..., description="The playlist description.")
    external_urls: ExternalUrls = Field(..., description="Known external URLs for this playlist.")
    href: str = Field(
        ..., description="A link to the Web API endpoint providing full details of the playlist."
    )
    id: str = Field(..., alias="_id", description="The Spotify ID for the playlist.")
    images: list[Image] = Field(..., description="Images for the playlist.")
    name: str = Field(..., description="The name of the playlist.")
    owner: Owner = Field(..., description="The user who owns the playlist.")
    public: bool = Field(..., description="The playlist's public/private status.")
    snapshot_id: str = Field(..., description="The version identifier for the current playlist.")
    items: PlaylistItems = Field(..., description="The tracks of the playlist.")
    type: PlaylistType = Field(..., description="The object type: 'playlist'")
    uri: str = Field(..., description="The Spotify URI for the playlist.")
    tracks: PlaylistItems = Field(..., description="The tracks of the playlist.", deprecated=True)
    followers: Followers = Field(..., description="The number of followers of the playlist.")
    primary_color: str | None = Field(default=None, description="Primary color.")

    model_config = ConfigDict(title="PlaylistResponse", extra="forbid", populate_by_name=True)

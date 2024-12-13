from typing import Any, Literal
from pydantic import BaseModel, Field


class ExternalUrls(BaseModel):
    spotify: str = ""


class Image(BaseModel):
    height: int
    url: str
    width: int


class Artist(BaseModel):
    id: str = Field(..., alias="_id")
    external_urls: ExternalUrls
    href: str
    name: str
    type: str
    uri: str

    class Config:
        populate_by_name = True


class Album(BaseModel):
    id: str = Field(..., alias="_id")
    artists: list[Artist]
    album_type: str
    external_urls: ExternalUrls
    href: str
    images: list[Image]
    name: str
    release_date: str
    release_date_precision: str
    total_tracks: int
    type: str
    uri: str

    class Config:
        populate_by_name = True


class ExternalIds(BaseModel):
    isrc: str = ""
    ean: str = ""
    upc: str = ""


class LinkedFrom(BaseModel):
    id: str = Field(..., alias="_id")
    external_urls: ExternalUrls | None = None
    href: str
    type: str
    uri: str

    class Config:
        populate_by_name = True


class Restrictions(BaseModel):
    reason: Literal["market", "product", "explicit"]


class Track(BaseModel):
    id: str = Field(..., alias="_id")
    available_markets: list[str]
    disc_number: int
    duration_ms: int
    explicit: bool
    external_ids: ExternalIds
    external_urls: ExternalUrls
    href: str
    is_playable: bool | None = None
    restrictions: Restrictions | None = None
    name: str
    popularity: int
    preview_url: str | None = None
    track_number: int
    type: str
    uri: str
    is_local: bool = False
    album: Album
    artists: list[Artist]
    linked_from: LinkedFrom | None = None

    class Config:
        populate_by_name = True

    def to_dict(self, by_alias: bool = False) -> dict[str, Any]:
        return self.model_dump(by_alias=by_alias)


class Followers(BaseModel):
    href: str
    total: int


class Owner(BaseModel):
    external_urls: ExternalUrls
    followers: Followers | None = None
    href: str
    id: str
    type: Literal["user"]
    uri: str
    display_name: str = ""


class LikedTrackItem(BaseModel):
    added_at: str
    track: Track
    added_by: Owner | None = None
    is_local: bool = False


class LikedTracksResponse(BaseModel):
    href: str
    limit: int
    next: str | None = None
    offset: int
    previous: str | None = None
    total: int
    items: list[LikedTrackItem]

    class Config:
        populate_by_name = True


class Playlist(BaseModel):
    collaborative: bool
    description: str
    external_urls: ExternalUrls
    followers: Followers
    href: str
    id: str
    images: list[Image]
    name: str
    owner: Owner
    public: bool
    snapshot_id: str
    tracks: LikedTracksResponse
    type: Literal["playlist"]
    uri: str

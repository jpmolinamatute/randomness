import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from src.spotify.types import LikedTracksResponse


@pytest.fixture
def loaded_json() -> dict[str, Any]:
    file_path = Path(__file__).parent.joinpath("test_data/me_tracks.json")
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def test_example_json(loaded_json: dict[str, Any]) -> None:
    try:
        LikedTracksResponse(**loaded_json)
    except ValidationError as e:
        pytest.fail(f"Validation error: {e}")


def test_missing_restrictions_reason(loaded_json: dict[str, Any]) -> None:
    loaded_json["items"][0]["track"]["restrictions"]["reason"] = "string"
    with pytest.raises(ValidationError):
        LikedTracksResponse(**loaded_json)


def test_missing_linked_from_fields(loaded_json: dict[str, Any]) -> None:
    loaded_json["items"][0]["track"]["linked_from"] = {}
    with pytest.raises(ValidationError):
        LikedTracksResponse(**loaded_json)


def test_missing_added_by(loaded_json: dict[str, Any]) -> None:
    if "added_by" in loaded_json["items"][0]:
        del loaded_json["items"][0]["added_by"]
    with pytest.raises(ValidationError):
        LikedTracksResponse(**loaded_json)


def test_missing_is_local(loaded_json: dict[str, Any]) -> None:
    if "is_local" in loaded_json["items"][0]:
        del loaded_json["items"][0]["is_local"]
    with pytest.raises(ValidationError):
        LikedTracksResponse(**loaded_json)


if __name__ == "__main__":
    pytest.main()

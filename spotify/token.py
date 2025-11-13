import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, PrivateAttr


class TokenError(Exception):
    """Raised when token persistence or loading fails."""


def _default_token_path() -> Path:
    """Return a writable path for storing tokens.

    Uses XDG cache dir if available, else falls back to ~/.cache/randomness/tokens.json.
    This avoids writing into the installed package directory.
    """
    cache_dir = Path.home() / ".cache" / "randomness"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "tokens.json"


class Token(BaseModel):
    """In-memory representation of the OAuth token set.

    Persisted minimally (no scope, type) to reduce surface area; scope
    can be re-derived as needed for API calls.
    """

    access_token: str = ""
    token_expires_at: float = 0.0
    refresh_token: str = ""
    # Private attribute (sunder name) for persistence path.
    _file_path: Path = PrivateAttr(default_factory=_default_token_path)

    def load_tokens(self) -> None:
        """Load token values from disk or raise TokenError if missing/corrupt."""
        if not self._file_path.exists():
            raise TokenError("Token file not found")
        try:
            with open(self._file_path, "r", encoding="utf-8") as file:
                token_data: dict[str, Any] = json.load(file)
        except Exception as exc:  # noqa: BLE001
            raise TokenError(f"Failed reading token file: {exc}") from exc
        try:
            self.access_token = token_data["access_token"]
            self.refresh_token = token_data["refresh_token"]
            self.token_expires_at = token_data["token_expires_at"]
        except KeyError as exc:
            raise TokenError(f"Token file missing key: {exc}") from exc

    def store_tokens(self) -> None:
        """Persist current token values to disk."""
        token_data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expires_at": self.token_expires_at,
        }
        try:
            with open(self._file_path, "w", encoding="utf-8") as file:
                json.dump(token_data, file, indent=4)
        except Exception as exc:  # noqa: BLE001
            raise TokenError(f"Failed storing token file: {exc}") from exc

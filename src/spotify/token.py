import json
from pathlib import Path

from pydantic import BaseModel, Field


# Examples:
# get_access_token = {
#     "access_token": "***",
#     "token_type": "Bearer",
#     "expires_in": 3600,
#     "refresh_token": "***",
#     "scope": "user-library-read playlist-modify-private playlist-modify-public",
# }
# get_refresh_access_token = {
#     "access_token": "***",
#     "token_type": "Bearer",
#     "expires_in": 3600,
#     "refresh_token": "***",
#     "scope": (
#         "playlist-read-private user-follow-modify user-library-read user-library-modify "
#         "playlist-modify-private playlist-modify-public"
#     ),
# }


class TokenError(Exception):
    """Custom exception for Token errors."""


class Token(BaseModel):
    access_token: str = ""
    token_type: str = "Bearer"
    token_expires_at: float = 0.0
    refresh_token: str = ""
    file_path: Path = Field(default=Path(__name__).parent.joinpath("tokens.json"), exclude=True)

    def load_tokens(self) -> None:
        if self.file_path.exists():
            with open(self.file_path, "r", encoding="utf-8") as file:
                token_data = json.load(file)
                self.access_token = token_data["access_token"]
                self.refresh_token = token_data["refresh_token"]
                self.token_expires_at = token_data["token_expires_at"]
        else:
            raise TokenError("Token file not found")

    def store_tokens(self) -> None:
        token_data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expires_at": self.token_expires_at,
        }
        with open(self.file_path, "w", encoding="utf-8") as file:
            json.dump(token_data, file, indent=4)

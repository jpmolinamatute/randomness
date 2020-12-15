# pylint: disable=unused-import
import base64
from .db_oauth import OAuth
from .common import DEFAULT_DB, DEFAULT_SETTINGS, TOKEN_URL
from .client_aouth import get_access_token, save_access_token
from .client_requests import generate_playlist
from .settings import create_settings, validate_settings, load_settings


def str_to_base64(line: str) -> str:
    byte_line = line.encode("utf-8")
    encoded_line = base64.b64encode(byte_line)
    return encoded_line.decode("utf-8")

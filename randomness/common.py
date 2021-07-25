import base64
from typing import TypedDict, Optional
import tempfile
import errno


BASE_URL = "https://api.spotify.com"
TOKEN_URL = "https://accounts.spotify.com/api/token"

PLAYLIST_URL = f"{BASE_URL}/v1/me/playlists"
Track_List = list[str]
Break_Track_list = list[Track_List]
Music_Table = list[tuple[str, str, str, float, str, str, str, str]]

class SpotifyToken(TypedDict):
    access_token: str
    refresh_token: str
    expires_in: int

# Mark_Key = Literal["min_mark", "weight", "order", "max_mark"]

class Mark(TypedDict, total=False):
    min_mark: int
    weight: float
    order: int
    max_mark: Optional[int]


def str_to_base64(line: str) -> str:
    byte_line = line.encode("utf-8")
    encoded_line = base64.b64encode(byte_line)
    return encoded_line.decode("utf-8")


def isWritable(filepath: str) -> bool:
    writable = True
    try:
        testfile = tempfile.TemporaryFile(dir=filepath)
        testfile.close()
    except OSError as e:
        if e.errno == errno.EACCES:  # 13
            writable = False
        else:
            e.filename = filepath
            raise
    return writable

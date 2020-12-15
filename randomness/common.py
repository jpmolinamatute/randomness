from typing import List, Text, TypedDict
import tempfile
import errno

# DEFAULT_DB = ":memory:"
DEFAULT_DB = "sqlite.db"
DEFAULT_SETTINGS = "settings.json"
BASE_URL = "https://api.spotify.com"
TOKEN_URL = "https://accounts.spotify.com/api/token"
PLAYLIST_SIZE = 100
PLAYLIST_NAME = "A Random randomness"
PLAYLIST_URL = f"{BASE_URL}/v1/me/playlists"
Track_List = List[Text]
Break_Track_list = List[Track_List]


class SpotifyToken(TypedDict):
    access_token: Text
    refresh_token: Text
    expires_in: int


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

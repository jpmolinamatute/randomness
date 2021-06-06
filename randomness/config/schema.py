DEFAULT_CONFIG_NAME = "config.yaml"
# DEFAULT_DB = ":memory:"
DEFAULT_DB = "sqlite.db"
PLAYLIST_SIZE = 1000
PLAYLIST_NAME = "A Random randomness"
DEFAULT_WEB_PORT = 5842
DEFAULT_WEB_HOST = "localhost"
CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft/2019-09/schema",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "playlist": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string", "default": PLAYLIST_NAME},
                "size": {"type": "number", "default": PLAYLIST_SIZE, "multipleOf": 100},
            },
        },
        "user": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "id": {"type": "string", "pattern": "^[0-9a-z]+$"},
                "username": {"type": "string"},
            },
            "required": ["id"],
        },
        "server": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "port": {
                    "type": "number",
                    "default": DEFAULT_WEB_PORT,
                    "minimum": 1024,
                    "exclusiveMaximum": 65536,
                },
                "hostname": {"type": "string", "default": DEFAULT_WEB_HOST},
            },
        },
        "credentials": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "spotipy_client_id": {"type": "string", "pattern": "^[0-9a-z]+$"},
                "spotipy_client_secret": {"type": "string", "pattern": "^[0-9a-z]+$"},
            },
            "required": ["spotipy_client_id", "spotipy_client_secret"],
        },
        "security": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"secret": {"type": "string"}},
            "required": ["secret"],
        },
        "database": {
            "type": "object",
            "properties": {"filename": {"type": "string", "default": DEFAULT_DB}},
        },
    },
    "required": ["credentials", "security", "user"],
}

DEFAULT_CONFIG = {
    "playlist": {"name": PLAYLIST_NAME, "size": PLAYLIST_SIZE},
    "server": {"port": DEFAULT_WEB_PORT, "hostname": DEFAULT_WEB_HOST},
    "database": {"filename": DEFAULT_DB},
}

CONFIG_SCHEMA = {
    "$schema": "http://json-schema.org/draft/2019-09/schema",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "playlist": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string", "default": "A Random randomness"},
                "size": {"type": "number", "default": 400},
            },
        },
        "user": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"id": {"type": "string"}, "username": {"type": "string"}},
            "required": ["id"],
        },
        "server": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "port": {"type": "number", "default": 5842},
                "hostname": {"type": "string", "default": "localhost"},
            },
        },
        "credentials": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "spotipy_client_id": {"type": "string"},
                "spotipy_client_secret": {"type": "string"},
            },
            "required": ["spotipy_client_id", "spotipy_client_secret"],
        },
        "security": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"secret": {"type": "string"}},
            "required": ["secret"],
        },
    },
    "required": ["credentials", "security", "user"],
}

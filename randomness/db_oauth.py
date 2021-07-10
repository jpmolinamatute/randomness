import time
from .db import DB
from .common import SpotifyToken


class OAuth(DB):
    def __init__(self, filepath: str, row_id: str = ""):
        super().__init__("OAuth", "oauth", filepath, row_id)
        self.create_table()

    def create_table(self) -> None:
        sql = f"""
            CREATE TABLE IF NOT EXISTS {self.table}(
                id TEXT NOT NULL PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_in REAL NOT NULL
            );
        """
        self.execute(sql)

    def save_access_token(self, new_token: SpotifyToken):
        epoch = time.time()
        epoch += new_token["expires_in"]
        row = {
            "id": self.row_id,
            "access_token": new_token["access_token"],
            "refresh_token": new_token["refresh_token"],
            "expires_in": epoch,
        }
        self.insert(row, "id")

    def get_field(self, field: str):
        if field not in ["access_token", "refresh_token", "expires_in", "*"]:
            raise Exception(f"ERROR: field '{field}' is invalid")
        sql = f"""
            SELECT {field}
            FROM {self.table}
            WHERE id = ?;
        """
        row = self.execute(sql, (self.row_id,))
        return row[0][0]

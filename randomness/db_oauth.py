from .db import DB
from .common import SpotifyToken


class OAuth(DB):
    def __init__(self, filename: str, row_id: str = ""):
        super().__init__("OAuth", "oauth", filename, row_id)
        self.create_table()

    def create_table(self) -> None:
        sql = f"""
            CREATE TABLE IF NOT EXISTS {self.table}(
                id TEXT NOT NULL PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_in INTEGER NOT NULL
            );
        """
        self.execute(sql)

    def save_access_token(self, new_token: SpotifyToken):
        # @TODO: expires_in should be an ipoch time
        row = {
            "id": self.row_id,
            "access_token": new_token["access_token"],
            "refresh_token": new_token["refresh_token"],
            "expires_in": new_token["expires_in"],
        }
        self.insert(row, "id")

    def get_field(self, field: str):
        if field not in ["access_token", "refresh_token", "expires_in", "*"]:
            raise Exception("Error")
        sql = f"""
            SELECT {field}
            FROM {self.table}
            WHERE id = ?;
        """
        row = self.query(sql, (self.row_id,))
        return row[0][0]

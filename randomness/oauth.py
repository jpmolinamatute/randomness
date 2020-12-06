from randomness.db import DB


class OAuth(DB):
    def __init__(self, row_id: str = ""):
        super(OAuth, self).__init__("OAuth", "oauth", row_id)
        self.create_table()

    def create_table(self) -> None:
        sql = f"""
            CREATE TABLE IF NOT EXISTS {self.table}(
                id TEXT NOT NULL PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_in INTEGER NOT NULL,
                user_uri TEXT
            );
        """
        self.execute(sql)

    def save_access_token(self, access: str, refresh: str, expires: int):
        row = {
            "id": self.row_id,
            "access_token": access,
            "refresh_token": refresh,
            "expires_in": expires,
        }
        self.insert(row)

    def save_uri(self, uri: str):
        sql = f"""
            UPDATE {self.table}
            SET user_uri = ?
            WHERE id = ?;
        """
        self.execute(sql, (uri, self.row_id))

    def get_access_token(self):
        sql = f"""
            SELECT access_token
            FROM {self.table}
            WHERE id = ?;
        """
        row = self.query(sql, (self.row_id,))
        return row[0][0]

    def get_all(self):
        sql = f"""
            SELECT *
            FROM {self.table}
            WHERE id = ?;
        """
        row = self.query(sql, (self.row_id,))
        print(row)


if __name__ == "__main__":
    oa = OAuth()

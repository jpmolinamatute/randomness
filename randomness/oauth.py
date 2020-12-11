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
                expires_in INTEGER NOT NULL
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
        self.insert(row, "id")

    def update_access_token(self, access: str, refresh: str):
        sql_str = f"""
            UPDATE {self.table}
            SET access_token = ?, refresh_token = ?
            WHERE id = ?;
        """
        self.execute(sql_str, (access, refresh, self.row_id))

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


if __name__ == "__main__":
    oa = OAuth()

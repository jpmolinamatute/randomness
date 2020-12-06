import uuid
from typing import Dict, Text
import pkce
from randomness.db import DB


class OAuth(DB):
    def __init__(self, row_id: str = ""):
        super(OAuth, self).__init__("OAuth")
        self.table = "oauth"
        self.create_table()
        self.row_id = ""
        self.set_id(row_id)

    def create_table(self) -> None:
        sql = f"""
            CREATE TABLE IF NOT EXISTS {self.table}(
                id TEXT NOT NULL PRIMARY KEY,
                verifier TEXT NOT NULL,
                challenge TEXT NOT NULL,
                state TEXT NOT NULL,
                code TEXT,
                access_token TEXT,
                refresh_token TEXT,
                expires_in INTEGER,
                user_uri TEXT
            );
        """
        self.execute(sql)

    def insert_oauth(self, state: str, verifier: str, challenge: str):
        self.row_id = str(uuid.uuid4())
        if not isinstance(state, str) or not state:
            raise ValueError("ERROR: state param is undefined or is invalid")
        if not isinstance(verifier, str) or not verifier:
            raise ValueError("ERROR: verifier param is undefined or is invalid")
        if not isinstance(challenge, str) or not challenge:
            raise ValueError("ERROR: challenge param is undefined or is invalid")
        oauth = {
            "id": self.row_id,
            "state": state,
            "verifier": verifier,
            "challenge": challenge,
        }
        self.insert(self.table, oauth)

    def save_code(self, state: str, code: str) -> dict:
        sql = f"""
            SELECT state
            FROM {self.table}
            WHERE id = ?
            AND state = ?;
        """
        status: Dict[Text, Text] = {}
        rows = self.query(sql, (self.row_id, state))
        if len(rows) == 1:
            status["status"] = "OK"
            sql = f"""
                UPDATE {self.table}
                SET code = ?
                WHERE id = ?
            """
            self.execute(sql, (code, self.row_id))
        else:
            status["status"] = "FAILED"
        return status

    def save_access_token(self, access: str, refresh: str, expires: int):
        sql = f"""
            UPDATE {self.table}
            SET access_token = ?, refresh_token = ?, expires_in = ?
            WHERE id = ?;
        """
        self.execute(sql, (access, refresh, expires, self.row_id))

    def save_uri(self, uri: str):
        sql = f"""
            UPDATE {self.table}
            SET user_uri = ?
            WHERE id = ?;
        """
        self.execute(sql, (uri, self.row_id))

    def create_pkce(self) -> dict:
        verifier, challenge = pkce.generate_pkce_pair()
        state = str(uuid.uuid4())
        pkce_dict = {
            "state": state,
            "verifier": verifier,
            "challenge": challenge,
        }
        self.insert_oauth(state, verifier, challenge)
        return pkce_dict

    def get_verifier(self) -> str:
        sql = f"""
            SELECT verifier
            FROM {self.table}
            WHERE id = ?;
        """
        row = self.query(sql, (self.row_id,))
        return row[0][0]

    def get_code(self) -> str:
        sql = f"""
            SELECT code
            FROM {self.table}
            WHERE id = ?;
        """
        row = self.query(sql, (self.row_id,))
        return row[0][0]

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

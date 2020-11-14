import datetime
from os import path
import sqlite3
import logging
from .spotify_handler import ID_LEN

sqlite3.register_adapter(bool, int)
sqlite3.register_converter("BOOLEAN", lambda v: bool(int(v)))


def return_marks(columns: tuple) -> str:
    marks = ""
    size = len(columns)
    for i in range(size):
        if (i + 1) < size:
            marks += "?, "
        else:
            marks += "?"
    return marks


def validate_uri(uri: str) -> bool:
    valid = False
    if isinstance(uri, str):
        uri_breakdown = uri.split(":")
        valid = (
            len(uri_breakdown) == 3
            and uri_breakdown[0] == "spotify"
            and len(uri_breakdown[2]) == ID_LEN
        )
    return valid


def get_db_path(filename: str) -> str:
    file_path = ""
    if filename == "sqlite.db":
        file_path = path.realpath(__file__)
        file_path = path.dirname(file_path)
        file_path = path.join(file_path, filename)
    else:
        if path.isfile(filename):
            # file already exists
            file_path = filename
        elif path.isdir(filename):
            file_path = path.join(filename, "sqlite.db")
        else:
            tmp_dir = path.dirname(filename)
            if path.isdir(tmp_dir):
                # file doesn't exist YET
                file_path = filename

    return file_path


class DB_Handler:
    def __init__(self, filename: str = "sqlite.db"):
        db_file_name = get_db_path(filename)
        self.logger = logging.getLogger("DB_Handler")
        self.tracks_table = "tracks"
        self.control_table = "control"
        if db_file_name:
            self.conn = sqlite3.connect(
                db_file_name, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            self.__create_db()
        else:
            raise ValueError("invalid filename")

    def __insert(self, table: str, columns: tuple, values) -> int:
        col_list = ", ".join(columns)
        marks = return_marks(columns)
        sql_str = f"INSERT INTO {table} ({col_list}) VALUES({marks});"
        cursor = self.conn.cursor()
        if isinstance(values, tuple):
            cursor.execute(sql_str, values)
        elif isinstance(values, list):
            cursor.executemany(sql_str, values)
        self.conn.commit()
        lastrowid = cursor.lastrowid
        cursor.close()
        return lastrowid

    def __query(self, sql_str: str, values: tuple = ()) -> list:
        cursor = self.conn.cursor()
        cursor.execute(sql_str, values)
        self.conn.commit()
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def __execute(self, sql_str: str):
        cursor = self.conn.cursor()
        cursor.execute(sql_str)
        self.conn.commit()
        cursor.close()

    def __create_db(self):
        self.__execute("PRAGMA foreign_keys = ON;")
        self.logger.info(f"creating '{self.control_table}' table")
        control_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.control_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                active BOOLEAN NOT NULL,
                playlist_id TEXT NOT NULL,
                sync_date timestamp NOT NULL
            );
        """
        self.__execute(control_sql)

        self.logger.info(f"creating '{self.tracks_table}' table")
        tracks_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.tracks_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uri TEXT NOT NULL,
                control_id INTEGER NOT NULL,
                FOREIGN KEY (control_id) REFERENCES {self.control_table}(id) ON DELETE CASCADE
            );
        """
        self.__execute(tracks_sql)

        self.logger.info("creating 'active_tracks' view")
        view_sql = f"""
            CREATE VIEW IF NOT EXISTS active_tracks AS
            SELECT c.playlist_id, t.uri
            FROM {self.control_table} as c
            INNER JOIN {self.tracks_table} AS t ON c.id == t.control_id
            WHERE c.active == true;
        """
        self.__execute(view_sql)

    def insert_control(self, playlist_id: str) -> int:
        if isinstance(playlist_id, str):
            if len(playlist_id) != ID_LEN:
                raise ValueError("playlist_id is an invalid id")
        else:
            raise TypeError("playlist_id should be type str")
        now = datetime.datetime.now()
        self.logger.info(f"inserting one row into '{self.control_table}' table")
        return self.__insert(
            self.control_table,
            ("active", "sync_date", "playlist_id"),
            (True, now, playlist_id),
        )

    def update_other_controls(self, control_id: int):
        udate_sql = f"""
            UPDATE {self.control_table}
            SET active = ?
            WHERE id <> ?;
        """
        self.__query(udate_sql, (False, control_id))

        delete_sql = f"""
            DELETE FROM {self.control_table}
            WHERE id NOT IN (
                SELECT id
                FROM {self.control_table}
                ORDER by datetime(sync_date) DESC
                LIMIT 10
            );
        """
        self.__execute(delete_sql)

    def insert_tracks(self, uri_list: list, control_id: int):
        if isinstance(uri_list, list):
            if not uri_list:
                raise ValueError("uri_list is empty")
        else:
            raise TypeError("uri_list should be type list")
        if not isinstance(control_id, int):
            raise TypeError("control_id should be type int")

        tuple_list = []
        for uri in uri_list:
            if not validate_uri(uri):
                raise ValueError("an element within uri_list has an invalid value")
            tuple_list.append((uri, control_id))
        self.logger.info(f"Inserting {len(tuple_list)} rows into '{self.tracks_table}' table")
        self.__insert(self.tracks_table, ("uri", "control_id"), tuple_list)

    def insert_data(self, playlist_id: str, uri_list: list):
        # TODO: move param validation from insert_control & insert_tracks here
        control_id = self.insert_control(playlist_id)
        self.update_other_controls(control_id)
        self.insert_tracks(uri_list, control_id)

    def get_active_tracks(self) -> dict:
        sql = """
            SELECT *
            FROM active_tracks;
        """
        track_obj = {}
        result = self.__query(sql)
        if result:
            track_obj["empty"] = False
            track_obj["uri_list"] = []
            track_obj["playlist_id"] = result[0][0]
            for track in result:
                track_obj["uri_list"].append(track[1])
        else:
            track_obj["empty"] = True
        return track_obj

    def get_active_playlist(self) -> str:
        playlist_id = ""
        sql = f"""
            SELECT playlist_id
            FROM {self.control_table}
            WHERE active = ?;
        """
        result = self.__query(sql, (True,))
        if result:
            playlist_id = result[0][0]
        return playlist_id


# def main():
#     uri_list = [
#         "spotify:track:5j7gLuOsBOyqooruGxX4nx",
#         "spotify:track:6n7GUf2h8D2Ad2wUy5s7nE",
#         "spotify:track:3DxKCst1JPt8qw7soauFXc",
#         "spotify:track:3JkWwGgpvaoxeCpzWQjgsD",
#         "spotify:track:2EoOZnxNgtmZaD8uUmz2nD",
#         "spotify:track:5Ps9XMq4PDMDCNnp4JfYiI",
#         "spotify:track:1Yo6lvTsNozmc9Y9SA275E",
#         "spotify:track:4r7im8h2DTRPvl25YfNyIT",
#         "spotify:track:3AwLxSqo1jOOMpNsgxqRNE",
#         "spotify:track:59U79BbUFCfMuG1WreMobs",
#         "spotify:track:76DbzeOqBxq9Ly9QFcUVpS",
#         "spotify:track:6kM8Y82PvBlSdmJkK2GwDC",
#         "spotify:track:1BpV8IGf4XsRRJf4Xuui9q",
#         "spotify:track:0NhbvFZXkZPWxPcQdtVFLZ",
#         "spotify:track:7qIw4D1PcDHigDohKkLB0W",
#         "spotify:track:52TariT5sfkYzKRwdVMrRw",
#         "spotify:track:2yiZyjMEByt9sJBZWnWaDR",
#         "spotify:track:5VVwwfK6Cp9IydkhKfJUEq",
#         "spotify:track:2IiuyEpN0t9HHDA7lHULce",
#         "spotify:track:42e1QfTyPYWuoddr0ghc0i",
#         "spotify:track:5E3n459RNgTgWjuNDivIvC",
#         "spotify:track:3ubZ2SxShewBQ6Ou6R7iyX",
#         "spotify:track:6beFuzSjwhOKFZp2aqYDdY",
#         "spotify:track:0QZpnTFBUyVBI47mi9hQ9W",
#         "spotify:track:30u8QyT0kBSYO5RcZmaLl3",
#         "spotify:track:5qdEyQh67bgT8ZaXKK4oTL",
#         "spotify:track:7r3H2gCRFovBxyg5wuSc83",
#         "spotify:track:5AiNZnMDCWwujIENPj9PV9",
#         "spotify:track:5ACaBsJ0uKcQXND3EL5fjf",
#         "spotify:track:16lLDX1QkgYBtp6qeXKlE5",
#         "spotify:track:4FffdKTXm2Y9vHZdTLXOS3",
#         "spotify:track:7zB4Z0zcw06BdFjqsoFezz",
#         "spotify:track:0wz1LjDb9ZNEYwOmDJ3Q4b",
#         "spotify:track:0Umih4I7bo4JR6QOlL5TRO",
#         "spotify:track:0OLgqLesHtrUUTtylKpquM",
#         "spotify:track:4LOh25rjksSqo8BdoBFxcM",
#         "spotify:track:1nKeVUSEKs7GYZieEbgXQx",
#         "spotify:track:2PkeVPcL32LA96cK5ySC3c",
#         "spotify:track:4JGKZS7h4Qa16gOU3oNETV",
#         "spotify:track:5RfndPd7aG3Mazneoy9t8q",
#         "spotify:track:3rjgzO7cjby4Ie9bot7iDz",
#         "spotify:track:3mlMpmY8oZIBFc39D9zLbh",
#         "spotify:track:1WR1ulnniI6u3hlrSsa4DF",
#         "spotify:track:29mVc6JEoHcHrTzJGSTuz0",
#         "spotify:track:4y1LsJpmMti1PfRQV9AWWe",
#         "spotify:track:3z6yGuVXfXqZjc8n6lfey4",
#         "spotify:track:1UHlw8ZbQPiFXTMZw6vbR1",
#         "spotify:track:3d2DyIigzomibwlVgobyxO",
#         "spotify:track:05aXW2pMJp9vjm7r6eKDAR",
#         "spotify:track:3KiOh2ZtTrhwFZRWUou5I4",
#         "spotify:track:6C6y4OWK1Ki3FVF1TIonxW",
#         "spotify:track:4dessGxnKXmTbHPhVgqODq",
#         "spotify:track:1BfRdnfPYrni7zj4ANodBX",
#         "spotify:track:0u6XYVosizh8HlBHgp4DaS",
#         "spotify:track:2HXDYLKetrIFjHhHAABnoM",
#         "spotify:track:58joIltQ2utJTyxFC5wdO0",
#         "spotify:track:3Ya0nFAUvckS30VvWBR4Y5",
#         "spotify:track:7zaZlzl0XhthNwH3GQcyZ0",
#         "spotify:track:4p1BBxRAgQ6IR4VvTEYByX",
#         "spotify:track:65DBZofI0b79kfHTcWWDuU",
#         "spotify:track:4YzsfaFUzQU4JoioVbFRL8",
#         "spotify:track:38APb71mtO1yc02aiheUWW",
#         "spotify:track:1M1onXUypfzT5AlBg8a37X",
#         "spotify:track:1jgXB7ttP1dNn00ey9icOK",
#         "spotify:track:58XWGx7KNNkKneHdprcprX",
#         "spotify:track:6UAEqIEDAOViZx8OWw7eUJ",
#         "spotify:track:291rusLEyNxa0AipNVCDMS",
#         "spotify:track:1a1E9BL87DcWJ2fTtQRraj",
#         "spotify:track:5dLx9bI8DJ024tsLbLc0m0",
#         "spotify:track:4lO57zZGFcj7vSY4QhfVDq",
#         "spotify:track:5Ky9nTmn5Yp4nclVpHD12A",
#         "spotify:track:5eRo6g2COIM4OE3UEHMA4g",
#         "spotify:track:2fXKyAyPrEa24c6PJyqznF",
#         "spotify:track:56Gm94B1FFj4Ifz17ooH2j",
#         "spotify:track:6cL78NVcSHAFqnbXZhAfdg",
#         "spotify:track:3ZpWy5rBZv2aLQAldnmTsP",
#         "spotify:track:6ndF1XQNseMhJGp7wAAILs",
#         "spotify:track:21ceHLJfgyO9703AlzM4DU",
#         "spotify:track:1D34gv3OYOOEvSdpypsfw1",
#         "spotify:track:2WmbbiWfFEKsSZe6E5GeVe",
#         "spotify:track:540SK3uC90geLZkbZrnpH9",
#         "spotify:track:6yCjhDzcVIfxvTjBKhhn7P",
#         "spotify:track:1mB6WKPsJRdkbI8bMPXa2C",
#         "spotify:track:4b5G1Xu4nttP1oyTNGNsNd",
#         "spotify:track:6KWXbv1vyJjPE0piwdh9M1",
#         "spotify:track:0LVJCbY7sX3IWQz0dCzfTp",
#         "spotify:track:22LVye1sCfx8j8ZHa1ykBg",
#         "spotify:track:6NYFHVsiWzE41A4ZssbUwx",
#         "spotify:track:2rZYj2iyLp447jGT8S8Ga4",
#         "spotify:track:4faOBnhxXN8wKbnWQvpRLJ",
#         "spotify:track:1wtIIAA91MNuq9jZeUD8zP",
#         "spotify:track:6eCMKiaVLCRrXM7WTrXxHf",
#         "spotify:track:7hgICrd3gcAdJJ7vD6zWvV",
#         "spotify:track:7wnC64YPj2YH2oHYBmCzHt",
#         "spotify:track:1q3kloUtlEWKV0zDLHxzph",
#         "spotify:track:6RFC7A6GPVdJxXhYC9nTdW",
#         "spotify:track:64qrAu1kvvu1uLuI8TP5XU",
#         "spotify:track:0vNDEjxp64RsCgjSel2m2m",
#         "spotify:track:2KARQ7TnFDDor6LisS5TrQ",
#         "spotify:track:3jscTYbCI9rvbTV0AfzLlr",
#     ]
#     db = DB_Handler()
#     control_id = db.insert_control("4WYXvsvUglNXBn15L8fPoh")
#     db.update_other_controls(control_id)
#     db.insert_tracks(uri_list, control_id)
#     my_obj = db.get_active_playlist()
#     print(my_obj)
#     sys.exit(0)


# if __name__ == "__main__":
#     import sys
#     main()

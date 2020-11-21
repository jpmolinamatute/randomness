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

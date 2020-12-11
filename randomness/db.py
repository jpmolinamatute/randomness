from os import path
import sqlite3
import logging
import uuid
import tempfile
import errno

# DEFAULT_DB = ":memory:"
DEFAULT_DB = "sqlite.db"


def isWritable(filepath: str) -> bool:
    try:
        testfile = tempfile.TemporaryFile(dir=filepath)
        testfile.close()
    except OSError as e:
        if e.errno == errno.EACCES:  # 13
            return False
        e.filename = filepath
        raise
    return True


def row_to_marks(row: dict) -> str:
    marks = ""
    size = len(row)
    for i in range(size):
        if (i + 1) < size:
            marks += "?, "
        else:
            marks += "?"
    return marks


def row_to_values(row: dict) -> tuple:
    val = tuple(row.values())
    if len(val) == 1:
        val = (val[0],)

    return val


def row_to_set_values(row: dict) -> str:
    values = ""
    for item in row.keys():
        values += f"{item} = excluded.{item}, "
    return values[:-2]


def get_db_path(filename: str) -> str:
    file_path = path.realpath(__file__)
    file_path = path.dirname(file_path)
    file_path = path.join(file_path, DEFAULT_DB)
    if filename == ":memory:":
        file_path = filename
    elif isinstance(filename, str) and filename:
        if path.isfile(filename):
            # file already exists
            file_path = filename
        elif path.isdir(filename) and isWritable(filename):
            file_path = path.join(filename, DEFAULT_DB)
        else:
            name = path.dirname(filename)
            if path.isdir(name) and isWritable(name):
                # file doesn't exist YET
                file_path = filename
    return file_path


class DB:
    def __init__(self, logtag: str, table: str, row_id: str = "", filename: str = DEFAULT_DB):
        db_file_name = get_db_path(filename)
        self.logger = logging.getLogger(logtag)
        self.table = table
        self.row_id = row_id if row_id else str(uuid.uuid4())
        self.conn = sqlite3.connect(
            db_file_name, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        self.execute("PRAGMA foreign_keys = ON;")

    def insert(self, row: dict, upsert: str = "") -> int:
        marks = row_to_marks(row)
        values = row_to_values(row)
        columns = tuple(row.keys())
        cursor = self.conn.cursor()
        sql_str = f"""
            INSERT INTO {self.table} {columns}
            VALUES({marks})
        """
        if upsert:
            set_values = row_to_set_values(row)
            sql_str += f"""
                ON CONFLICT({upsert}) DO UPDATE SET {set_values};
            """
        else:
            sql_str += ";"
        cursor.execute(sql_str, values)
        self.conn.commit()
        lastrowid = cursor.lastrowid
        cursor.close()
        return lastrowid

    def execute(self, sql_str: str, values: tuple = ()) -> None:
        cursor = self.conn.cursor()
        cursor.execute(sql_str, values)
        self.conn.commit()
        cursor.close()

    def query(self, sql_str: str, values: tuple = ()) -> list:
        cursor = self.conn.cursor()
        cursor.execute(sql_str, values)
        self.conn.commit()
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def close(self) -> None:
        self.conn.close()

    def get_id(self) -> str:
        return self.row_id

    def set_id(self, oauth_id: str) -> bool:
        sql = f"""
            SELECT *
            FROM {self.table}
            WHERE id = ?;
        """
        valid = False

        row = self.query(sql, (oauth_id,))

        if row:
            self.row_id = oauth_id
            valid = True
        return valid

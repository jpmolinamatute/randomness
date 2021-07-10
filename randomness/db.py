from os import path
import sqlite3
import logging
import uuid
from typing import Sequence
from .config import load_config
from .common import isWritable


def row_to_marks(column: tuple) -> str:
    marks = ""
    size = len(column)
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


class DB:
    def __init__(self, logtag: str, table: str, filepath: str, row_id: str = ""):
        if not isWritable(filepath):
            msg = f"Settings path '{filepath}' is not writable "
            msg += "or doesn't exists. "
            msg += "Please change it and try again"
            raise Exception(msg)

        config = load_config(filepath)
        self.db_file_name = path.join(filepath, config["database"]["filename"])
        self.logger = logging.getLogger(logtag)
        self.table = table
        self.row_id = row_id if row_id else str(uuid.uuid4())
        self.logger.debug(f"Opening connection to {self.db_file_name}")
        self.conn = sqlite3.connect(
            self.db_file_name, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        self.execute("PRAGMA foreign_keys = ON;")

    def insert(self, row: dict, upsert: str = "") -> int:
        columns = tuple(row.keys())
        marks = row_to_marks(columns)
        values = row_to_values(row)
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
        self.logger.debug(f"Executing {sql_str}")
        cursor.execute(sql_str, values)
        self.conn.commit()
        lastrowid = cursor.lastrowid
        cursor.close()
        return lastrowid

    def execute(self, sql_str: str, values: tuple = ()) -> list:
        cursor = self.conn.cursor()
        self.logger.debug(f"Executing{sql_str}")
        cursor.execute(sql_str, values)
        self.conn.commit()
        rows = cursor.fetchall()
        if cursor.rowcount >= 0:
            self.logger.info(f"{cursor.rowcount} rows modified")
        elif rows:
            self.logger.info(f"{len(rows)} rows retrieved")
        cursor.close()
        return rows

    def executemany(self, sql_str: str, values: Sequence[tuple]) -> None:
        cursor = self.conn.cursor()
        self.logger.debug(f"Executing{sql_str}")
        cursor.executemany(sql_str, values)
        self.conn.commit()
        self.logger.info(f"{cursor.rowcount} rows modified")
        cursor.close()

    def close(self) -> None:
        self.logger.debug(f"Closing connection to {self.db_file_name}")
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

        row = self.execute(sql, (oauth_id,))

        if row:
            self.row_id = oauth_id
            valid = True
        return valid

    def create_table(self):
        raise NotImplementedError

    def reset_table(self) -> None:
        self.logger.debug(f"Reseting table {self.table}")
        sql = f"DROP TABLE IF EXISTS {self.table};"
        self.execute(sql)
        self.create_table()

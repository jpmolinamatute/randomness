#! /usr/bin/env python
import sys
from os import path
import logging
import sqlite3
from dotenv import load_dotenv
from shared import get_session, BASE_URL


def get_tracks(session) -> list:
    track_list = []
    headers = {"Accept": "application/json"}
    next_url = f"{BASE_URL}/v1/me/tracks?limit=50"
    logging.info("Getting new load of tracks from Spotify Library...")
    total = 0
    while next_url:
        response = session.get(next_url, headers=headers)
        response.raise_for_status()
        if response.status_code == 200:
            response_dict = response.json()
            next_url = response_dict["next"]
            for item in response_dict["items"]:
                total += 1
                track_list.append(
                    (
                        item["track"]["uri"],
                        item["track"]["name"],
                        item["track"]["album"]["name"],
                        item["track"]["artists"][0]["name"],
                    )
                )
        else:
            next_url = ""
    logging.info(f"tracks count is {total}")
    return track_list


def return_marks(columns: tuple) -> str:
    marks = ""
    size = len(columns)
    for i in range(size):
        if (i + 1) < size:
            marks += "?, "
        else:
            marks += "?"
    return marks


def insert(conn, table: str, columns: tuple, values) -> int:
    col_list = ", ".join(columns)
    marks = return_marks(columns)
    sql_str = f"INSERT INTO {table} ({col_list}) VALUES({marks});"
    cursor = conn.cursor()
    if isinstance(values, tuple):
        cursor.execute(sql_str, values)
    elif isinstance(values, list):
        cursor.executemany(sql_str, values)
    conn.commit()
    lastrowid = cursor.lastrowid
    cursor.close()
    return lastrowid


def execute(conn, sql_str: str) -> None:
    cursor = conn.cursor()
    cursor.execute(sql_str)
    conn.commit()
    cursor.close()


def create_db(conn) -> None:
    sql_str1 = """
        CREATE TABLE IF NOT EXISTS library (
            uri TEXT PRIMARY KEY,
            song TEXT NOT NULL,
            album TEXT NOT NULL,
            artist TEXT NOT NULL
        );
    """
    logging.info("creating 'library' table")
    execute(conn, sql_str1)
    sql_str2 = """
        CREATE VIEW IF NOT EXISTS duplicate AS
        SELECT artist, song, COUNT(*)
        FROM library
        GROUP BY artist, song
        HAVING COUNT(*) > 1
        ORDER BY artist;
    """
    logging.info("creating 'duplicate' view")
    execute(conn, sql_str2)


def process_data(conn, track_list: list) -> None:
    if isinstance(track_list, list):
        insert(conn, "library", ("uri", "song", "album", "artist"), track_list)


def get_connection():
    file_path = path.realpath(__file__)
    file_path = path.dirname(file_path)
    filename = path.join(file_path, "analysis.db")
    return sqlite3.connect(filename, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)


def main() -> None:
    try:
        logging.basicConfig(level=logging.INFO)
        logging.info("I just started")
        session = get_session()
        conn = get_connection()
        create_db(conn)
        all_track_list = get_tracks(session)
        process_data(conn, all_track_list)
    except Exception:
        logging.exception("I failed :-(")
        sys.exit(2)
    else:
        logging.info("Bye! :-)")
        sys.exit(0)


if __name__ == "__main__":
    load_dotenv()
    main()

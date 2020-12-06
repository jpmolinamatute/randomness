#! /usr/bin/env python
import sys
from os import environ  # , path, remove as file_remove
import logging
from typing import List, Text, Tuple, Dict
import pymongo
from dotenv import load_dotenv
from shared import get_session, BASE_URL


# import sqlite3

# Item_row = Tuple[Text, Text, Text, Text]
Item_row = Dict[Text, Text]
Item_list = List[Item_row]
Library_row = Tuple[Text, Text, int]
Library_list = List[Library_row]


def get_tracks(session) -> Item_list:
    track_list: Item_list = []
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
                song = {
                    "_id": item["track"]["uri"],
                    "name": item["track"]["name"],
                    "added_at": item["added_at"],
                    "duration_ms": item["track"]["duration_ms"],
                    "album_uri": item["track"]["album"]["uri"],
                    "album_name": item["track"]["album"]["name"],
                    "artists_uri": item["track"]["artists"][0]["uri"],
                    "artists_name": item["track"]["artists"][0]["name"],
                }

                track_list.append(song)
                # track_list.append(
                #     (
                #         item["track"]["uri"],
                #         item["track"]["name"],
                #         item["track"]["album"]["name"],
                #         item["track"]["artists"][0]["name"],
                #     )
                # )
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


def insert(conn, collection: str, values: Item_list):
    mycol = conn[collection]
    x = mycol.insert_many(values)
    length = len(x.inserted_ids)
    logging.info(f"{length} documents were inserted on collection '{collection}'")


# def insert(conn, table: str, columns: tuple, values) -> int:
#     col_list = ", ".join(columns)
#     marks = return_marks(columns)
#     sql_str = f"INSERT INTO {table} ({col_list}) VALUES({marks});"
#     cursor = conn.cursor()
#     if isinstance(values, tuple):
#         cursor.execute(sql_str, values)
#     elif isinstance(values, list):
#         cursor.executemany(sql_str, values)
#     conn.commit()
#     lastrowid = cursor.lastrowid
#     cursor.close()
#     return lastrowid


def execute(conn, sql_str: str) -> None:
    cursor = conn.cursor()
    cursor.execute(sql_str)
    conn.commit()
    cursor.close()


def query(conn, sql_str: str, values: tuple = ()) -> Library_list:
    cursor = conn.cursor()
    cursor.execute(sql_str, values)
    conn.commit()
    rows = cursor.fetchall()
    cursor.close()
    return rows


def print_summary(conn) -> None:
    sql_str = """
        SELECT *
        FROM duplicate;
    """
    logging.info("Printing Summary")
    rows = query(conn, sql_str)
    print("%-25s %-50s %5s" % ("artist", "song", "count"))
    for r in rows:
        print("%-25s %-50s %2i" % r)


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


# def process_data(conn, track_list: Item_list) -> None:
#     if isinstance(track_list, list):
#         insert(conn, "library", ("uri", "song", "album", "artist"), track_list)


# def get_connection():
#     file_path = path.realpath(__file__)
#     file_path = path.dirname(file_path)
#     filename = path.join(file_path, "analysis.db")
#     if path.isfile(filename):
#         file_remove(filename)
#     return sqlite3.connect(filename,
# detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)


def get_connection():
    user = environ["MONGO_USER"]
    word = environ["MONGO_PASS"]
    host = environ["MONGO_HOST"]
    port = environ["MONGO_PORT"]
    db = environ["MONGO_DB"]
    uri = f"mongodb://{user}:{word}@{host}:{port}/{db}"
    myclient = pymongo.MongoClient(uri)
    return myclient[db]


def main() -> None:
    try:
        logging.basicConfig(level=logging.INFO)
        logging.info("I just started")
        session = get_session()
        conn = get_connection()
        # create_db(conn)
        all_track_list = get_tracks(session)
        insert(conn, "library", all_track_list)
        # process_data(conn, all_track_list)
        # print_summary(conn)
    except Exception:
        logging.exception("I failed :-(")
        sys.exit(2)
    else:
        logging.info("Bye! :-)")
        sys.exit(0)


if __name__ == "__main__":
    load_dotenv()
    main()

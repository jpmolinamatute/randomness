from typing import TypedDict, Optional
from .db import DB
from .common import Track_List, Music_Table

Mark = TypedDict(
    "Mark",
    {
        "min-mark": int,
        "weight": float,
        "max-mark": Optional[int]
    },
    total=False,
)

class Library(DB):
    def __init__(self, filepath: str):
        super().__init__("Library", "library", filepath)
        mark1:Mark = {
            "min-mark": 0,
            "max-mark": 2,
            "weight": 0.3
        }
        mark2:Mark = {
            "min-mark": mark1["max-mark"] or 0,
            "max-mark": 7,
            "weight": 0.3
        }
        mark3:Mark = {
            "min-mark": mark2["max-mark"] or 0,
            "max-mark": 24,
            "weight": 0.25
        }
        mark4:Mark = {
            "min-mark": mark3["max-mark"] or 0,
            "weight": 0.15
        }
        self.mark_list: list[Mark] = [mark1, mark2, mark3, mark4]
        self.history_table = "history"
        self.create_table()

    def reset_table(self) -> None:
        self.logger.debug(f"Reseting table {self.table}")
        self.execute(f"DROP TABLE IF EXISTS {self.table};")
        self.create_table()

    def create_table(self) -> None:
        self.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.table}(
                uri TEXT NOT NULL PRIMARY KEY,
                name TEXT NOT NULL,
                added_at TEXT NOT NULL,
                duration_ms REAL NOT NULL,
                album_uri TEXT NOT NULL,
                album_name TEXT NOT NULL,
                artists_uri TEXT NOT NULL,
                artists_name TEXT NOT NULL
            );
        """)
        self.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.history_table}(
                uri TEXT NOT NULL PRIMARY KEY,
                count INTEGER DEFAULT 1,
                FOREIGN KEY(uri) REFERENCES {self.table}(uri)
            );
        """)

    def sample(self, limit:int, mark:Mark, old_track_list: Track_List) -> Track_List:
        func = lambda row: row[0]
        min_point = mark["min-mark"]
        max_point = mark["max-mark"] if "max-mark" in mark else None
        sub_limit = int(mark["weight"] * limit)
        not_id = ""
        for _ in old_track_list:
            not_id += "?, "
        not_id = not_id[:-2]
        sql_str = f"""
            SELECT uri
            FROM {self.table}
            WHERE artists_uri IN (
                SELECT artists_uri
                FROM {self.table}
                WHERE uri NOT IN ({not_id})
                GROUP BY artists_uri
        """

        if max_point:
            sql_str += "HAVING (COUNT(artists_uri) > ? AND COUNT(artists_uri) <= ?)"
            values = old_track_list + [min_point, max_point, sub_limit]
        else:
            sql_str += "HAVING COUNT(artists_uri) > ?"
            values = old_track_list  + [min_point, sub_limit]

        sql_str += """
            )
            ORDER BY random()
            LIMIT ?;
        """
        songs = self.execute(sql_str, tuple(values))
        return list(map(func, songs))

    def write_history(self, old_track_list: Track_List) -> None:
        sql_str = f"""
            INSERT INTO {self.history_table}(uri) VALUES(?)
            ON CONFLICT(uri) DO UPDATE SET count=count+1;
        """
        sql_track_list:list[tuple] = [(l,) for l in old_track_list]
        self.logger.info("Inserting previous tracks played")
        self.executemany(sql_str, sql_track_list)

    def clear_removed_tracks(self, track_list: Music_Table) ->None:
        not_id = ""
        sql_track_list:list[str] = []
        for t in track_list:
            not_id += "?, "
            sql_track_list.append(t[0])
        not_id = not_id[:-2]

        sql_str = f"""
            DELETE FROM {self.table}
            WHERE uri NOT IN ({not_id});
        """
        self.logger.info("Clearing removed tracks")
        self.execute(sql_str, tuple(sql_track_list))

    def write_table(self, track_list: Music_Table) -> None:
        sql_str = f"""
            INSERT OR IGNORE INTO {self.table}(uri, name, added_at, duration_ms, album_uri, album_name,
            artists_uri, artists_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        self.logger.info("Inserting new tracks")
        self.executemany(sql_str, track_list)

    def get_sample(self, limit: int, old_track_list: Track_List) -> Track_List:
        result_all: Track_List = []
        for mark in self.mark_list:
            result = self.sample(limit, mark, old_track_list)
            result_all.extend(result)
        return result_all

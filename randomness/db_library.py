from copy import deepcopy
from .db import DB
from .common import Track_List, Music_Table, Mark


def is_valid_mark_order(mark: Mark)-> bool:
    return "order" in mark and isinstance(mark["order"], int) and mark["order"] >= 0

def is_valid_mark_min(mark: Mark)-> bool:
    return "min_mark" in mark and isinstance(mark["min_mark"], int) and mark["min_mark"] >= 1

def is_valid_mark_weight(mark: Mark)-> bool:
    return "weight" in mark and isinstance(mark["weight"], float) and mark["weight"] > 0.0

class Library(DB):
    def __init__(self, filepath: str, mark_list: list[Mark]):
        super().__init__("Library", "library", filepath)
        self.add_marks(mark_list)
        self.history_table = "history"
        self.create_table()

    def add_marks(self, mark_list: list[Mark]) -> None:
        valid = False
        weight_total = 0.0
        for mark in mark_list:
            if is_valid_mark_order(mark) and is_valid_mark_min(mark) and is_valid_mark_weight(mark):
                valid = True
                weight_total += mark["weight"]

        if valid and weight_total == 1.0:
            self.mark_list = mark_list
        else:
            self.logger.warning("WARNING: Generator list is empty or invalid")
            self.mark_list = []

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
        min_point = mark["min_mark"]
        max_point = mark["max_mark"] if "max_mark" in mark else None
        sub_limit = int(mark["weight"] * limit)
        not_id = ""
        values = deepcopy(old_track_list)
        for _ in values:
            not_id += "?, "
        not_id = not_id[:-2]
        sql_str = f"""
            SELECT uri
            FROM {self.table}
            WHERE uri NOT IN ({not_id}) 
            AND artists_uri IN (
                SELECT artists_uri
                FROM {self.table}
                GROUP BY artists_uri
        """
        values.append(min_point)
        if max_point:
            sql_str += "        HAVING (COUNT(artists_uri) >= ? AND COUNT(artists_uri) < ?)"
            values.append(max_point)
        else:
            sql_str += "        HAVING COUNT(artists_uri) >= ?"

        values.append(sub_limit)
        sql_str += """
            )
            ORDER BY random()
            LIMIT ?;
        """

        songs = self.execute(sql_str, tuple(values))
        len_song = len(songs)
        if sub_limit != len_song:
            self.logger.warning(f"Mark {mark['order']} limit was {sub_limit} we got {len_song}")
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

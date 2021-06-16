from typing import TypedDict, Optional
from .db import DB
from .common import Track_List

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
            "min-mark": mark1["max-mark"],
            "max-mark": 7,
            "weight": 0.3
        }
        mark3:Mark = {
            "min-mark": mark2["max-mark"],
            "max-mark": 24,
            "weight": 0.25
        }
        mark4:Mark = {
            "min-mark": mark3["max-mark"],
            "weight": 0.15
        }
        self.mark_list: list[Mark] = [mark1, mark2, mark3, mark4]
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

    def _total(self, sql_str: str) -> int:
        result = self.query(sql_str)
        return result[0][0] if result and result[0] else 0

    def grand_total(self) -> int:
        sql_str = f"""
            SELECT COUNT(uri) AS total
            FROM {self.table};
        """
        return self._total(sql_str)

    def sample(self, limit:int, mark:Mark) -> Track_List:
        func = lambda row: row[0]
        min_point = mark["min-mark"]
        max_point = mark["max-mark"] if "max-mark" in mark else None
        sub_limit = int(mark["weight"] * limit)
        sql_str = f"""
            SELECT uri
            FROM {self.table}
            WHERE artists_uri in (
                SELECT artists_uri
                FROM {self.table}
                GROUP BY artists_uri
                HAVING COUNT(artists_uri) > {min_point}
        """
        if max_point:
            sql_str += f"""
                    AND COUNT(artists_uri) <= {max_point}
            """
        sql_str += f"""
            )
            ORDER BY random()
            LIMIT {sub_limit};
        """
        return list(map(func, self.query(sql_str)))

    def get_sample(self, limit: int) -> Track_List:
        result_all: Track_List = []
        for mark in self.mark_list:
            result = self.sample(limit, mark)
            result_all.extend(result)
        return result_all

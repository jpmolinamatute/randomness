from .db import DB
from .common import Track_List


class Library(DB):
    def __init__(self, filepath: str):
        super().__init__("Library", "library", filepath)
        self.g1_name = "G1"
        self.g2_name = "G2"
        self.g3_name = "G3"
        self.g4_name = "G4"
        self.mark1 = 2
        self.mark2 = 7
        self.mark3 = 24
        self.create_table()

    def reset_table(self) -> None:
        self.logger.debug(f"Reseting table {self.table}")
        sql = [
            f"DROP TABLE IF EXISTS {self.table};",
            f"DROP VIEW IF EXISTS {self.g1_name};",
            f"DROP VIEW IF EXISTS {self.g2_name};",
            f"DROP VIEW IF EXISTS {self.g3_name};",
            f"DROP VIEW IF EXISTS {self.g4_name};",
        ]

        for sql_str in sql:
            self.execute(sql_str)
        self.create_table()

    def create_table(self) -> None:
        sql = []
        sql.append(
            f"""
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
            """
        )
        sql.append(
            f"""
                CREATE TEMP VIEW {self.g1_name} AS
                SELECT uri
                FROM {self.table}
                WHERE artists_uri in (
                    SELECT artists_uri
                    FROM {self.table}
                    GROUP BY artists_uri
                    HAVING COUNT(artists_uri) <= {self.mark1}
                );
            """
        )
        sql.append(
            f"""
                CREATE TEMP VIEW {self.g2_name} AS
                SELECT uri
                FROM {self.table}
                WHERE artists_uri in (
                    SELECT artists_uri
                    FROM {self.table}
                    GROUP BY artists_uri
                    HAVING COUNT(artists_uri) > {self.mark1}
                    AND COUNT(artists_uri) <= {self.mark2}
                );
            """
        )
        sql.append(
            f"""
                CREATE TEMP VIEW {self.g3_name} AS
                SELECT uri
                FROM {self.table}
                WHERE artists_uri in (
                    SELECT artists_uri
                    FROM {self.table}
                    GROUP BY artists_uri
                    HAVING COUNT(artists_uri) > {self.mark2}
                    AND COUNT(artists_uri) <= {self.mark3}
                );
            """
        )
        sql.append(
            f"""
                CREATE TEMP VIEW {self.g4_name} AS
                SELECT uri
                FROM {self.table}
                WHERE artists_uri in (
                    SELECT artists_uri
                    FROM {self.table}
                    GROUP BY artists_uri
                    HAVING COUNT(artists_uri) > {self.mark3}
                );
            """
        )

        for sql_str in sql:
            self.execute(sql_str)

    def _total(self, sql_str: str) -> int:
        result = self.query(sql_str)
        return result[0][0] if result and result[0] else 0

    def grand_total(self) -> int:
        sql_str = f"""
            SELECT COUNT(uri) AS total
            FROM {self.table};
        """
        return self._total(sql_str)

    def sample(self, view:str, limit:int ) -> Track_List:
        func = lambda row: row[0]
        sql_str = f"""
            SELECT uri
            FROM {view}
            ORDER BY random()
            LIMIT {limit};
        """
        return list(map(func, self.query(sql_str)))

    def get_sample(self, limit: int) -> Track_List:
        result_all: Track_List = []
        result1 = self.sample(self.g1_name, int(limit * 0.3))
        result2 = self.sample(self.g2_name, int(limit * 0.3))
        result3 = self.sample(self.g3_name, int(limit * 0.25))
        result4 = self.sample(self.g4_name, int(limit * 0.15))
        result_all.extend(result1)
        result_all.extend(result2)
        result_all.extend(result3)
        result_all.extend(result4)
        return result_all

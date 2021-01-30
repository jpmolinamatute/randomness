from .db import DB
from .common import Track_List


class Library(DB):
    def __init__(self, filepath: str, mark1: int = 20, mark2: int = 55, mark3: int = 94):
        super().__init__("Library", "library", filepath)
        self.g1_name = "G1"
        self.g2_name = "G2"
        self.g3_name = "G3"
        self.g4_name = "G4"
        self.mark1 = mark1
        self.mark2 = mark2
        self.mark3 = mark3
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

    def g1_total(self) -> int:
        sql_str = f"""
            SELECT COUNT(uri) AS total
            FROM {self.g1_name};
        """
        return self._total(sql_str)

    def g2_total(self) -> int:
        sql_str = f"""
            SELECT COUNT(uri) AS total
            FROM {self.g2_name};
        """
        return self._total(sql_str)

    def g3_total(self) -> int:
        sql_str = f"""
            SELECT COUNT(uri) AS total
            FROM {self.g3_name};
        """
        return self._total(sql_str)

    def g4_total(self) -> int:
        sql_str = f"""
            SELECT COUNT(uri) AS total
            FROM {self.g4_name};
        """
        return self._total(sql_str)

    def _sample(self, sql_str) -> Track_List:
        func = lambda row: row[0]
        return list(map(func, self.query(sql_str)))

    def g1_sample(self, limit: int) -> Track_List:
        sql_str = f"""
            SELECT uri
            FROM {self.g1_name}
            ORDER BY random()
            LIMIT {limit};
        """
        return self._sample(sql_str)

    def g2_sample(self, limit: int) -> Track_List:
        sql_str = f"""
            SELECT uri
            FROM {self.g2_name}
            ORDER BY random()
            LIMIT {limit};
        """
        return self._sample(sql_str)

    def g3_sample(self, limit: int) -> Track_List:
        sql_str = f"""
            SELECT uri
            FROM {self.g3_name}
            ORDER BY random()
            LIMIT {limit};
        """
        return self._sample(sql_str)

    def g4_sample(self, limit: int) -> Track_List:
        sql_str = f"""
            SELECT uri
            FROM {self.g4_name}
            ORDER BY random()
            LIMIT {limit};
        """
        return self._sample(sql_str)

    def get_sample(self, limit: int) -> Track_List:
        result_all: Track_List = []
        sample_limit = int(limit / 4)
        result1 = self.g1_sample(sample_limit)
        result2 = self.g2_sample(sample_limit)
        result3 = self.g3_sample(sample_limit)
        result4 = self.g4_sample(sample_limit)
        result_all.extend(result1)
        result_all.extend(result2)
        result_all.extend(result3)
        result_all.extend(result4)
        return result_all

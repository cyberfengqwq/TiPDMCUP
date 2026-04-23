# core/services/db_service.py

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# 切换调试模式：True=DuckDB+CSV，False=MySQL
_USE_DUCKDB = os.environ.get("USE_DUCKDB", "0") == "1"

_CSV_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "output"

_TABLE_NAMES = [
    "income_sheet",
    "balance_sheet",
    "cash_flow_sheet",
    "core_performance_indicators_sheet",
]

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3307,
    "user": "python_user",
    "password": "Python@123",
    "database": "python_db",
    "charset": "utf8mb4",
}


def _build_duckdb_conn():
    import duckdb

    conn = duckdb.connect(":memory:")

    for table in _TABLE_NAMES:
        # 找所有匹配该表名的 CSV（各公司子目录 + 合并文件）
        csvs = list(_CSV_ROOT.rglob(f"*{table}.csv"))
        if not csvs:
            logger.warning(f"[DBService] 未找到 {table} 的 CSV 文件")
            continue

        # 用 UNION ALL 合并为同名视图
        parts = [f"SELECT * FROM read_csv_auto('{p}', ignore_errors=true)" for p in csvs]
        union_sql = " UNION ALL ".join(parts)
        conn.execute(f"CREATE VIEW {table} AS {union_sql}")
        logger.info(f"[DBService] 创建视图 {table}，共 {len(csvs)} 个 CSV")

    return conn


class DBService:
    def __init__(self):
        self._conn = None

    def _get_conn(self):
        if _USE_DUCKDB:
            if self._conn is None:
                self._conn = _build_duckdb_conn()
            return self._conn
        else:
            import pymysql
            import pymysql.cursors
            if self._conn is None or not self._conn.open:
                self._conn = pymysql.connect(
                    **DB_CONFIG,
                    cursorclass=pymysql.cursors.DictCursor,
                )
            return self._conn

    def execute(self, sql: str) -> list[dict]:
        conn = self._get_conn()
        try:
            if _USE_DUCKDB:
                # DuckDB 不支持部分 MySQL 方言，做简单兼容处理
                sql = _mysql_to_duckdb(sql)
                rel = conn.execute(sql)
                cols = [d[0] for d in rel.description]
                return [dict(zip(cols, row)) for row in rel.fetchall()]
            else:
                with conn.cursor() as cursor:
                    cursor.execute(sql)
                    return list(cursor.fetchall())
        except Exception as e:
            logger.error(f"[DBService] SQL执行失败: {sql}\n错误: {e}")
            raise

    def close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None


def _mysql_to_duckdb(sql: str) -> str:
    """处理常见 MySQL→DuckDB 方言差异。"""
    import re
    # 去掉反引号
    sql = sql.replace("`", '"')
    # LIMIT x,y → LIMIT y OFFSET x
    sql = re.sub(
        r"\bLIMIT\s+(\d+)\s*,\s*(\d+)",
        lambda m: f"LIMIT {m.group(2)} OFFSET {m.group(1)}",
        sql,
        flags=re.IGNORECASE,
    )
    return sql

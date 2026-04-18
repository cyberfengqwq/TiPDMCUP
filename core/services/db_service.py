# core/services/db_service.py

import logging

import pymysql
import pymysql.cursors

logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "your_password",
    "database": "finance_db",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}


class DBService:
    def __init__(self):
        self._conn = None

    def _get_conn(self):
        if self._conn is None or not self._conn.open:
            self._conn = pymysql.connect(**DB_CONFIG)
        return self._conn

    def execute(self, sql: str) -> list[dict]:
        """
        执行SQL，返回结果列表

        Args:
            sql: SQL语句

        Returns:
            list of dict，每行是一个字典
        """
        conn = self._get_conn()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                result = cursor.fetchall()
                return list(result)
        except Exception as e:
            logger.error(f"[DBService] SQL执行失败: {sql}\n错误: {e}")
            raise

    def close(self):
        if self._conn and self._conn.open:
            self._conn.close()

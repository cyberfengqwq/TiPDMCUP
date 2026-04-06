# core/pdf/exporter.py

from pathlib import Path

import pandas as pd
from pandas.core.methods.describe import DataFrame

from config.db_schema import DATABASE_SCHEMA_DICT


class SchemaExporter:
    """
    严格按照 schema 输出 CSV
    """

    @staticmethod
    def build_df(table_name: str, rows: list[dict]) -> pd.DataFrame:
        # 从官方附件中获取英文字段
        cols: list[str] = list(DATABASE_SCHEMA_DICT[table_name].keys())

# core/pdf/exporter.py

from pathlib import Path

import pandas as pd
from pandas.core.methods.describe import DataFrame

from config.db_schema import DATABASE_SCHEMA_DICT


class SchemaExporter:
    """
    严格按照 schema 输出 CSV
    """

    # 静态方法，可在外部直接调用
    @staticmethod
    def build_df(table_name: str, rows: list[dict]) -> pd.DataFrame:
        # 从官方附件中获取英文字段作为列名
        cols: list[str] = list(DATABASE_SCHEMA_DICT[table_name].keys())

        normalized: list[dict] = []
        # Loop_1: 遍历 out 字典的 value, 根据官方附件创建空白 ”答题卡“
        for r in rows:
            item = {c: pd.NA for c in cols}
            # Loop_1.1: 遍历每一行输出的 MR 指标，将 item 的 key 与标准字段对照，填充 ”答题卡“
            for k, v in r.items():
                if k in item:
                    item[k] = v
            normalized.append(item)

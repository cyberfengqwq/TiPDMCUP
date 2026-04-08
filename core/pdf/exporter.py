# core/pdf/exporter.py

from pathlib import Path

import pandas as pd

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

        # 空的字典列表，
        normalized: list[dict] = []
        # Loop_1: 遍历 out 字典的 value, 根据官方附件创建空白 ”答题卡“
        for r in rows:
            item = {c: pd.NA for c in cols}

            # Loop_1.1: 遍历每一行输出的 MR 指标，将 item 的 key 与标准字段对照，填充 ”答题卡“
            for k, v in r.items():
                if k in item:
                    item[k] = v
            normalized.append(item)
        return pd.DataFrame(normalized, columns=cols)

    @staticmethod
    def validate_strict(df: pd.DataFrame, table_name: str) -> None:
        # 官方列名
        expected: list = list(DATABASE_SCHEMA_DICT[table_name].keys())
        # 实际列名
        actual: list = list(df.columns)
        if actual != expected:
            raise ValueError(
                f"[{table_name}] schema mismatch\nexpected={expected}\nactual={actual}"
            )

    @staticmethod
    def save_csv(df: pd.DataFrame, table_name: str, out_file: str | Path) -> None:
        SchemaExporter.validate_strict(df, table_name)
        out_file = Path(out_file)

        # 自动在父目录创建文件夹
        out_file.parent.mkdir(parents=True, exist_ok=True)

        # 不要行号，"sig" 确保中文在 Excel 中正常显示
        df.to_csv(out_file, index=False, encoding="utf-8-sig")

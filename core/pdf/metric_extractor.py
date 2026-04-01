# core/pdf/normalizer.py

import re
from typing import Iterable

import pandas as pd

from core.pdf.mapper import FIELD_PATTERNS
from core.pdf.models import MetricRecord, RawTable


def _to_number(x):
    """
    将财报中 “不干净” 的数字提取出来
    """
    if x is None:
        return None
    s = str(x).strip().replace(",", "")
    if s in ("", "=", "--", "不适用", "nan", "None"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _pick_value(row: pd.Series):
    """
    从每行中提取数字
    """
    for v in row.tolist()[1:]:
        num = _to_number(v)
        if num is not None:
            return num
    return None


def extract_metric_records(
    raw_tables: Iterable[RawTable],
    stock_code: str,
    stock_abbr: str | None,
    report_period: str | None,
    report_year: str | None,
) -> list[MetricRecord]:
    """
    逐行扫描，提取科目名，提取数字，字段对比，返回 MetricRecord 对象
    """
    records: list[MetricRecord] = []

    for rt in raw_tables:
        df = rt.df.fillna("")
        for _, row in df.iterrows():
            item_text = str(row.iloc[0].strip())
            if not item_text:
                continue

            value = _pick_value(row)
            if value is None:
                continue

            for table_name, mapping in FIELD_PATTERNS.items():
                for field_key, patterns in mapping.items():
                    if any(re.search(p, item_text) for p in patterns):
                        records.append(
                            MetricRecord(
                                table_name=table_name,
                                field_key=field_key,
                                value=value,
                                report_period=report_period,
                                report_year=report_year,
                                stock_code=stock_code,
                                stock_abbr=stock_abbr,
                                confidence=0.8,
                                source_page=rt.page_no,
                                source_text=item_text,
                            )
                        )

# core/pdf/metric_extractor.py

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

    # 数字的核心清洗动作
    s = str(x).strip().replace(",", "")
    # 把这些占位符替换为 None
    if s in ("", "=", "--", "不适用", "nan", "None"):
        return None

    # try-except 防止提取的是文字备注
    try:
        return float(s)
    except ValueError:
        return None


def _pick_value(row: pd.Series) -> list[float]:
    """
    从每行中提取数字
    """
    values: list[float] = []
    # Loop_1: 遍历该行除第一列的所有单元格的内容
    for v in row.tolist()[1:]:
        # 将内容尝试洗成数字
        num = _to_number(v)
        # 只要找到靠左的数字，返回该 num，否则返回 None
        if num is not None:
            values.append(num)
    return values


def extract_metric_records(
    raw_tables: Iterable[RawTable],
    stock_code: str,
    stock_abbr: str | None,
    report_period: str | None,
    report_year: int | None,
    report_type: str | None,
    report_quarter: str | None,
) -> list[MetricRecord]:
    """
    逐行扫描 raw_table，提取科目名，提取数字，字段对比，返回 MetricRecord 对象
    """
    # 空列表，装一系列原始指标记录
    records: list[MetricRecord] = []

    # Loop_2: 遍历 raw_tables, 将 NaN 替换为 空字符串
    for rt in raw_tables:
        df = rt.df.fillna("")
        # Loop_2.1: 遍历每一行（可迭代对象），"_" 是占位符，表示索引(未使用)
        for _, row in df.iterrows():
            # 注意括号位置，strip 的作用对象为 string
            item_text = str(row.iloc[0]).strip()
            # 若没有表头，丢掉该行
            if not item_text:
                continue

            # 调用刚才写的 _pick_value() 函数
            values = _pick_value(row)
            # 若后续单元格没有金额，丢掉该行
            if not values:
                continue

            value = values[0]

            # Loop_2.1.1: 遍历 “字段匹配规则字典”，四个大表名 & 中英文字段
            matched = False
            for table_name, mapping in FIELD_PATTERNS.items():
                # Loop_2.1.1.1: 遍历 英文字段名 以及 中文对照规则（base + extra）
                for field_key, patterns in mapping.items():
                    # 与上一级循环提取的 "item_text"(表头) 对照，用正则去扫，若匹配就放入 records
                    if field_key in {"report_period", "report_year"}:
                        continue

                    if any(re.search(p, item_text) for p in patterns):
                        records.append(
                            MetricRecord(
                                table_name=table_name,
                                field_key=field_key,
                                value=value,
                                report_period=report_period,
                                report_year=report_year,
                                report_type=report_type,
                                report_quarter=report_quarter,
                                stock_code=stock_code,
                                stock_abbr=stock_abbr,
                                confidence=0.8,
                                source_page=rt.page_no,
                                source_text=item_text,
                            )
                        )
                        matched = True
                        break
                if matched:
                    break

    return records

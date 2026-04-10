# core/pdf/aggregator.py

from __future__ import annotations

import re
from typing import List, Dict, Tuple, Optional

# core/pdf/aggregator.py
from collections import defaultdict

import pandas as pd

from config.db_schema import DATABASE_SCHEMA_DICT
from core.pdf.models import MetricRecord


def merge_duplicate_rows(rows: List[Dict], key_fields: List[str]) -> List[Dict]:
    """
    合并重复行：同 key 合并为一行，优先保留非空值
    """
    merged: Dict[Tuple, Dict] = {}
    for r in rows:
        key = tuple(r.get(k) for k in key_fields)
        if key not in merged:
            merged[key] = r.copy()
            continue

        for k, v in r.items():
            if merged[key].get(k) is None or pd.isna(merged[key].get(k)):
                merged[key][k] = v
    return list(merged.values())


def _extract_role_from_source_text(source_text: Optional[str]) -> str:
    """
    source_text 中抽取 role:
    例如 metric_extractor 里写入了: "... | col=3 role=current"
    """
    if not source_text:
        return "unknown"
    m = re.search(r"role=(current|previous|yoy|qoq|unknown)", source_text)
    return m.group(1) if m else "unknown"


def _score_record(r: MetricRecord) -> Tuple[float, int, int]:
    """
    记录评分（越大越优）：
    1) confidence 主导
    2) role 偏好：current > unknown > previous > yoy/qoq
    3) 页面偏好：页码越小越优（用负页码参与排序）
    返回 tuple 可直接比较
    """
    role = _extract_role_from_source_text(r.source_text)
    role_weight_map = {
        "current": 4,
        "unknown": 3,
        "previous": 2,
        "yoy": 1,
        "qoq": 1,
    }
    role_weight = role_weight_map.get(role, 0)

    # source_page 越小越优；若 None 给很差值
    page = r.source_page if r.source_page is not None else 10**9
    page_pref = -page

    return (r.confidence, role_weight, page_pref)


def _safe_sort_rows_by_period(rows: List[Dict], table_name: str) -> List[Dict]:
    """
    若存在 report_period / report_year 列，按时间排序，保证 serial_number 稳定。
    """
    cols = DATABASE_SCHEMA_DICT[table_name]
    has_period = "report_period" in cols
    has_year = "report_year" in cols

    if not rows:
        return rows

    def key_fn(x: Dict):
        rp = x.get("report_period")
        ry = x.get("report_year")
        # report_period 优先；其次 report_year；最后原顺序靠稳定排序保证
        # 空值放最后
        rp_key = str(rp) if rp is not None and rp is not pd.NA else "9999-99-99"
        try:
            ry_key = int(ry) if ry is not None and ry is not pd.NA else 9999
        except Exception:
            ry_key = 9999
        return (rp_key if has_period else "9999-99-99", ry_key if has_year else 9999)

    return sorted(rows, key=key_fn)


def metric_records_to_rows(
    records: List[MetricRecord],
) -> Dict[str, List[Dict[str, object]]]:
    """把 MetricRecord 聚合成四张表的 row（dict 列表）

    Arg:
        records (List[MetricRecord]) : metric_extract 中返回的列表，其中有数个 MeticRecord 类

    Return:
        Dict[str, List[Dict]] : key 是目标表名，value 是一行一行的 CSV 数据
    """
    # 过滤无效记录
    valid_records = [r for r in records if r.stock_code and r.report_period]
    
    # 按表名、股票代码、报告期分组
    grouped: Dict[Tuple[str, str, str], List[MetricRecord]] = defaultdict(list)
    for r in valid_records:
        key = (
            r.table_name,
            r.stock_code,
            r.report_period,
        )
        grouped[key].append(r)

    # 最终输出结果
    out: Dict[str, List[Dict]] = {
        "core_performance_indicators_sheet": [],
        "balance_sheet": [],
        "income_sheet": [],
        "cash_flow_sheet": [],
    }

    # 处理每个分组
    for (table_name, stock_code, report_period), recs in grouped.items():
        # 取出表中应有的“标准英文名”到一个列表当中，即对应的 key
        schema_cols: List[str] = list(DATABASE_SCHEMA_DICT[table_name].keys())
        row: Dict[str, object] = {c: pd.NA for c in schema_cols}

        # 填充基本信息
        if "stock_code" in row:
            row["stock_code"] = stock_code
        if "stock_abbr" in row and recs:
            row["stock_abbr"] = recs[0].stock_abbr
        if "report_period" in row:
            row["report_period"] = report_period
        if "report_year" in row and recs:
            row["report_year"] = recs[0].report_year

        # 选择每个字段的最佳值
        best_by_field: Dict[str, MetricRecord] = {}
        for r in recs:
            if r.field_key not in row:
                continue
            old = best_by_field.get(r.field_key)
            if old is None or _score_record(r) > _score_record(old):
                best_by_field[r.field_key] = r

        # 填充最佳值
        for fk, best_mr in best_by_field.items():
            row[fk] = best_mr.value

        out[table_name].append(row)

    # 合并重复行并补充序号
    for t_name, rows in out.items():
        # 使用股票代码和报告期作为合并键
        rows_merged = merge_duplicate_rows(
            rows,
            key_fields=[
                "stock_code",
                "report_period",
            ],
        )
        # 按报告期排序
        rows_sorted = _safe_sort_rows_by_period(rows_merged, t_name)
        out[t_name] = rows_sorted
        
        # 补充序号
        if "serial_number" in DATABASE_SCHEMA_DICT[t_name]:
            for i, r in enumerate(out[t_name], start=1):
                r["serial_number"] = i
    return out

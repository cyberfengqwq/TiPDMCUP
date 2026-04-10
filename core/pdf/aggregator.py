# core/pdf/aggregator.py

from __future__ import annotations

import re

# core/pdf/aggregator.py
from collections import defaultdict

import pandas as pd

from config.db_schema import DATABASE_SCHEMA_DICT
from core.pdf.models import MetricRecord


def merge_duplicate_rows(rows: list[dict], key_fields: list[str]) -> list[dict]:
    """
    合并重复行：同 key 合并为一行，优先保留非空值
    """
    merged: dict[tuple, dict] = {}
    for r in rows:
        key = tuple(r.get(k) for k in key_fields)
        if key not in merged:
            merged[key] = r.copy()
            continue

        for k, v in r.items():
            if merged[key].get(k) is None or pd.isna(merged[key].get(k)):
                merged[key][k] = v
    return list(merged.values())


def _extract_role_from_source_text(source_text: str | None) -> str:
    """
    source_text 中抽取 role:
    例如 metric_extractor 里写入了: "... | col=3 role=current"
    """
    if not source_text:
        return "unknown"
    m = re.search(r"role=(current|previous|yoy|qoq|unknown)", source_text)
    return m.group(1) if m else "unknown"


def _score_record(r: MetricRecord) -> tuple[float, int, int]:
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


def _safe_sort_rows_by_period(rows: list[dict], table_name: str) -> list[dict]:
    """
    若存在 report_period / report_year 列，按时间排序，保证 serial_number 稳定。
    """
    cols = DATABASE_SCHEMA_DICT[table_name]
    has_period = "report_period" in cols
    has_year = "report_year" in cols

    if not rows:
        return rows

    def key_fn(x: dict):
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
    records: list[MetricRecord],
) -> dict[str, list[dict[str, object]]]:
    """把 MetricRecord 聚合成四张表的 row（dict 列表）

    Arg:
        records (list[MetirRecord]) : metric_extract 中返回的列表，其中有数个 MeticRecord 类

    Return:
        dict[str, list[dict]] : key 是目标表名，value 是一行一行的 CSV 数据
    """
    # 如果下方的 key 对应的 value (list[MetricRecord]) 不存在，系统自动生成空列表
    # 等待填充选拔好的 MR 指标对象 和 他的归属
    grouped: dict[tuple, list[MetricRecord]] = defaultdict(list)

    # Loop_1: 遍历 MR 对象，根据字段创建空列表，等待后续填充
    for r in records:
        key = (
            r.table_name,
            r.stock_code,
            r.report_period,
            r.report_year,
            r.report_quarter,
        )
        grouped[key].append(r)

    # 最终输出结果
    out: dict[str, list[dict]] = {
        "core_performance_indicators_sheet": [],
        "balance_sheet": [],
        "income_sheet": [],
        "cash_flow_sheet": [],
    }

    # Loop_2: 遍历 grouped 中分好的数据拿出来，recs 是指多个 MetricRecord 对象
    for (
        table_name,
        stock_code,
        report_period,
        report_year,
        report_quarter,
    ), recs in grouped.items():
        # 取出表中应有的“标准英文名”到一个列表当中，即对应的 key
        schema_cols: list[str] = list(DATABASE_SCHEMA_DICT[table_name].keys())
        """
        将所有“标准英文名”作为 key, 同时利用扁平化处理自动分配 “空白” 的 None 值;
        每次遍历都有一个 row, 利用 table_name 对应四大目标表格之一
        """
        row: dict[str, object] = {c: pd.NA for c in schema_cols}

        # 开始根据 Loop_2 遍历传的变量，替换 None 值
        if "stock_code" in row:
            row["stock_code"] = stock_code
        if "stock_abbr" in row:
            row["stock_abbr"] = recs[0].stock_abbr
        if "report_period" in row:
            row["report_period"] = report_period
        if "report_year" in row:
            row["report_year"] = report_year

        # 新建临时字典，选拔相同字段中 confidence 最高的
        best_by_field: dict[str, MetricRecord] = {}
        # Loop_2.1: 开始遍历 (选拔) 数个 MetricRecord 对象
        for r in recs:
            # 开始比对，如果该字段不在空白的 row 中，跳过该 MR 对象
            if r.field_key not in row:
                continue

            old = best_by_field.get(r.field_key)
            if old is None or _score_record(r) > _score_record(old):
                """
                若遍历到的 r 之前没有存在 best_by_field 或
                当前对象的置信度（r.confidence）高于旧对象
                """
                # 完成去重，保留置信度更高的对象
                best_by_field[r.field_key] = r

        # Loop_2.2: 把 best_by_field 中选拔出来的 "字段" 和 MR 对象 放入 row（fk == field_key，字段）
        for fk, best_mr in best_by_field.items():
            # 对比字段，填充置信度最高的 MR 对象
            row[fk] = best_mr.value

        # 调试：中间层保留季度信息（不写入CSV schema, piprlinr 会 pop 掉）
        row["_report_quarter"] = report_quarter

        out[table_name].append(row)

    # Loop_3: 合并重复行并补充序号，保证存进 MySQL 时有唯一主键
    for t_name, rows in out.items():
        rows_merged = merge_duplicate_rows(
            rows,
            key_fields=[
                "stock_code",
                "report_year",
                "report_period",
                "_report_quarter",
            ],
        )
        rows_sorted = _safe_sort_rows_by_period(rows_merged, t_name)
        out[t_name] = rows_sorted

        if "serial_number" in DATABASE_SCHEMA_DICT[t_name]:
            for i, r in enumerate(out[t_name], start=1):
                r["serial_number"] = i
    return out

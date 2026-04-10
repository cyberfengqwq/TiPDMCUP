# core/pdf/metric_extractor.py

import re
from typing import Iterable

import pandas as pd

from core.pdf.mapper import FIELD_PATTERNS, MANUAL_ALIASES
from core.pdf.models import MetricRecord, RawTable


def _to_number(x):
    """
    将财报中 “不干净” 的数字提取出来
    - 逗号分隔
    - 括号负数
    - 百分号
    """
    if x is None:
        return None

    # 数字的核心清洗动作
    s = str(x).strip().replace(",", "").replace("，", "")
    # 把这些占位符替换为 None
    if s in ("", "=", "--", "不适用", "nan", "None", "N/A", "n/a", "—", "-"):
        return None

    # 括号 -> 负数
    neg = False
    if re.fullmatch(r"\(.*\)", s):
        s = s[1:-1].strip()
        neg = True

    # 去百分号
    if s.endswith("%"):
        s = s[:-1].strip()

    # try-except 防止提取的是文字备注
    try:
        val = float(s)
        return -val if neg else val
    except ValueError:
        return None


def _normalize_text(x) -> str:
    """
    把 净 利 润 强行压缩成 净利润，极大提升字典的命中率
    """
    if x is None:
        return ""
    s = str(x).strip()
    s = s.replace("\u3000", " ")
    s = re.sub(r"\s+", "", s)
    return s


def _is_header_like_row(row: pd.Series) -> bool:
    """
    判断是否像表头行：
    常见关键词：项目、本期、上期、期末、期初、同比、环比、附注...
    """
    txt = "".join(_normalize_text(v) for v in row.tolist())
    if not txt:
        return False

    header_keywords = [
        "项目",
        "科目",
        "附注",
        "本期",
        "上期",
        "本年",
        "上年",
        "期末",
        "期初",
        "年末",
        "年初",
        "同比",
        "环比",
        "本报告期",
        "上年同期",
    ]
    return any(k in txt for k in header_keywords)


def _build_column_roles(df: pd.DataFrame) -> dict[int, str]:
    """
    扫描前几行，推断每一列角色
    current / previous / yoy / qoq / unknown

    Arg:
        df (pd.DataFrame)

    Return:

    """
    roles: dict[int, str] = {i: "unknown" for i in range(len(df.columns))}

    if df.empty:
        return roles

    scan_rows = min(3, len(df))
    for r in range(scan_rows):
        row = df.iloc[r]
        for i, v in enumerate(row.tolist()):
            t = _normalize_text(v)
            if not t:
                continue

            if re.search(r"(本期|本年|当期|本报告期|期末|年末)", t):
                roles[i] = "current"
            elif re.search(r"(上期|上年|同期|期初|年初)", t):
                if roles[i] == "unknown":
                    roles[i] = "previous"
            elif "同比" in t:
                roles[i] = "yoy"
            elif "环比" in t:
                roles[i] = "qoq"

    return roles


def _pick_value_with_role(row: pd.Series, col_roles: dict[int, str]):
    """
    从一行中选数值：
    1) 优先 current
    2) 再 previous
    3) 最后任意第一个可转数字
    返回固定三元组: (value, role, col_idx)
    """
    values = row.tolist()
    candidate_indices = list(range(1, len(values)))  # 跳过第0列科目名

    # 先 current
    for i in candidate_indices:
        if col_roles.get(i) == "current":
            num = _to_number(values[i])
            if num is not None:
                return num, "current", i

    # 再 previous
    for i in candidate_indices:
        if col_roles.get(i) == "previous":
            num = _to_number(values[i])
            if num is not None:
                return num, "previous", i

    # 最后兜底
    for i in candidate_indices:
        num = _to_number(values[i])
        if num is not None:
            return num, col_roles.get(i, "unknown"), i

    # 没找到数字也要返回三元组，避免 unpack 报错
    return None, "unknown", -1


def _get_pattern_confidence(
    table_name: str,
    field_key: str,
    pattern: str,
    item_text: str,
) -> float:
    """
    动态置信度：
    - 精确命中官方标签：0.95
    - alias命中：0.85
    - 其他正则命中：0.75
    """
    try:
        if re.fullmatch(pattern, item_text):
            return 0.95
    except re.error:
        pass

    aliases = MANUAL_ALIASES.get((table_name, field_key), [])
    if pattern in aliases:
        return 0.85

    return 0.75


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
    records: list[MetricRecord] = []

    for rt in raw_tables:
        df = rt.df.fillna("")
        if df.empty:
            continue

        # 识别列角色（本期/上期）
        col_roles = _build_column_roles(df)

        # 若前几行像表头，行遍历时自动跳过
        for _, row in df.iterrows():
            # 跳过明显表头行
            if _is_header_like_row(row):
                continue

            item_text_raw = row.iloc[0]
            item_text = _normalize_text(item_text_raw)

            # 若没有科目名，丢掉该行
            if not item_text:
                continue

            value, picked_role, picked_col = _pick_value_with_role(row, col_roles)
            if value is None:
                continue

            # 用于去重：同一table + field + source_text，只保留最高置信度
            best_local: dict[tuple[str, str, str], MetricRecord] = {}

            for table_name, mapping in FIELD_PATTERNS.items():
                for field_key, patterns in mapping.items():
                    if field_key in {"report_period", "report_year", "serial_number"}:
                        continue

                    matched = False
                    best_conf = 0.0

                    for p in patterns:
                        try:
                            if re.search(p, item_text):
                                matched = True
                                conf = _get_pattern_confidence(
                                    table_name, field_key, p, item_text
                                )
                                if conf > best_conf:
                                    best_conf = conf
                        except re.error:
                            continue

                    if not matched:
                        continue

                    # 列角色微调置信度：current +0.03，previous -0.02
                    if picked_role == "current":
                        best_conf += 0.03
                    elif picked_role == "previous":
                        best_conf -= 0.02

                    # clamp
                    best_conf = max(0.0, min(0.99, best_conf))

                    mr = MetricRecord(
                        table_name=table_name,
                        field_key=field_key,
                        value=value,
                        report_period=report_period,
                        report_year=report_year,
                        report_type=report_type,
                        report_quarter=report_quarter,
                        stock_code=stock_code,
                        stock_abbr=stock_abbr,
                        confidence=best_conf,
                        source_page=rt.page_no,
                        source_text=f"{item_text_raw} | col={picked_col} role={picked_role}",
                    )

                    key = (table_name, field_key, item_text)
                    old = best_local.get(key)
                    if old is None or mr.confidence > old.confidence:
                        best_local[key] = mr

            records.extend(best_local.values())

    return records

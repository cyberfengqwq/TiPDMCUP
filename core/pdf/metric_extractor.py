# core/pdf/metric_extractor.py

import re
from typing import Iterable, Optional, List, Dict, Tuple

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


def _find_label_cell(row: pd.Series) -> tuple[str, int]:
    """
    找到该行的“科目/项目”文本所在列。
    默认只在前3列里找非空且非纯数字的文本。
    """
    values = row.tolist()
    max_scan = min(3, len(values))
    for i in range(max_scan):
        raw = values[i]
        text = _normalize_text(raw)
        if not text:
            continue
        if _to_number(text) is None:
            return raw, i
    return values[0] if values else "", 0


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


def _parse_period_token(
    text: str, default_year: Optional[int]
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    解析列头中的期间信息，返回 (report_period, report_year, report_quarter)
    规则：
      - 2022年 -> 2022Q4
      - 2023年3月31日 -> 2023Q1
      - Q1/Q2/Q3/Q4 或 第一季度/第二季度/第三季度/第四季度 -> 以 default_year 组成 YYYYQx
      - 含同比/环比/增减/% 的列忽略
    """
    t = _normalize_text(text)
    if not t:
        return None, None, None

    if re.search(r"(同比|环比|增减|增长|变动|%|百分)", t):
        return None, None, None

    # 处理 "2023年3月31日" 格式
    date_match = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", t)
    if date_match:
        year = int(date_match.group(1))
        month = int(date_match.group(2))
        # 根据月份推断季度
        if 1 <= month <= 3:
            quarter = "Q1"
        elif 4 <= month <= 6:
            quarter = "Q2"
        elif 7 <= month <= 9:
            quarter = "Q3"
        else:
            quarter = "Q4"
        return f"{year}Q{quarter[1]}", year, quarter

    # 处理 "2022年" 格式
    m = re.search(r"(20\d{2})年", t)
    if m:
        year = int(m.group(1))
        return f"{year}Q4", year, "Q4"

    # 处理 "Q1/Q2/Q3/Q4" 或 "第一季度/第二季度/第三季度/第四季度" 格式
    if re.search(r"(第一季度|一季度|Q1|1-3月|1-3月份|1至3月)", t, re.IGNORECASE):
        if default_year is None:
            return None, None, None
        return f"{default_year}Q1", default_year, "Q1"
    if re.search(
        r"(第二季度|二季度|Q2|4-6月|4-6月份|4至6月|半年度|中报)", t, re.IGNORECASE
    ):
        if default_year is None:
            return None, None, None
        return f"{default_year}Q2", default_year, "Q2"
    if re.search(r"(第三季度|三季度|Q3|7-9月|7-9月份|7至9月)", t, re.IGNORECASE):
        if default_year is None:
            return None, None, None
        return f"{default_year}Q3", default_year, "Q3"
    if re.search(
        r"(第四季度|四季度|Q4|10-12月|10-12月份|10至12月|年度|年报)", t, re.IGNORECASE
    ):
        if default_year is None:
            return None, None, None
        return f"{default_year}Q4", default_year, "Q4"

    return None, None, None


def _build_column_tokens(df: pd.DataFrame, scan_rows: int = 5) -> Dict[int, str]:
    """
    把表头的多行信息按列拼接为一个 token，提升季度/年份识别率
    """
    tokens: Dict[int, str] = {}
    if df.empty:
        return tokens

    rows = min(scan_rows, len(df))
    for i in range(len(df.columns)):
        parts: List[str] = []
        for r in range(rows):
            v = df.iloc[r, i]
            t = _normalize_text(v)
            if t:
                parts.append(t)
        if parts:
            tokens[i] = "".join(parts)
    return tokens


def _infer_column_periods(
    df: pd.DataFrame, default_year: Optional[int], default_quarter: Optional[str]
) -> Dict[int, Tuple[str, int, str]]:
    """
    从表头行推断每一列对应的 report_period/report_year/report_quarter
    返回: {col_idx: (period, year, quarter)}
    """
    periods: Dict[int, Tuple[str, int, str]] = {}
    if df.empty:
        return periods

    col_tokens = _build_column_tokens(df, scan_rows=5)
    for i, token in col_tokens.items():
        p, y, q = _parse_period_token(token, default_year)
        if p and y and q:
            periods[i] = (p, y, q)

    # 若存在季度列，只保留季度列（避免混入同比/环比等列）
    has_quarter = any(q in ("Q1", "Q2", "Q3", "Q4") for _, (_, _, q) in periods.items())
    if has_quarter:
        periods = {i: v for i, v in periods.items() if v[2] in ("Q1", "Q2", "Q3", "Q4")}
    else:
        # 对于主要会计数据和财务指标表格，使用默认的报告期
        if default_year and default_quarter:
            # 使用从文件名推断的报告期
            if len(col_tokens) >= 2:
                # 遍历 col_tokens 中的所有键
                for i in col_tokens.keys():
                    # 跳过第一列（通常是指标名称）
                    if i == 0:
                        continue
                    # 为所有列创建报告期，使用默认的报告期
                    period = f"{default_year}Q{default_quarter[1]}"
                    periods[i] = (period, default_year, default_quarter)

    return periods


def _pick_value_with_role(row: pd.Series, col_roles: Dict[int, str], label_col: int):
    """
    从一行中选数值：
    1) 优先 current
    2) 再 previous
    3) 最后任意第一个可转数字
    返回固定三元组: (value, role, col_idx)
    """
    values = row.tolist()
    start = min(label_col + 1, len(values))
    candidate_indices = list(range(start, len(values)))

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


def _is_financial_indicators_table(df: pd.DataFrame) -> bool:
    """
    识别是否为主要会计数据和财务指标表格
    """
    if df.empty:
        return False
    
    # 检查表头是否包含关键词
    for i in range(min(3, len(df))):
        row = df.iloc[i]
        text = "".join(_normalize_text(v) for v in row.tolist())
        if "主要会计数据" in text or "财务指标" in text:
            return True
    return False

def extract_metric_records(
    raw_tables: Iterable[RawTable],
    stock_code: str,
    stock_abbr: Optional[str],
    report_period: Optional[str],
    report_year: Optional[int],
    report_type: Optional[str],
    report_quarter: Optional[str],
) -> List[MetricRecord]:
    """
    逐行扫描 raw_table，提取科目名，提取数字，字段对比，返回 MetricRecord 对象
    """
    records: List[MetricRecord] = []

    for rt in raw_tables:
        df = rt.df.fillna("")
        if df.empty:
            continue

        # 识别是否为主要会计数据和财务指标表格
        is_financial_indicators = _is_financial_indicators_table(df)
        
        # 识别列角色（本期/上期）
        col_roles = _build_column_roles(df)
        # 识别列对应的季度/年份
        col_periods = _infer_column_periods(df, report_year, report_quarter)

        # 若前几行像表头，行遍历时自动跳过
        for _, row in df.iterrows():
            # 跳过明显表头行
            if _is_header_like_row(row):
                continue

            item_text_raw, label_col = _find_label_cell(row)
            item_text = _normalize_text(item_text_raw)

            # 若没有科目名，丢掉该行
            if not item_text:
                continue

            # 用于去重：同一table + field + source_text，只保留最高置信度
            best_local: dict[tuple[str, str, str, str], MetricRecord] = {}

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

                    # 若识别到了列期间，就逐列写入
                    if col_periods:
                        # 重新构建列令牌，用于识别同比增长列
                        col_tokens = _build_column_tokens(df, scan_rows=5)
                        for col_idx, (p, y, q) in col_periods.items():
                            if col_idx <= label_col:
                                continue
                            num = _to_number(row.iloc[col_idx])
                            if num is None:
                                continue

                            # 检查该列是否是同比增长列
                            is_yoy_column = False
                            if col_idx in col_tokens:
                                token = col_tokens[col_idx]
                                if "同比" in token or "环比" in token or "增减" in token:
                                    is_yoy_column = True

                            # 为同比增长字段创建对应的同比字段名
                            if is_yoy_column and "_yoy" not in field_key:
                                # 为资产类字段创建同比增长字段
                                if field_key.startswith("asset_"):
                                    yoy_field_key = field_key + "_yoy_growth"
                                # 为负债类字段创建同比增长字段
                                elif field_key.startswith("liability_"):
                                    yoy_field_key = field_key + "_yoy_growth"
                                # 为其他字段创建同比增长字段
                                else:
                                    yoy_field_key = field_key + "_yoy_growth"
                                # 检查该同比字段是否存在于映射中
                                if table_name in FIELD_PATTERNS and yoy_field_key in FIELD_PATTERNS[table_name]:
                                    field_key_to_use = yoy_field_key
                                else:
                                    field_key_to_use = field_key
                            else:
                                field_key_to_use = field_key

                            # 确保报告期一致性：优先使用表格中的报告期
                            mr = MetricRecord(
                                table_name=table_name,
                                field_key=field_key_to_use,
                                value=num,
                                report_period=p,
                                report_year=y,
                                report_type=report_type,
                                report_quarter=q,
                                stock_code=stock_code,
                                stock_abbr=stock_abbr,
                                confidence=best_conf,
                                source_page=rt.page_no,
                                source_text=f"{item_text_raw} | col={col_idx} period={p}",
                            )

                            key = (table_name, field_key_to_use, item_text, p)
                            old = best_local.get(key)
                            if old is None or mr.confidence > old.confidence:
                                best_local[key] = mr
                    else:
                        # 对于主要会计数据和财务指标表格，特殊处理
                        if is_financial_indicators:
                            # 尝试从所有列中提取数据
                            for col_idx in range(label_col + 1, len(df.columns)):
                                num = _to_number(row.iloc[col_idx])
                                if num is not None:
                                    # 使用默认的报告期
                                    mr = MetricRecord(
                                        table_name=table_name,
                                        field_key=field_key,
                                        value=num,
                                        report_period=report_period,
                                        report_year=report_year,
                                        report_type=report_type,
                                        report_quarter=report_quarter,
                                        stock_code=stock_code,
                                        stock_abbr=stock_abbr,
                                        confidence=best_conf,
                                        source_page=rt.page_no,
                                        source_text=f"{item_text_raw} | col={col_idx} (financial indicators table)",
                                    )
                                    key = (table_name, field_key, item_text, report_period or "")
                                    old = best_local.get(key)
                                    if old is None or mr.confidence > old.confidence:
                                        best_local[key] = mr
                        else:
                            # 常规表格处理
                            value, picked_role, picked_col = _pick_value_with_role(
                                row, col_roles, label_col
                            )
                            if value is None:
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

                            key = (table_name, field_key, item_text, report_period or "")
                            old = best_local.get(key)
                            if old is None or mr.confidence > old.confidence:
                                best_local[key] = mr

            records.extend(best_local.values())

    return records

# File: core/pdf/field_mapping.py
from __future__ import annotations

import re

from config.db_schema import DATABASE_SCHEMA_DICT


def _to_pattern(label: str) -> str:
    return re.escape(label)


# 后续可手动扩展同义词
# 全局字典，key: 元组；value: 列表
MANUAL_ALIASES: dict[tuple[str, str], list[str]] = {
    ("income_sheet", "net_profit"): [
        r"净利润(?!同比|环比)",
        r"归属于.*净利润",
        r"归母净利润",
        r"归属于母公司股东的净利润",
    ],
    ("income_sheet", "total_operating_revenue"): [
        r"营业总收入",
        r"营业收入(?!同比|环比)",
        r"主营业务收入",
    ],
    ("cash_flow_sheet", "net_cash_flow"): [
        r"现金及现金等价物净增加额",
        r"净现金流",
    ],
    ("cash_flow_sheet", "operating_cf_net_amount"): [
        r"经营活动产生的现金流量净额",
        r"经营活动现金流净额",
    ],
    ("cash_flow_sheet", "investing_cf_net_amount"): [
        r"投资活动产生的现金流量净额",
        r"投资活动现金流净额",
    ],
    ("cash_flow_sheet", "financing_cf_net_amount"): [
        r"(筹资|融资)活动产生的现金流量净额",
        r"(筹资|融资)活动现金流净额",
    ],
    ("balance_sheet", "asset_total_assets"): [r"总资产"],
    ("balance_sheet", "liability_total_liabilities"): [r"总负债", r"负债合计"],
    ("balance_sheet", "equity_total_equity"): [r"所有者权益合计", r"股东权益合计"],
    ("balance_sheet", "asset_liability_ratio"): [r"资产负债率"],
}


def build_field_patterns() -> dict[str, dict[str, list[str]]]:
    patterns: dict[str, dict[str, list[str]]] = {}

    for table_name, field_map in DATABASE_SCHEMA_DICT.items():
        patterns[table_name] = {}
        for field_key, cn_label in field_map.items():
            # 官方附件中的完整字段
            base = [_to_pattern(cn_label)]
            # 上方人造含有正则表达式的模糊匹配字段
            extra = MANUAL_ALIASES.get((table_name, field_key), [])
            # 官方字段 & 模糊匹配字段进行拼接，相当于在原有大字典的基础上加入中文方言字段
            patterns[table_name][field_key] = base + extra
    return patterns


# 把 patterns 赋值给 ‘字段匹配规则’ 这个全局变量
FIELD_PATTERNS: dict[str, dict[str, list[str]]] = build_field_patterns()

# File: core/pdf/field_mapping.py
from __future__ import annotations

import re

from config.db_schema import DATABASE_SCHEMA_DICT


def _to_pattern(label: str) -> str:
    return re.escape(label)


# 可手动扩展同义词
MANUAL_ALIASES: dict[tuple[str, str], list[str]] = {
    ("balance_sheet", "liability_total_liabilities"): [r"总负债", r"负债合计"],
    ("balance_sheet", "equity_total_equity"): [r"所有者权益合计", r"股东权益合计"],
    ("balance_sheet", "asset_total_assets"): [r"总资产"],
    ("balance_sheet", "asset_liability_ratio"): [r"资产负债率"],
    ("income_sheet", "total_operating_revenue"): [
        r"营业总收入",
        r"营业收入(?!同比|环比)",
    ],
    ("income_sheet", "net_profit"): [r"净利润(?!同比|环比)", r"归属于.*净利润"],
    ("income_sheet", "total_profit"): [r"合并利润总额", r"利润总额"],
    ("income_sheet", "operating_profit"): [r"营业利润"],
    ("cash_flow_sheet", "operating_cf_net_amount"): [r"经营活动产生的现金流量净额"],
    ("cash_flow_sheet", "investing_cf_net_amount"): [r"投资活动产生的现金流量净额"],
    ("cash_flow_sheet", "financing_cf_net_amount"): [
        r"(筹资|融资)活动产生的现金流量净额"
    ],
    ("cash_flow_sheet", "net_cash_flow"): [r"现金及现金等价物净增加额", r"净现金流"],
    ("core_performance_indicators_sheet", "eps"): [r"每股收益"],
    ("core_performance_indicators_sheet", "roe"): [r"净资产收益率"],
    ("core_performance_indicators_sheet", "net_asset_per_share"): [r"每股净资产"],
}


def build_field_patterns() -> dict[str, dict[str, list[str]]]:
    patterns: dict[str, dict[str, list[str]]] = {}

    for table_name, field_map in DATABASE_SCHEMA_DICT.items():
        patterns[table_name] = {}
        for field_key, cn_label in field_map.items():
            base = [_to_pattern(cn_label)]

            extra = MANUAL_ALIASES.get((table_name, field_key), [])

            patterns[table_name][field_key] = base + extra
    return patterns


FIELD_PATTERNS: dict[str, dict[str, list[str]]] = build_field_patterns()

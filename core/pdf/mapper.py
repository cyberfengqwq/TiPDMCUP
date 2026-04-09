# File: core/pdf/field_mapping.py
from __future__ import annotations

import re

from config.db_schema import DATABASE_SCHEMA_DICT


def _to_pattern(label: str) -> str:
    return re.escape(label)


# 扩展的同义词和变体规则
# 涵盖财报中常见的不同表述方式
MANUAL_ALIASES: dict[tuple[str, str], list[str]] = {
    # ==================== 核心表指标 (core_performance_indicators_sheet) ====================
    ("core_performance_indicators_sheet", "eps"): [
        r"每股收益(?!同比|环比)",
        r"基本每股收益",
        r"EPS",
        r"每股盈利",
    ],
    ("core_performance_indicators_sheet", "total_operating_revenue"): [
        r"营业总收入(?!同比|环比)",
        r"营业收入(?!同比|环比)",
        r"主营业务收入",
        r"营业总收入-合计",
        r"营收(?!同比|环比)",
    ],
    ("core_performance_indicators_sheet", "operating_revenue_yoy_growth"): [
        r"营业总收入.*同比增长",
        r"营业收入.*同比增长",
        r"营业总收入.*同比",
        r"营业收入.*同比",
    ],
    ("core_performance_indicators_sheet", "operating_revenue_qoq_growth"): [
        r"营业总收入.*环比增长",
        r"营业收入.*环比增长",
        r"营业总收入.*环比",
        r"营业收入.*环比",
        r"营业总收入-季度环比增长",
    ],
    ("core_performance_indicators_sheet", "net_profit_10k_yuan"): [
        r"净利润(?!同比|环比|归|扣)",
        r"归属于.*净利润",
        r"归母净利润",
        r"归属于母公司股东的净利润",
        r"净利润\(万元\)",
    ],
    ("core_performance_indicators_sheet", "net_profit_yoy_growth"): [
        r"净利润.*同比增长",
        r"净利润.*同比",
        r"归属于.*同比",
    ],
    ("core_performance_indicators_sheet", "net_profit_qoq_growth"): [
        r"净利润.*环比增长",
        r"净利润.*环比",
        r"净利润-季度环比增长",
    ],
    ("core_performance_indicators_sheet", "net_asset_per_share"): [
        r"每股净资产(?!同比|环比)",
        r"每股资产",
        r"单位净资产",
    ],
    ("core_performance_indicators_sheet", "roe"): [
        r"净资产收益率(?!同比|环比|加权)",
        r"ROE(?!加权)",
        r"净资产报酬率",
        r"权益报酬率",
    ],
    ("core_performance_indicators_sheet", "operating_cf_per_share"): [
        r"每股经营现金流",
        r"每股现金流量",
        r"每股经营活动现金流",
    ],
    ("core_performance_indicators_sheet", "net_profit_excl_non_recurring"): [
        r"扣非净利润",
        r"扣除非经常性损益后的净利润",
        r"归属于母公司的扣非净利润",
        r"扣非.*净利润",
    ],
    ("core_performance_indicators_sheet", "net_profit_excl_non_recurring_yoy"): [
        r"扣非净利润.*同比",
        r"扣非.*同比增长",
    ],
    ("core_performance_indicators_sheet", "gross_profit_margin"): [
        r"销售毛利率",
        r"毛利率",
        r"毛利润率",
    ],
    ("core_performance_indicators_sheet", "net_profit_margin"): [
        r"销售净利率(?!同比|环比)",
        r"净利润率",
        r"净利率",
    ],
    ("core_performance_indicators_sheet", "roe_weighted_excl_non_recurring"): [
        r"加权平均净资产收益率(?!同比).*扣非",
        r"加权平均ROE.*扣非",
        r"加权净资产收益率.*扣非",
    ],
    # ==================== 资产负债表 (balance_sheet) ====================
    ("balance_sheet", "asset_cash_and_cash_equivalents"): [
        r"资产.*货币资金",
        r"货币资金",
        r"现金及现金等价物",
        r"库存现金",
        r"银行存款",
    ],
    ("balance_sheet", "asset_accounts_receivable"): [
        r"资产.*应收账款",
        r"应收账款(?!融资)",
        r"应收款项",
    ],
    ("balance_sheet", "asset_inventory"): [
        r"资产.*存货",
        r"存货",
        r"库存",
        r"商品存货",
    ],
    ("balance_sheet", "asset_trading_financial_assets"): [
        r"资产.*交易性金融资产",
        r"交易性金融资产",
        r"短期投资",
        r"金融资产(?!长期)",
    ],
    ("balance_sheet", "asset_construction_in_progress"): [
        r"资产.*在建工程",
        r"在建工程",
        r"施工中工程",
    ],
    ("balance_sheet", "asset_total_assets"): [
        r"总资产(?!同比)",
        r"资产总计",
        r"资产合计",
    ],
    ("balance_sheet", "asset_total_assets_yoy_growth"): [
        r"总资产.*同比",
        r"资产总计.*同比",
    ],
    ("balance_sheet", "liability_accounts_payable"): [
        r"负债.*应付账款",
        r"应付账款(?!融资)",
        r"应付款项",
    ],
    ("balance_sheet", "liability_advance_from_customers"): [
        r"负债.*预收账款",
        r"预收账款",
        r"预收款",
    ],
    ("balance_sheet", "liability_total_liabilities"): [
        r"总负债(?!同比)",
        r"负债总计",
        r"负债合计",
    ],
    ("balance_sheet", "liability_total_liabilities_yoy_growth"): [
        r"总负债.*同比",
        r"负债总计.*同比",
    ],
    ("balance_sheet", "liability_contract_liabilities"): [
        r"合同负债",
        r"预付货款",
        r"销售退回估计",
    ],
    ("balance_sheet", "liability_short_term_loans"): [
        r"短期借款",
        r"短期贷款",
        r"短期债务",
    ],
    ("balance_sheet", "asset_liability_ratio"): [
        r"资产负债率(?!同比)",
        r"负债比率",
        r"资产负债比",
    ],
    ("balance_sheet", "equity_unappropriated_profit"): [
        r"股东权益.*未分配利润",
        r"未分配利润",
        r"留存利润",
    ],
    ("balance_sheet", "equity_total_equity"): [
        r"所有者权益合计",
        r"股东权益合计",
        r"权益合计",
        r"权益总计",
    ],
    # ==================== 利润表 (income_sheet) ====================
    ("income_sheet", "net_profit"): [
        r"净利润(?!同比|环比|归|扣)",
        r"归属于.*净利润",
        r"归母净利润",
        r"归属于母公司股东的净利润",
        r"本期净利润",
    ],
    ("income_sheet", "net_profit_yoy_growth"): [
        r"净利润.*同比(?!环)",
        r"净利润(?:增长|变化).*%",
    ],
    ("income_sheet", "other_income"): [
        r"其他收益",
        r"营业外收入",
        r"其他收入",
    ],
    ("income_sheet", "total_operating_revenue"): [
        r"营业总收入(?!同比|环比)",
        r"营业收入(?!同比|环比)",
        r"营业收入合计",
        r"主营业务收入",
        r"营收(?!同比|环比)",
    ],
    ("income_sheet", "operating_revenue_yoy_growth"): [
        r"营业总收入.*同比",
        r"营业收入.*同比",
        r"营业总收入(?:增长|变化).*%",
    ],
    ("income_sheet", "operating_expense_cost_of_sales"): [
        r"营业总支出.*营业支出",
        r"营业支出(?!费)",
        r"营业成本",
        r"销售成本",
        r"营业支出-主营",
    ],
    ("income_sheet", "operating_expense_selling_expenses"): [
        r"营业总支出.*销售费用",
        r"销售费用",
        r"销售费",
    ],
    ("income_sheet", "operating_expense_administrative_expenses"): [
        r"营业总支出.*管理费用",
        r"管理费用",
        r"管理费",
        r"行政费用",
    ],
    ("income_sheet", "operating_expense_financial_expenses"): [
        r"营业总支出.*财务费用",
        r"财务费用",
        r"财务费",
        r"金融费用",
        r"利息费用",
    ],
    ("income_sheet", "operating_expense_rnd_expenses"): [
        r"营业总支出.*研发费用",
        r"研发费用",
        r"研发费",
        r"研究开发费",
        r"R&D费用",
    ],
    ("income_sheet", "operating_expense_taxes_and_surcharges"): [
        r"营业总支出.*税金及附加",
        r"税金及附加",
        r"营业税及附加",
        r"税费",
    ],
    ("income_sheet", "total_operating_expenses"): [
        r"营业总支出(?!-)",
        r"营业支出合计",
        r"营业费用合计",
    ],
    ("income_sheet", "operating_profit"): [
        r"营业利润(?!率)",
        r"营业利润-合计",
        r"经营利润",
    ],
    ("income_sheet", "total_profit"): [
        r"利润总额(?!率)",
        r"利润总计",
        r"税前利润",
    ],
    ("income_sheet", "asset_impairment_loss"): [
        r"资产减值损失",
        r"减值准备",
        r"资产减值",
    ],
    ("income_sheet", "credit_impairment_loss"): [
        r"信用减值损失",
        r"坏账准备",
        r"减值准备.*应收",
    ],
    # ==================== 现金流量表 (cash_flow_sheet) ====================
    ("cash_flow_sheet", "net_cash_flow"): [
        r"现金及现金等价物净增加额",
        r"净现金流(?!占比)",
        r"现金流净增加",
    ],
    ("cash_flow_sheet", "net_cash_flow_yoy_growth"): [
        r"现金及现金等价物净增加额.*同比",
        r"净现金流.*同比",
    ],
    ("cash_flow_sheet", "operating_cf_net_amount"): [
        r"经营活动产生的现金流量净额",
        r"经营活动现金流净额",
        r"经营活动产生的现金流",
    ],
    ("cash_flow_sheet", "operating_cf_ratio_of_net_cf"): [
        r"经营性现金流.*净现金流占比",
        r"经营现金流.*占比",
    ],
    ("cash_flow_sheet", "operating_cf_cash_from_sales"): [
        r"经营性现金流.*销售商品收到的现金",
        r"销售商品收到的现金",
        r"销售收入现金",
    ],
    ("cash_flow_sheet", "investing_cf_net_amount"): [
        r"投资活动产生的现金流量净额",
        r"投资活动现金流净额",
        r"投资活动产生的现金流",
    ],
    ("cash_flow_sheet", "investing_cf_ratio_of_net_cf"): [
        r"投资性现金流.*净现金流占比",
        r"投资现金流.*占比",
    ],
    ("cash_flow_sheet", "investing_cf_cash_for_investments"): [
        r"投资性现金流.*投资支付的现金",
        r"投资支付的现金",
        r"投资支出",
    ],
    ("cash_flow_sheet", "investing_cf_cash_from_investment_recovery"): [
        r"投资性现金流.*收回投资收到的现金",
        r"收回投资收到的现金",
        r"投资回收",
    ],
    ("cash_flow_sheet", "financing_cf_cash_from_borrowing"): [
        r"融资性现金流.*取得借款收到的现金",
        r"取得借款收到的现金",
        r"借款收入",
    ],
    ("cash_flow_sheet", "financing_cf_cash_for_debt_repayment"): [
        r"融资性现金流.*偿还债务支付的现金",
        r"偿还债务支付的现金",
        r"偿债支出",
    ],
    ("cash_flow_sheet", "financing_cf_net_amount"): [
        r"(?:筹资|融资)活动产生的现金流量净额",
        r"(?:筹资|融资)活动现金流净额",
        r"(?:筹资|融资)活动产生的现金流",
    ],
    ("cash_flow_sheet", "financing_cf_ratio_of_net_cf"): [
        r"融资性现金流.*净现金流占比",
        r"融资现金流.*占比",
    ],
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
            # 官方字段 & 模糊匹配字段进行拼接
            patterns[table_name][field_key] = base + extra
    return patterns


# 把 patterns 赋值给 '字段匹配规则' 这个全局变量
FIELD_PATTERNS: dict[str, dict[str, list[str]]] = build_field_patterns()

# core/agent/visualizer.py

import logging
import re
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from matplotlib import font_manager

font_path = '/home/qwq/TiPDMCUP/scripts/SimHei.ttf'
font_manager.fontManager.addfont(font_path)

matplotlib.rcParams["font.family"] = ["SimHei"]
matplotlib.rcParams["axes.unicode_minus"] = False

logger = logging.getLogger(__name__)

RESULT_DIR = Path("./result")
RESULT_DIR.mkdir(parents=True, exist_ok=True)

# ── 字段元数据 ────────────────────────────────────────────────────────────────

FIELD_LABELS: dict[str, str] = {
    "total_operating_revenue": "营业总收入(万元)",
    "net_profit_10k_yuan": "净利润(万元)",
    "net_profit": "净利润(万元)",
    "operating_profit": "营业利润(万元)",
    "total_profit": "利润总额(万元)",
    "eps": "每股收益(元/股)",
    "net_asset_per_share": "每股净资产(元/股)",
    "operating_cf_per_share": "每股经营现金流(元/股)",
    "roe": "净资产收益率(%)",
    "gross_profit_margin": "毛利率(%)",
    "net_profit_margin": "净利率(%)",
    "roe_weighted_excl_non_recurring": "加权ROE扣非(%)",
    "operating_revenue_yoy_growth": "营收同比增长(%)",
    "operating_revenue_qoq_growth": "营收环比增长(%)",
    "net_profit_yoy_growth": "净利润同比增长(%)",
    "net_profit_qoq_growth": "净利润环比增长(%)",
    "net_profit_excl_non_recurring": "扣非净利润(万元)",
    "net_profit_excl_non_recurring_yoy": "扣非净利润同比(%)",
    "asset_total_assets": "总资产(万元)",
    "asset_total_assets_yoy_growth": "总资产同比(%)",
    "asset_cash_and_cash_equivalents": "货币资金(万元)",
    "asset_accounts_receivable": "应收账款(万元)",
    "asset_inventory": "存货(万元)",
    "asset_trading_financial_assets": "交易性金融资产(万元)",
    "asset_construction_in_progress": "在建工程(万元)",
    "asset_liability_ratio": "资产负债率(%)",
    "liability_total_liabilities": "总负债(万元)",
    "liability_total_liabilities_yoy_growth": "总负债同比(%)",
    "liability_accounts_payable": "应付账款(万元)",
    "liability_advance_from_customers": "预收账款(万元)",
    "liability_contract_liabilities": "合同负债(万元)",
    "liability_short_term_loans": "短期借款(万元)",
    "equity_total_equity": "股东权益(万元)",
    "equity_unappropriated_profit": "未分配利润(万元)",
    "operating_cf_net_amount": "经营现金流净额(万元)",
    "investing_cf_net_amount": "投资现金流净额(万元)",
    "financing_cf_net_amount": "筹资现金流净额(万元)",
    "net_cash_flow": "净现金流(元)",
    "net_cash_flow_yoy_growth": "净现金流同比(%)",
    "operating_cf_cash_from_sales": "销售收到现金(万元)",
    "investing_cf_cash_for_investments": "投资支付现金(万元)",
    "investing_cf_cash_from_investment_recovery": "收回投资现金(万元)",
    "financing_cf_cash_from_borrowing": "取得借款现金(万元)",
    "financing_cf_cash_for_debt_repayment": "偿还债务现金(万元)",
    "total_operating_expenses": "营业总支出(万元)",
    "operating_expense_cost_of_sales": "营业支出(万元)",
    "operating_expense_selling_expenses": "销售费用(万元)",
    "operating_expense_administrative_expenses": "管理费用(万元)",
    "operating_expense_financial_expenses": "财务费用(万元)",
    "operating_expense_rnd_expenses": "研发费用(万元)",
    "operating_expense_taxes_and_surcharges": "税金及附加(万元)",
    "other_income": "其他收益(万元)",
    "asset_impairment_loss": "资产减值损失(万元)",
    "credit_impairment_loss": "信用减值损失(万元)",
    "report_period": "报告期",
    "report_year": "报告年份",
    "stock_abbr": "公司",
    "stock_code": "股票代码",
}

# 百分比字段（不加万元，直接显示 %）
PCT_FIELDS: set[str] = {
    k for k, v in FIELD_LABELS.items() if v.endswith("(%)")
} | {
    "yield_rate", "ratio", "rate",  # SQL AS 别名常用词
}

# 元/股字段
PER_SHARE_FIELDS: set[str] = {
    "eps", "net_asset_per_share", "operating_cf_per_share",
}

# ── 报告期排序 ────────────────────────────────────────────────────────────────

_PERIOD_ORDER = {"Q1": 1, "HY": 2, "Q3": 3, "FY": 4}


def _period_sort_key(p: str) -> tuple:
    m = re.match(r"(\d{4})(FY|HY|Q1|Q3)", str(p))
    if m:
        return (int(m.group(1)), _PERIOD_ORDER.get(m.group(2), 0))
    return (9999, 0)


def _is_period_column(labels: list[str]) -> bool:
    return any(re.match(r"\d{4}(FY|HY|Q1|Q3)", str(l)) for l in labels)


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _to_number(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _field_label(field: str) -> str:
    return FIELD_LABELS.get(field, field)


def _is_pct_field(field: str) -> bool:
    if field in PCT_FIELDS:
        return True
    # alias 模式：以 ratio/rate/growth/margin/roe 结尾
    return bool(re.search(r"(ratio|rate|growth|margin|roe|yoy|qoq)$", field, re.I))


def _fmt_val(v: float, field: str = "") -> str:
    """按字段类型格式化数值"""
    if _is_pct_field(field):
        return f"{v:.2f}%"
    if field in PER_SHARE_FIELDS:
        return f"{v:.4f}元"
    # 万元金额
    if abs(v) >= 100_000:
        return f"{v / 10_000:.1f}亿"
    if abs(v) >= 10_000:
        return f"{v / 10_000:.2f}亿"
    return f"{v:.0f}万"


def _get_numeric_fields(data: list) -> list[str]:
    if not data:
        return []
    skip = {"serial_number", "stock_code", "report_year"}
    return [
        k for k, v in data[0].items()
        if k not in skip and _to_number(v) is not None
    ]


def _get_label_field(data: list) -> str:
    if not data:
        return ""
    first = data[0]

    # report_period 只有在多行且值各不相同时才作为 x 轴（时间序列）
    if "report_period" in first:
        periods = [str(r.get("report_period", "")) for r in data]
        if len(set(periods)) > 1:  # 多个不同的期 → 时间序列
            return "report_period"
        # 所有行同一个期 → 应该用公司名做 x 轴
        if "stock_abbr" in first:
            return "stock_abbr"

    for preferred in ["stock_abbr", "stock_code"]:
        if preferred in first:
            return preferred
    for k, v in first.items():
        if isinstance(v, str) and _to_number(v) is None:
            return k
    return list(first.keys())[0]


def _sort_by_period(data: list, label_field: str) -> list:
    """如果标签列是报告期，按时间顺序排序"""
    labels = [str(row.get(label_field, "")) for row in data]
    if _is_period_column(labels):
        return sorted(data, key=lambda r: _period_sort_key(str(r.get(label_field, ""))))
    return data


_AGG_PREFIXES = ("count", "sum", "avg", "max", "min", "total_count", "cnt")


def _is_single_aggregate(data: list) -> bool:
    """单行聚合结果（如 COUNT(*)=4）不适合画图"""
    if len(data) != 1:
        return False
    keys = list(data[0].keys())
    return all(k.lower().startswith(_AGG_PREFIXES) or k.lower() in ("count(*)", "count(1)") for k in keys)


def _has_multi_company(data: list) -> bool:
    """数据包含多家不同公司"""
    abbrs = {str(r.get("stock_abbr", "")) for r in data if r.get("stock_abbr")}
    return len(abbrs) > 1


# ── 图表类型判断 ──────────────────────────────────────────────────────────────

def _detect_chart_type(question: str, data: list) -> str:
    if not data:
        return "none"

    # 单行聚合（COUNT/SUM/AVG）→ 不画图
    if _is_single_aggregate(data):
        return "none"

    q = question
    n = len(data)

    # 1. 用户明确指定图表类型（最高优先级）
    if "散点图" in q or "scatter" in q.lower():
        return "scatter"
    if any(k in q for k in ["水平柱状图", "横向柱状图", "水平条形", "横向条形"]):
        return "bar_h"
    if any(k in q for k in ["折线图", "趋势图", "线图"]):
        return "line"
    if any(k in q for k in ["柱状图", "条形图", "柱形图"]):
        return "bar"
    if any(k in q for k in ["饼图", "环形图", "pie图"]):
        return "pie" if n <= 10 else "bar"
    if "表格" in q:
        return "table"

    # 2. 单行数据 → 表格
    if n == 1:
        return "table"

    # 3. 数据特征优先：多公司+多报告期 → 分组折线图（在语义关键词之前判断）
    if _has_multi_company(data) and "report_period" in (data[0] if data else {}):
        periods = {str(r.get("report_period", "")) for r in data if r.get("report_period")}
        if len(periods) > 1:
            return "line_multi"

    # 4. 语义关键词
    if any(k in q for k in ["趋势", "变化", "走势", "历年", "近几年", "历史"]):
        return "line"
    if any(k in q for k in ["对比", "比较", "排名", "top", "最高", "最低"]):
        return "bar"
    if any(k in q for k in ["占比", "构成", "分布", "比重", "份额"]):
        return "pie" if n <= 10 else "bar"

    # 5. 数据特征兜底
    label_field = _get_label_field(data)
    labels = [str(row.get(label_field, "")) for row in data]
    if _is_period_column(labels):
        return "line"
    if n >= 3:
        return "bar"
    return "table"


# ── 主入口 ────────────────────────────────────────────────────────────────────

def draw_chart(question: str, sql_result: Any, problem_id: str, seq: int = 1) -> str:
    if not isinstance(sql_result, list) or not sql_result:
        return ""

    chart_type = _detect_chart_type(question, sql_result)
    if chart_type == "none":
        return ""

    save_path = RESULT_DIR / f"{problem_id}_{seq}.jpg"
    try:
        if chart_type == "scatter":
            _draw_scatter(sql_result, question, save_path)
        elif chart_type == "line_multi":
            _draw_line_multi(sql_result, question, save_path)
        elif chart_type == "line":
            _draw_line(sql_result, question, save_path)
        elif chart_type in ("bar", "bar_h"):
            _draw_bar(sql_result, question, save_path, horizontal=(chart_type == "bar_h"))
        elif chart_type == "pie":
            _draw_pie(sql_result, question, save_path)
        else:
            _draw_table(sql_result, question, save_path)
        logger.info(f"[Visualizer] 图表已保存: {save_path}")
        return f"/result/{problem_id}_{seq}.jpg"
    except Exception as e:
        logger.warning(f"[Visualizer] 绘图失败: {e}", exc_info=True)
        return ""


# ── 各图表实现 ────────────────────────────────────────────────────────────────

_PRIORITY_FIELDS = [
    "total_operating_revenue", "net_profit_10k_yuan", "net_profit",
    "operating_profit", "total_profit", "eps", "roe", "gross_profit_margin",
]


def _draw_line(data: list, title: str, save_path: Path):
    label_field = _get_label_field(data)
    data = _sort_by_period(data, label_field)
    numeric_fields = _get_numeric_fields(data)
    if not numeric_fields:
        raise ValueError("无数值字段")

    plot_fields = [f for f in _PRIORITY_FIELDS if f in numeric_fields] or numeric_fields[:3]
    labels = [str(row.get(label_field, "")) for row in data]
    x = np.arange(len(labels))

    # 判断是否全是百分比字段
    all_pct = all(_is_pct_field(f) for f in plot_fields)
    fmt = (lambda v, _: f"{v:.1f}%") if all_pct else (lambda v, _: _fmt_val(v, plot_fields[0]))

    fig, ax = plt.subplots(figsize=(max(10, len(labels) * 0.9), 5))
    for field in plot_fields:
        values = [(_to_number(row.get(field)) or 0) for row in data]
        ax.plot(x, values, marker="o", label=_field_label(field), linewidth=2)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    ax.set_title(title[:50], fontsize=12)
    ax.legend(loc="best", fontsize=9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt))
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def _draw_bar(data: list, title: str, save_path: Path, horizontal: bool = False):
    label_field = _get_label_field(data)
    data = _sort_by_period(data, label_field)
    numeric_fields = _get_numeric_fields(data)
    if not numeric_fields:
        raise ValueError("无数值字段")

    plot_fields = [f for f in _PRIORITY_FIELDS if f in numeric_fields] or numeric_fields[:2]
    if not plot_fields:
        plot_fields = numeric_fields[:2]

    labels = [str(row.get(label_field, "")) for row in data]

    # 数据量大或明确要求 → 水平条形图
    if not horizontal:
        horizontal = len(labels) > 15 or (len(labels) > 8 and len(plot_fields) == 1)

    all_pct = all(_is_pct_field(f) for f in plot_fields)
    fmt = (lambda v, _: f"{v:.1f}%") if all_pct else (lambda v, _: _fmt_val(v, plot_fields[0]))

    if horizontal:
        fig, ax = plt.subplots(figsize=(10, max(6, len(labels) * 0.45)))
        x = np.arange(len(labels))
        width = 0.8 / max(len(plot_fields), 1)
        for i, field in enumerate(plot_fields):
            values = [(_to_number(row.get(field)) or 0) for row in data]
            offset = (i - len(plot_fields) / 2 + 0.5) * width
            ax.barh(x + offset, values, width, label=_field_label(field), alpha=0.85)
        ax.set_yticks(x)
        ax.set_yticklabels(labels, fontsize=9)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(fmt))
    else:
        fig, ax = plt.subplots(figsize=(max(10, len(labels) * 1.1), 5))
        x = np.arange(len(labels))
        width = 0.8 / max(len(plot_fields), 1)
        for i, field in enumerate(plot_fields):
            values = [(_to_number(row.get(field)) or 0) for row in data]
            offset = (i - len(plot_fields) / 2 + 0.5) * width
            ax.bar(x + offset, values, width, label=_field_label(field), alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt))

    ax.set_title(title[:50], fontsize=12)
    ax.legend(loc="best", fontsize=9)
    ax.grid(axis="x" if horizontal else "y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def _draw_pie(data: list, title: str, save_path: Path):
    label_field = _get_label_field(data)
    numeric_fields = _get_numeric_fields(data)
    if not numeric_fields:
        raise ValueError("无数值字段")

    value_field = numeric_fields[0]
    pairs = [
        (str(row.get(label_field, "")), abs(_to_number(row.get(value_field)) or 0))
        for row in data
    ]
    pairs = [(l, v) for l, v in pairs if v > 0]
    if not pairs:
        raise ValueError("无有效数值")

    # 超过10条 → 合并尾部为"其他"
    MAX_SLICES = 10
    if len(pairs) > MAX_SLICES:
        pairs.sort(key=lambda x: x[1], reverse=True)
        top = pairs[:MAX_SLICES - 1]
        others_val = sum(v for _, v in pairs[MAX_SLICES - 1:])
        top.append(("其他", others_val))
        pairs = top

    labels, values = zip(*pairs)
    fig, ax = plt.subplots(figsize=(9, 7))
    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct="%1.1f%%",
        startangle=90,
        pctdistance=0.82,
    )
    for t in texts:
        t.set_fontsize(9)
    for t in autotexts:
        t.set_fontsize(8)
    ax.set_title(title[:50], fontsize=12)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def _draw_table(data: list, title: str, save_path: Path):
    if not data:
        raise ValueError("空数据")

    display_data = data[:20]
    cols = list(display_data[0].keys())
    # 格式化数值：百分比字段加%，金额字段保留2位小数
    def fmt_cell(col, val):
        n = _to_number(val)
        if n is None:
            return str(val) if val is not None else ""
        if _is_pct_field(col):
            return f"{n:.2f}%"
        if col in PER_SHARE_FIELDS:
            return f"{n:.4f}"
        return f"{n:,.2f}"

    rows = [[fmt_cell(c, row.get(c, "")) for c in cols] for row in display_data]
    col_labels = [_field_label(c) for c in cols]

    fig, ax = plt.subplots(
        figsize=(max(10, len(cols) * 1.8), max(3, len(rows) * 0.5 + 1.5))
    )
    ax.axis("off")
    table = ax.table(
        cellText=rows,
        colLabels=col_labels,
        cellLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.5)
    # 表头加底色
    for j in range(len(cols)):
        table[0, j].set_facecolor("#4472C4")
        table[0, j].set_text_props(color="white", fontweight="bold")
    ax.set_title(title[:50], fontsize=11, pad=15)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def _draw_scatter(data: list, title: str, save_path: Path):
    """散点图：X=第一个数值字段，Y=第二个数值字段，标签=公司名"""
    numeric_fields = _get_numeric_fields(data)
    if len(numeric_fields) < 2:
        raise ValueError("散点图需要至少两个数值字段")

    # 优先找营收和利润
    x_candidates = ["total_operating_revenue", "asset_total_assets"] + numeric_fields
    y_candidates = ["net_profit", "net_profit_10k_yuan", "operating_profit", "total_profit"] + numeric_fields
    x_field = next((f for f in x_candidates if f in numeric_fields), numeric_fields[0])
    y_field = next((f for f in y_candidates if f in numeric_fields and f != x_field), numeric_fields[1])

    xs = [_to_number(r.get(x_field)) for r in data]
    ys = [_to_number(r.get(y_field)) for r in data]
    labels = [str(r.get("stock_abbr") or r.get("stock_code") or "") for r in data]

    # 过滤 None
    valid = [(x, y, l) for x, y, l in zip(xs, ys, labels) if x is not None and y is not None]
    if not valid:
        raise ValueError("无有效数据点")
    xs, ys, labels = zip(*valid)

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.scatter(xs, ys, alpha=0.7, s=80)
    for x, y, label in zip(xs, ys, labels):
        ax.annotate(label, (x, y), textcoords="offset points", xytext=(5, 5), fontsize=8)

    ax.set_xlabel(_field_label(x_field), fontsize=10)
    ax.set_ylabel(_field_label(y_field), fontsize=10)
    ax.set_title(title[:50], fontsize=12)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: _fmt_val(v, x_field)))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: _fmt_val(v, y_field)))
    ax.grid(linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def _draw_line_multi(data: list, title: str, save_path: Path):
    """多公司时序折线图：每家公司一条线"""
    numeric_fields = _get_numeric_fields(data)
    if not numeric_fields:
        raise ValueError("无数值字段")

    plot_field = next((f for f in _PRIORITY_FIELDS if f in numeric_fields), numeric_fields[0])
    all_pct = _is_pct_field(plot_field)
    fmt = (lambda v, _: f"{v:.1f}%") if all_pct else (lambda v, _: _fmt_val(v, plot_field))

    # 按公司分组
    from collections import defaultdict
    company_data: dict[str, list] = defaultdict(list)
    for row in data:
        abbr = str(row.get("stock_abbr") or row.get("stock_code") or "未知")
        company_data[abbr].append(row)

    # 收集所有出现过的报告期并排序
    all_periods = sorted(
        {str(r.get("report_period", "")) for r in data if r.get("report_period")},
        key=_period_sort_key
    )
    if not all_periods:
        raise ValueError("无报告期数据")

    fig, ax = plt.subplots(figsize=(max(10, len(all_periods) * 1.0), 5))
    x = np.arange(len(all_periods))
    period_idx = {p: i for i, p in enumerate(all_periods)}

    for abbr, rows in list(company_data.items())[:8]:  # 最多8家公司
        period_val = {str(r.get("report_period", "")): _to_number(r.get(plot_field)) for r in rows}
        ys = [period_val.get(p) for p in all_periods]
        # 只画有数据的点
        valid_x = [x[i] for i, v in enumerate(ys) if v is not None]
        valid_y = [v for v in ys if v is not None]
        if valid_y:
            ax.plot(valid_x, valid_y, marker="o", label=abbr, linewidth=1.5, markersize=5)

    ax.set_xticks(x)
    ax.set_xticklabels(all_periods, rotation=30, ha="right", fontsize=8)
    ax.set_title(title[:50], fontsize=12)
    ax.legend(loc="best", fontsize=8, ncol=2)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(fmt))
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()

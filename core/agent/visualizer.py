# core/agent/visualizer.py

import logging
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

matplotlib.rcParams["font.family"] = ["WenQuanYi Micro Hei", "SimHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

logger = logging.getLogger(__name__)

RESULT_DIR = Path("./result")
RESULT_DIR.mkdir(parents=True, exist_ok=True)


def _to_number(v):
    """尝试转为数字，失败返回None"""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _detect_chart_type(question: str, data: list) -> str:
    """
    根据问题和数据自动判断图表类型
    返回: "line" | "bar" | "pie" | "table" | "none"
    """
    q = question.lower()

    if not data or len(data) == 0:
        return "none"

    # 趋势/变化/走势 → 折线图
    if any(
        k in q
        for k in ["趋势", "变化", "走势", "历年", "近几年", "历史", "环比", "同比变化"]
    ):
        return "line"

    # 对比/排名/top → 柱状图
    if any(k in q for k in ["对比", "比较", "排名", "top", "最高", "最低", "占比排"]):
        return "bar"

    # 占比/构成/分布 → 饼图
    if any(k in q for k in ["占比", "构成", "分布", "比重", "份额"]):
        return "pie"

    # 数据行数判断
    if len(data) >= 3:
        # 检查是否有时间序列字段
        first = data[0] if data else {}
        keys = list(first.keys())
        if any("period" in k or "year" in k or "date" in k for k in keys):
            return "line"
        return "bar"

    return "table"


def _get_numeric_fields(data: list) -> list:
    """从数据中找出数值型字段"""
    if not data:
        return []
    first = data[0]
    numeric = []
    skip = {"serial_number", "stock_code", "report_year"}
    for k, v in first.items():
        if k in skip:
            continue
        if _to_number(v) is not None:
            numeric.append(k)
    return numeric


def _get_label_field(data: list) -> str:
    """获取用于x轴/标签的字段"""
    if not data:
        return ""
    first = data[0]
    # 优先级：report_period > stock_abbr > 第一个字符串字段
    for preferred in ["report_period", "stock_abbr", "stock_code"]:
        if preferred in first:
            return preferred
    for k, v in first.items():
        if isinstance(v, str) and _to_number(v) is None:
            return k
    return list(first.keys())[0]


def draw_chart(
    question: str,
    sql_result: Any,
    problem_id: str,
    seq: int = 1,
) -> str:
    """
    根据问题和SQL结果自动绘图

    Args:
        question:   用户问题
        sql_result: SQL执行结果（list of dict）
        problem_id: 问题编号如 "B1002"
        seq:        图表序号

    Returns:
        图表相对路径，如 "./result/B1002_1.jpg"，失败返回 ""
    """
    if not isinstance(sql_result, list) or len(sql_result) == 0:
        return ""

    chart_type = _detect_chart_type(question, sql_result)
    if chart_type == "none":
        return ""

    save_path = RESULT_DIR / f"{problem_id}_{seq}.jpg"

    try:
        if chart_type == "line":
            _draw_line(sql_result, question, save_path)
        elif chart_type == "bar":
            _draw_bar(sql_result, question, save_path)
        elif chart_type == "pie":
            _draw_pie(sql_result, question, save_path)
        else:
            _draw_table(sql_result, question, save_path)

        logger.info(f"[Visualizer] 图表已保存: {save_path}")
        return f"./result/{problem_id}_{seq}.jpg"

    except Exception as e:
        logger.warning(f"[Visualizer] 绘图失败: {e}")
        return ""


def _draw_line(data: list, title: str, save_path: Path):
    label_field = _get_label_field(data)
    numeric_fields = _get_numeric_fields(data)
    if not numeric_fields:
        raise ValueError("无数值字段")

    # 优先选择营收/利润/核心指标
    priority = [
        "total_operating_revenue",
        "net_profit_10k_yuan",
        "net_profit",
        "operating_profit",
        "total_profit",
        "eps",
        "roe",
        "gross_profit_margin",
    ]
    plot_fields = [f for f in priority if f in numeric_fields] or numeric_fields[:3]

    labels = [str(row.get(label_field, "")) for row in data]
    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(10, 5))
    for field in plot_fields:
        values = [_to_number(row.get(field)) for row in data]
        values = [v if v is not None else 0 for v in values]
        ax.plot(x, values, marker="o", label=_field_label(field), linewidth=2)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_title(title[:40], fontsize=12)
    ax.legend(loc="best", fontsize=9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: _fmt_val(v)))
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def _draw_bar(data: list, title: str, save_path: Path):
    label_field = _get_label_field(data)
    numeric_fields = _get_numeric_fields(data)
    if not numeric_fields:
        raise ValueError("无数值字段")

    priority = [
        "total_operating_revenue",
        "net_profit_10k_yuan",
        "net_profit",
        "operating_profit",
        "total_profit",
    ]
    plot_fields = [f for f in priority if f in numeric_fields] or numeric_fields[:2]

    labels = [str(row.get(label_field, "")) for row in data]
    x = np.arange(len(labels))
    width = 0.8 / max(len(plot_fields), 1)

    fig, ax = plt.subplots(figsize=(max(10, len(labels) * 1.2), 5))
    for i, field in enumerate(plot_fields):
        values = [_to_number(row.get(field)) or 0 for row in data]
        offset = (i - len(plot_fields) / 2 + 0.5) * width
        bars = ax.bar(x + offset, values, width, label=_field_label(field), alpha=0.85)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_title(title[:40], fontsize=12)
    ax.legend(loc="best", fontsize=9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: _fmt_val(v)))
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def _draw_pie(data: list, title: str, save_path: Path):
    label_field = _get_label_field(data)
    numeric_fields = _get_numeric_fields(data)
    if not numeric_fields:
        raise ValueError("无数值字段")

    value_field = numeric_fields[0]
    labels = [str(row.get(label_field, "")) for row in data]
    values = [abs(_to_number(row.get(value_field)) or 0) for row in data]

    # 过滤掉0值
    pairs = [(l, v) for l, v in zip(labels, values) if v > 0]
    if not pairs:
        raise ValueError("无有效数值")
    labels, values = zip(*pairs)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.pie(
        values,
        labels=labels,
        autopct="%1.1f%%",
        startangle=90,
        pctdistance=0.85,
    )
    ax.set_title(title[:40], fontsize=12)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def _draw_table(data: list, title: str, save_path: Path):
    if not data:
        raise ValueError("空数据")

    # 最多显示15行
    display_data = data[:15]
    cols = list(display_data[0].keys())
    rows = [[str(row.get(c, "")) for c in cols] for row in display_data]

    fig, ax = plt.subplots(
        figsize=(max(12, len(cols) * 1.5), max(4, len(rows) * 0.5 + 1.5))
    )
    ax.axis("off")
    table = ax.table(
        cellText=rows,
        colLabels=[_field_label(c) for c in cols],
        cellLoc="center",
        loc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.4)
    ax.set_title(title[:40], fontsize=11, pad=15)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


# ========== 辅助函数 ==========
FIELD_LABELS = {
    "total_operating_revenue": "营业总收入",
    "net_profit_10k_yuan": "净利润",
    "net_profit": "净利润",
    "operating_profit": "营业利润",
    "total_profit": "利润总额",
    "eps": "每股收益",
    "roe": "净资产收益率(%)",
    "gross_profit_margin": "毛利率(%)",
    "net_profit_margin": "净利率(%)",
    "asset_total_assets": "总资产",
    "equity_total_equity": "股东权益",
    "operating_cf_net_amount": "经营现金流",
    "report_period": "报告期",
    "stock_abbr": "公司",
}


def _field_label(field: str) -> str:
    return FIELD_LABELS.get(field, field)


def _fmt_val(v: float) -> str:
    """数值格式化：万元→亿元"""
    if abs(v) >= 100000:
        return f"{v / 10000:.1f}亿"
    if abs(v) >= 10000:
        return f"{v / 10000:.2f}亿"
    return f"{v:.0f}万"

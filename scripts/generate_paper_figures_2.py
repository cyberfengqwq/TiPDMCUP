#!/usr/bin/env python3
"""
generate_paper_figures_2.py
论文第5章（研报知识库 & 系统评测）图表生成

  图5-10  知识库构成总览图（分组柱状图）
  图5-11  高频主题关键词统计图
  图5-12  多意图分布统计图
  图5-13  证据来源贡献图
  图5-14  可信度评分分布折线图
  表5-5   归因强度计算示例表
  表5-6   不同问题可信度评分与证据情况

运行方式（在项目根目录）：
    python generate_paper_figures_2.py
输出目录：./paper_figures/
"""

import json
import re
from collections import Counter
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager

# ─────────────────────────────────────────────────────────────────────────────
# 字体配置
# ─────────────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent
_FONT = _ROOT / "SimHei.ttf"
if _FONT.exists():
    font_manager.fontManager.addfont(str(_FONT))
    matplotlib.rcParams["font.family"] = ["SimHei", "DejaVu Sans"]
else:
    matplotlib.rcParams["font.family"] = [
        "WenQuanYi Micro Hei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
matplotlib.rcParams["axes.unicode_minus"] = False

OUT_DIR = _ROOT / "paper_figures"
OUT_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# 数据路径
# ─────────────────────────────────────────────────────────────────────────────
REPORT_META_FILE = _ROOT / "data" / "faiss_report_store" / "report_meta.json"
REPORT_MANIFEST = _ROOT / "data" / "faiss_report_store" / "report_manifest.json"
BATCH_RESULTS = _ROOT / "batch_results.json"

COLORS4 = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D"]
COLORS6 = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#3BB273", "#8E44AD"]

# ─────────────────────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────────────────────


def _load(path: Path) -> list | dict | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [WARN] 读取 {p.name} 失败: {e}")
        return None


def _save(fig: plt.Figure, name: str) -> None:
    out = OUT_DIR / name
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    kb = out.stat().st_size // 1024
    print(f"  ✓ {name:<46} ({kb} KB)")


def _three_line_table(
    ax: plt.Axes,
    rows: list,
    col_labels: list,
    header_color: str = "#2E86AB",
    alt_color: str = "#EAF4FB",
    font_size: int = 10,
    row_scale: float = 1.65,
) -> None:
    """在 ax 上绘制三线表风格表格。"""
    tbl = ax.table(cellText=rows, colLabels=col_labels, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(font_size)
    tbl.scale(1, row_scale)
    tbl.auto_set_column_width(list(range(len(col_labels))))

    n_r, n_c = len(rows), len(col_labels)
    for j in range(n_c):
        c = tbl[(0, j)]
        c.set_facecolor(header_color)
        c.set_text_props(color="white", fontweight="bold")
        c.set_edgecolor("white")
        c.set_linewidth(0)
    for i in range(1, n_r + 1):
        for j in range(n_c):
            tbl[(i, j)].set_facecolor(alt_color if i % 2 == 0 else "white")
            tbl[(i, j)].set_edgecolor("#D8D8D8")

    # 顶线 & 底线
    for y in (0.97, 0.03):
        ax.plot(
            [0, 1],
            [y, y],
            color="#333333",
            linewidth=1.8,
            transform=ax.transAxes,
            clip_on=False,
        )


def _kw_score(question: str, text: str) -> float:
    """问题与文本片段的中文词汇重叠率（Precision 侧）。"""
    q_words = set(re.findall(r"[\u4e00-\u9fff]{2,}", question))
    t_words = set(re.findall(r"[\u4e00-\u9fff]{2,}", text[:500]))
    if not q_words:
        return 0.0
    return len(q_words & t_words) / len(q_words)


# ═════════════════════════════════════════════════════════════════════════════
# 图5-10  知识库构成总览图
# ═════════════════════════════════════════════════════════════════════════════


def fig5_10() -> None:
    meta = _load(REPORT_META_FILE) or []
    manifest = _load(REPORT_MANIFEST) or {}

    stock_meta = [m for m in meta if m.get("report_type") == "stock"]
    ind_meta = [m for m in meta if m.get("report_type") == "industry"]

    # 文档数（来自 manifest 路径）
    n_stock_docs = len([k for k in manifest if "个股研报" in k])
    n_ind_docs = len([k for k in manifest if "行业研报" in k])

    # 估算总页数（每页约 800 汉字）
    CHARS_PER_PAGE = 800
    stock_chars = sum(len(m["text"]) for m in stock_meta)
    ind_chars = sum(len(m["text"]) for m in ind_meta)
    n_stock_pages = max(1, round(stock_chars / CHARS_PER_PAGE))
    n_ind_pages = max(1, round(ind_chars / CHARS_PER_PAGE))

    # 总文本量（万字）
    stock_wan = round(stock_chars / 10000, 1)
    ind_wan = round(ind_chars / 10000, 1)

    metric_names = ["文档数（篇）", "估算总页数（页）", "总文本量（万字）"]
    stock_vals = [n_stock_docs, n_stock_pages, stock_wan]
    ind_vals = [n_ind_docs, n_ind_pages, ind_wan]

    x = np.arange(len(metric_names))
    width = 0.36

    fig, ax = plt.subplots(figsize=(10, 5.5))
    bars1 = ax.bar(
        x - width / 2,
        stock_vals,
        width,
        label="个股研报",
        color="#2E86AB",
        edgecolor="white",
        zorder=3,
    )
    bars2 = ax.bar(
        x + width / 2,
        ind_vals,
        width,
        label="行业研报",
        color="#F18F01",
        edgecolor="white",
        zorder=3,
    )

    def _label(bars: list, vals: list) -> None:
        for b, v in zip(bars, vals):
            txt = f"{v:,}" if isinstance(v, int) else str(v)
            ax.text(
                b.get_x() + b.get_width() / 2,
                b.get_height() * 1.018,
                txt,
                ha="center",
                va="bottom",
                fontsize=10,
                fontweight="bold",
            )

    _label(bars1, stock_vals)
    _label(bars2, ind_vals)

    ax.set_xticks(x)
    ax.set_xticklabels(metric_names, fontsize=11)
    ax.set_title("图5-10  研报知识库构成总览", fontsize=14, pad=12)
    ax.set_ylabel("数值", fontsize=11)
    ax.legend(fontsize=11, loc="upper left")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    fig.tight_layout()
    _save(fig, "fig5_10_knowledge_base_overview.png")


# ═════════════════════════════════════════════════════════════════════════════
# 图5-11  高频主题关键词统计图
# ═════════════════════════════════════════════════════════════════════════════


def fig5_11() -> None:
    manifest = _load(REPORT_MANIFEST) or {}
    titles = list(manifest.keys())

    KEYWORDS = [
        "业绩",
        "创新",
        "行业",
        "增长",
        "集采",
        "承压",
        "提升",
        "研发",
        "利润",
        "出海",
        "收入",
        "改善",
        "估值",
        "分红",
    ]
    cnt: Counter = Counter()
    for title in titles:
        for kw in KEYWORDS:
            if kw in title:
                cnt[kw] += 1

    # 降序排列
    pairs = sorted(cnt.items(), key=lambda x: -x[1])
    labels = [p[0] for p in pairs]
    vals = [p[1] for p in pairs]

    # 渐变蓝色系
    cmap = plt.cm.get_cmap("Blues", len(labels) + 4)
    colors = [cmap(len(labels) - i + 3) for i in range(len(labels))]

    fig, ax = plt.subplots(figsize=(12, 5))
    bars = ax.bar(
        labels, vals, color=colors, edgecolor="white", linewidth=0.6, zorder=3
    )
    for b, v in zip(bars, vals):
        ax.text(
            b.get_x() + b.get_width() / 2,
            b.get_height() + max(vals) * 0.012,
            str(v),
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    ax.set_title(
        "图5-11  研报知识库高频主题关键词统计（按报告标题统计）", fontsize=14, pad=12
    )
    ax.set_xlabel("关键词", fontsize=11)
    ax.set_ylabel("出现频次（篇次）", fontsize=11)
    ax.set_ylim(0, max(vals) * 1.18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    fig.tight_layout()
    _save(fig, "fig5_11_top_keywords.png")


# ═════════════════════════════════════════════════════════════════════════════
# 图5-12  多意图分布统计图
# ═════════════════════════════════════════════════════════════════════════════

# 意图关键词规则（优先级从上到下）
_INTENT_RULES: list[tuple[str, list[str]]] = [
    ("排名查询\n(rank)", ["排名", "最高", "最低", "前几", "第一", "榜首", "哪家最"]),
    (
        "趋势分析\n(trend)",
        ["趋势", "变化", "走势", "历年", "近几年", "同比", "环比", "年度变"],
    ),
    ("对比分析\n(compare)", ["对比", "比较", "相比", "差异", "哪个", "两者", "vs"]),
    ("原因分析\n(explain)", ["为什么", "原因", "影响", "因素", "如何", "分析原因"]),
    ("综合总结\n(summarize)", ["总结", "综合", "整体", "全面", "概述", "综述"]),
    ("单点查询\n(lookup)", []),  # 兜底
]


def _classify_intent(question: str) -> str:
    q = question.lower()
    for intent, kws in _INTENT_RULES:
        if kws and any(kw in q for kw in kws):
            return intent
    return "单点查询\n(lookup)"


def fig5_12() -> None:
    batch = _load(BATCH_RESULTS) or []

    cnt: Counter = Counter()
    for r in batch:
        cnt[_classify_intent(r.get("question", ""))] += 1

    # 按规则顺序输出，保证顺序固定
    labels = [intent for intent, _ in _INTENT_RULES]
    vals = [cnt.get(lb, 0) for lb in labels]

    fig, ax = plt.subplots(figsize=(12, 5))
    bars = ax.bar(labels, vals, color=COLORS6, edgecolor="white", width=0.55, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(
            b.get_x() + b.get_width() / 2,
            b.get_height() + 0.2,
            str(v),
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
        )

    ax.set_title("图5-12  测试问题多意图类型分布统计", fontsize=14, pad=12)
    ax.set_xlabel("意图类型", fontsize=11)
    ax.set_ylabel("出现次数", fontsize=11)
    ax.set_ylim(0, max(vals) * 1.25 if vals else 10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    fig.tight_layout()
    _save(fig, "fig5_12_intent_distribution.png")


# ═════════════════════════════════════════════════════════════════════════════
# 图5-13  证据来源贡献图
# ═════════════════════════════════════════════════════════════════════════════


def fig5_13() -> None:
    meta = _load(REPORT_META_FILE) or []
    batch = _load(BATCH_RESULTS) or []

    # 为加速，取前 200 个 chunk 做代表性匹配
    stock_sample = [m for m in meta if m.get("report_type") == "stock"][:200]
    ind_sample = [m for m in meta if m.get("report_type") == "industry"][:200]

    THRESHOLD = 0.12  # 有效命中最低得分

    stock_hits = 0
    ind_hits = 0
    both_hits = 0
    total = len(batch)

    for r in batch:
        q = r.get("question", "")
        best_s = max((_kw_score(q, m["text"]) for m in stock_sample), default=0.0)
        best_i = max((_kw_score(q, m["text"]) for m in ind_sample), default=0.0)
        hit_s = best_s >= THRESHOLD
        hit_i = best_i >= THRESHOLD
        if hit_s:
            stock_hits += 1
        if hit_i:
            ind_hits += 1
        if hit_s and hit_i:
            both_hits += 1

    labels = ["个股研报\n有效命中", "行业研报\n有效命中", "双侧均\n有效命中"]
    vals = [stock_hits, ind_hits, both_hits]
    colors = ["#2E86AB", "#F18F01", "#3BB273"]

    fig, ax = plt.subplots(figsize=(8, 5.5))
    bars = ax.bar(labels, vals, color=colors, width=0.42, edgecolor="white", zorder=3)
    for b, v in zip(bars, vals):
        pct = v / max(total, 1) * 100
        ax.text(
            b.get_x() + b.get_width() / 2,
            b.get_height() + 0.4,
            f"{v}  ({pct:.0f}%)",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )

    ax.set_title("图5-13  研报证据来源对问题的有效命中贡献", fontsize=14, pad=12)
    ax.set_xlabel("证据来源", fontsize=11)
    ax.set_ylabel(f"有效命中问题数（共 {total} 题）", fontsize=11)
    ax.set_ylim(0, total * 1.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
    fig.tight_layout()
    _save(fig, "fig5_13_evidence_source_contribution.png")


# ═════════════════════════════════════════════════════════════════════════════
# 可信度评分计算（供 图5-14 & 表5-6 复用）
# ═════════════════════════════════════════════════════════════════════════════


def _compute_confidence(
    record: dict,
    stock_sample: list,
    ind_sample: list,
) -> dict:
    """
    四维可信度评分：
      DataSup  (0-40): SQL 是否返回有效、无空值的结果
      TextSup  (0-30): 研报关键词命中得分
      Cons     (0-20): 数据内部一致性（无 null、结果≥1行）
      Attr     (0-10): 溯源质量奖励（SQL 被修正则扣分）
      Total    (0-100): 四项之和，上限 100
    """
    q = record.get("question", "")
    sql_result = record.get("sql_result") or []
    sql = record.get("sql", "")
    corrected = record.get("sql_corrected", False)

    # ── DataSup ───────────────────────────────────────────────
    if isinstance(sql_result, list) and len(sql_result) > 0:
        non_null = sum(
            1
            for row in sql_result
            for v in (row.values() if isinstance(row, dict) else [row])
            if v is not None
        )
        data_sup = min(40, 18 + non_null * 4)
    elif sql and sql.strip().upper().startswith(("SELECT", "WITH")):
        data_sup = 8
    else:
        data_sup = 0

    # ── TextSup ───────────────────────────────────────────────
    best_s = max((_kw_score(q, m["text"]) for m in stock_sample), default=0.0)
    best_i = max((_kw_score(q, m["text"]) for m in ind_sample), default=0.0)
    text_sup = min(30, round(max(best_s, best_i) * 115))

    # ── Cons ──────────────────────────────────────────────────
    if isinstance(sql_result, list) and len(sql_result) > 0:
        null_cnt = sum(
            1
            for row in sql_result
            for v in (row.values() if isinstance(row, dict) else [row])
            if v is None
        )
        cons = max(0, 20 - null_cnt * 4)
    else:
        cons = 0

    # ── Attr ──────────────────────────────────────────────────
    attr = 6 if not corrected else 2
    if data_sup >= 30:
        attr = min(10, attr + 2)

    total = min(100, data_sup + text_sup + cons + attr)
    return {
        "data_sup": data_sup,
        "text_sup": text_sup,
        "cons": cons,
        "attr": attr,
        "total": total,
    }


def _confidence_level(score: int) -> str:
    if score >= 80:
        return "高"
    if score >= 60:
        return "中"
    if score >= 40:
        return "低"
    return "极低"


# ═════════════════════════════════════════════════════════════════════════════
# 图5-14  可信度评分分布折线图
# ═════════════════════════════════════════════════════════════════════════════


def fig5_14(scores: list[dict]) -> None:
    if not scores:
        print("  [WARN] 图5-14：无评分数据，跳过")
        return

    totals = [s["total"] for s in scores]
    x = list(range(1, len(totals) + 1))

    # 按等级着色散点
    point_colors = []
    for t in totals:
        if t >= 80:
            point_colors.append("#3BB273")
        elif t >= 60:
            point_colors.append("#F18F01")
        elif t >= 40:
            point_colors.append("#C73E1D")
        else:
            point_colors.append("#AAAAAA")

    fig, ax = plt.subplots(figsize=(13, 5))

    ax.fill_between(x, totals, alpha=0.10, color="#2E86AB")
    ax.plot(x, totals, "-", linewidth=1.6, color="#2E86AB", alpha=0.65, zorder=2)
    ax.scatter(
        x, totals, c=point_colors, s=60, zorder=4, edgecolors="white", linewidths=0.9
    )

    # 参考线
    for thresh, lbl, clr in [
        (80, "高可信 (≥80)", "#3BB273"),
        (60, "中可信 (≥60)", "#F18F01"),
        (40, "低可信 (≥40)", "#C73E1D"),
    ]:
        ax.axhline(
            thresh, linestyle="--", linewidth=1.2, color=clr, alpha=0.85, label=lbl
        )

    avg = float(np.mean(totals))
    ax.axhline(
        avg,
        linestyle=":",
        linewidth=1.5,
        color="#2E86AB",
        label=f"均分 {avg:.1f}",
        zorder=3,
    )

    ax.set_title("图5-14  各测试问题可信度评分分布", fontsize=14, pad=12)
    ax.set_xlabel("问题编号", fontsize=11)
    ax.set_ylabel("可信度评分（0 – 100）", fontsize=11)
    ax.set_ylim(-5, 115)
    ax.set_xlim(0, len(totals) + 1)
    ax.legend(fontsize=9, loc="lower right", ncol=2, framealpha=0.85)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.30)
    fig.tight_layout()
    _save(fig, "fig5_14_confidence_overview.png")


# ═════════════════════════════════════════════════════════════════════════════
# 表5-5  归因强度计算示例表
# ═════════════════════════════════════════════════════════════════════════════


def table5_5() -> None:
    """
    固定示例：展示四维度评分方法论。
    DataSup(0-40)  TextSup(0-30)  Cons(0-20)  Attr(0-10)  总分
    """
    rows = [
        ["金花股份2023年净利润", "38", "22", "20", "8", "88（高）"],
        ["云南白药近三年营收趋势", "40", "26", "18", "10", "94（高）"],
        ["同仁堂总资产对比行业均值", "32", "18", "16", "7", "73（中）"],
        ["太安堂研发投入占比情况", "20", "14", "12", "6", "52（低）"],
        ["某公司2025Q3净利润（无数据）", "8", "8", "0", "2", "18（极低）"],
    ]
    col_labels = ["问题示例", "DataSup", "TextSup", "Cons", "Attr", "总分（等级）"]

    fig, ax = plt.subplots(figsize=(14, 5.5))
    ax.axis("off")
    ax.set_title(
        "表5-5  归因强度四维度评分计算示例", fontsize=13, fontweight="bold", pad=10
    )
    _three_line_table(
        ax,
        rows,
        col_labels,
        header_color="#2E86AB",
        alt_color="#EAF4FB",
        font_size=10,
        row_scale=1.75,
    )
    fig.tight_layout()
    _save(fig, "table5_5_attribution_strength.png")


# ═════════════════════════════════════════════════════════════════════════════
# 表5-6  不同问题可信度评分与证据情况
# ═════════════════════════════════════════════════════════════════════════════


def table5_6(scores: list[dict], batch: list[dict]) -> None:
    if not scores or not batch:
        print("  [WARN] 表5-6：无数据，跳过")
        return

    meta = _load(REPORT_META_FILE) or []
    stock_s = [m for m in meta if m.get("report_type") == "stock"][:300]
    ind_s = [m for m in meta if m.get("report_type") == "industry"][:300]

    # 按可信度等级各选代表：高2、中3、低3、极低2（共10条）
    buckets: dict[str, list[int]] = {"高": [], "中": [], "低": [], "极低": []}
    for i, s in enumerate(scores):
        lv = _confidence_level(s["total"])
        buckets[lv].append(i)

    sample_idx: list[int] = []
    for lv, quota in [("高", 2), ("中", 3), ("低", 3), ("极低", 2)]:
        sample_idx.extend(buckets[lv][:quota])

    # 不足 10 条时补全
    for i in range(len(batch)):
        if i not in sample_idx and len(sample_idx) < 10:
            sample_idx.append(i)

    # 构建表格行
    rows = []
    for idx in sample_idx[:10]:
        r = batch[idx]
        s = scores[idx]
        q_raw = r.get("question", "")
        q_short = q_raw[:16] + ("…" if len(q_raw) > 16 else "")
        best_s = max((_kw_score(q_raw, m["text"]) for m in stock_s), default=0.0)
        best_i = max((_kw_score(q_raw, m["text"]) for m in ind_s), default=0.0)
        dual = "√" if (best_s >= 0.12 and best_i >= 0.12) else "×"
        lv = _confidence_level(s["total"])
        rows.append(
            [
                q_short,
                f"{best_s:.3f}",
                f"{best_i:.3f}",
                dual,
                str(s["total"]),
                lv,
            ]
        )

    col_labels = [
        "问题简述",
        "个股证据\nTop1得分",
        "行业证据\nTop1得分",
        "双侧覆盖",
        "最终得分",
        "可信度等级",
    ]

    fig, ax = plt.subplots(figsize=(14, 7.5))
    ax.axis("off")
    ax.set_title(
        "表5-6  不同问题可信度评分与证据覆盖情况",
        fontsize=13,
        fontweight="bold",
        pad=10,
    )
    _three_line_table(
        ax,
        rows,
        col_labels,
        header_color="#A23B72",
        alt_color="#F9F0F5",
        font_size=9.5,
        row_scale=1.7,
    )
    fig.tight_layout()
    _save(fig, "table5_6_confidence_evidence.png")


# ═════════════════════════════════════════════════════════════════════════════
# 主流程
# ═════════════════════════════════════════════════════════════════════════════


def main() -> None:
    print("=" * 66)
    print("  论文第5章图表生成器（Part 2） — generate_paper_figures_2.py")
    print("=" * 66)

    # 预加载公共数据
    meta = _load(REPORT_META_FILE) or []
    batch = _load(BATCH_RESULTS) or []
    stock_meta = [m for m in meta if m.get("report_type") == "stock"]
    ind_meta = [m for m in meta if m.get("report_type") == "industry"]

    print(f"\n  研报 meta: 个股 {len(stock_meta)} chunk, 行业 {len(ind_meta)} chunk")
    print(f"  batch_results: {len(batch)} 条问题")
    print(f"  输出目录: {OUT_DIR}\n")

    print("── 图5-10  知识库构成总览图")
    fig5_10()

    print("── 图5-11  高频主题关键词统计图")
    fig5_11()

    print("── 图5-12  多意图分布统计图")
    fig5_12()

    print("── 图5-13  证据来源贡献图（检索中，稍候…）")
    fig5_13()

    print("── 计算各题可信度评分…")
    stock_s = stock_meta[:500]
    ind_s = ind_meta[:500]
    scores = [_compute_confidence(r, stock_s, ind_s) for r in batch]
    if scores:
        avg = np.mean([s["total"] for s in scores])
        dist = Counter(_confidence_level(s["total"]) for s in scores)
        print(f"  平均分: {avg:.1f}  分布: {dict(dist)}")

    print("── 图5-14  可信度评分分布折线图")
    fig5_14(scores)

    print("── 表5-5  归因强度计算示例表")
    table5_5()

    print("── 表5-6  不同问题可信度评分与证据情况")
    table5_6(scores, batch)

    print("\n" + "=" * 66)
    print(f"  ✅ 全部完成！  输出目录：{OUT_DIR}")
    print("=" * 66)
    print("\n新生成文件：")
    targets = sorted(OUT_DIR.glob("fig5_1[0-9]*.png")) + sorted(
        OUT_DIR.glob("table5_[56]*.png")
    )
    for f in targets:
        kb = f.stat().st_size // 1024
        print(f"  {f.name:<48}  {kb:>5} KB")
    print()


if __name__ == "__main__":
    main()

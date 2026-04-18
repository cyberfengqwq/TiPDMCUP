"""
json_to_csv_v2.py

针对 report_period=null、metric_std 为英文键名、statement=core_indicator 的 JSON 结构。

特点：
  - report_period 为 null 时，从 time_role（年份字符串）推断报告期
  - metric_std 直接是英文列名，无需中文映射
  - 同一字段多个 table_title 重复时，按优先级去重
  - 单位为"元"时自动换算为万元（附件3要求）
  - 一家公司一个文件夹，文件夹内4张CSV（无数据的表不生成）

用法：
  python json_to_csv_v2.py --input ./json_data --output ./output
"""

import argparse
import json
import logging
import re
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# 附件3 四张表的列定义（完整列名、顺序与附件3完全一致）
# ══════════════════════════════════════════════════════════════════════════════
COLS_CORE = [
    "serial_number", "stock_code", "stock_abbr",
    "eps",
    "total_operating_revenue",
    "operating_revenue_yoy_growth",
    "operating_revenue_qoq_growth",
    "net_profit_10k_yuan",
    "net_profit_yoy_growth",
    "net_profit_qoq_growth",
    "net_asset_per_share",
    "roe",
    "operating_cf_per_share",
    "net_profit_excl_non_recurring",
    "net_profit_excl_non_recurring_yoy",
    "gross_profit_margin",
    "net_profit_margin",
    "roe_weighted_excl_non_recurring",
    "report_period", "report_year",
]

COLS_BALANCE = [
    "serial_number", "stock_code", "stock_abbr",
    "asset_cash_and_cash_equivalents",
    "asset_accounts_receivable",
    "asset_inventory",
    "asset_trading_financial_assets",
    "asset_construction_in_progress",
    "asset_total_assets",
    "asset_total_assets_yoy_growth",
    "liability_accounts_payable",
    "liability_advance_from_customers",
    "liability_total_liabilities",
    "liability_total_liabilities_yoy_growth",
    "liability_contract_liabilities",
    "liability_short_term_loans",
    "asset_liability_ratio",
    "equity_unappropriated_profit",
    "equity_total_equity",
    "report_period", "report_year",
]

COLS_INCOME = [
    "serial_number", "stock_code", "stock_abbr",
    "net_profit",
    "net_profit_yoy_growth",
    "other_income",
    "total_operating_revenue",
    "operating_revenue_yoy_growth",
    "operating_expense_cost_of_sales",
    "operating_expense_selling_expenses",
    "operating_expense_administrative_expenses",
    "operating_expense_financial_expenses",
    "operating_expense_rnd_expenses",
    "operating_expense_taxes_and_surcharges",
    "total_operating_expenses",
    "operating_profit",
    "total_profit",
    "asset_impairment_loss",
    "credit_impairment_loss",
    "report_period", "report_year",
]

COLS_CASHFLOW = [
    "serial_number", "stock_code", "stock_abbr",
    "net_cash_flow",
    "net_cash_flow_yoy_growth",
    "operating_cf_net_amount",
    "operating_cf_ratio_of_net_cf",
    "operating_cf_cash_from_sales",
    "investing_cf_net_amount",
    "investing_cf_ratio_of_net_cf",
    "investing_cf_cash_for_investments",
    "investing_cf_cash_from_investment_recovery",
    "financing_cf_cash_from_borrowing",
    "financing_cf_cash_for_debt_repayment",
    "financing_cf_net_amount",
    "financing_cf_ratio_of_net_cf",
    "report_period", "report_year",
]

# 所有合法列名的集合（用于快速判断 metric_std 是否直接可用）
ALL_VALID_COLS: set[str] = set(
    COLS_CORE + COLS_BALANCE + COLS_INCOME + COLS_CASHFLOW
)

# 每张表的列集合（用于归属判断）
TABLE_COL_SET: dict[str, set[str]] = {
    "core":     set(COLS_CORE),
    "balance":  set(COLS_BALANCE),
    "income":   set(COLS_INCOME),
    "cashflow": set(COLS_CASHFLOW),
}

# ══════════════════════════════════════════════════════════════════════════════
# metric_std 别名映射（处理与附件3列名不一致的情况）
# ══════════════════════════════════════════════════════════════════════════════
ALIAS_MAP: dict[str, str] = {
    # ── core 表 ──────────────────────────────────────────────────────────────
    "basic_eps":                            "eps",
    "diluted_eps":                          "eps",
    # core 表的净利润列名是 net_profit_10k_yuan，而 income 表是 net_profit
    # 归属判断由 TABLE_COL_SET 决定，这里统一先映射到 net_profit_10k_yuan
    "net_profit":                           "net_profit_10k_yuan",

    # ── balance 表 ───────────────────────────────────────────────────────────
    "cash":                                 "asset_cash_and_cash_equivalents",
    "total_assets":                         "asset_total_assets",
    "total_liabilities":                    "liability_total_liabilities",
    "total_equity":                         "equity_total_equity",
    "retained_earnings":                    "equity_unappropriated_profit",
    "undistributed_profit":                 "equity_unappropriated_profit",
    "accounts_receivable":                  "asset_accounts_receivable",
    "inventory":                            "asset_inventory",
    "trading_financial_assets":             "asset_trading_financial_assets",
    "construction_in_progress":             "asset_construction_in_progress",
    "short_term_borrowings":                "liability_short_term_loans",
    "accounts_payable":                     "liability_accounts_payable",
    "contract_liabilities":                 "liability_contract_liabilities",

    # ── income 表 ────────────────────────────────────────────────────────────
    "revenue":                              "total_operating_revenue",
    "cost_of_revenue":                      "operating_expense_cost_of_sales",
    "selling_expenses":                     "operating_expense_selling_expenses",
    "general_and_administrative_expenses":  "operating_expense_administrative_expenses",
    "r_and_d_expenses":                     "operating_expense_rnd_expenses",
    "financial_expenses":                   "operating_expense_financial_expenses",
    "taxes_and_surcharges":                 "operating_expense_taxes_and_surcharges",

    # ── cashflow 表 ──────────────────────────────────────────────────────────
    "net_cash_flow":                        "net_cash_flow",
}

# ── JSON statement → 表键 ─────────────────────────────────────────────────────
STMT_TO_KEY: dict[str, str] = {
    "core_indicator":  "core",
    "balance_sheet":   "balance",
    "income_sheet":    "income",
    "cash_flow_sheet": "cashflow",
}

# ── table_title 优先级（数字越小优先级越高）────────────────────────────────────
TITLE_PRIORITY: dict[str, int] = {
    "近3年的主要会计数据和财务指标":       1,
    "报告期分季度的主要会计数据":           2,
    "季度数据与已披露定期报告数据差异说明": 3,
}


def _title_pri(title: str) -> int:
    return TITLE_PRIORITY.get(str(title), 99)


# ── 报告期归一化 ──────────────────────────────────────────────────────────────
_PERIOD_NORM: dict[str, str] = {
    # English
    "annual": "FY", "fy": "FY", "full_year": "FY",
    "quarter_q4": "FY", "q4": "FY", "year": "FY",
    "quarter_q1": "Q1", "q1": "Q1",
    "half_year": "HY", "hy": "HY", "h1": "HY", "semi_annual": "HY", "q2": "HY",
    "quarter_q3": "Q3", "q3": "Q3",
    # 中文
    "年度": "FY", "年报": "FY", "全年": "FY",
    "一季度": "Q1", "一季报": "Q1",
    "半年度": "HY", "半年报": "HY", "中报": "HY",
    "三季度": "Q3", "三季报": "Q3",
}


# 这些列按赛题要求保留元单位，不转换为万元
_KEEP_YUAN_COLS: set[str] = {"net_cash_flow"}


def _period_code(s: str) -> str | None:
    """将任意格式字符串解析为 FY/Q1/HY/Q3，失败返回 None"""
    # 剥掉年份前缀，如 "2023Q1" → "Q1"
    m = re.match(r"\d{4}(.+)", s.strip())
    if m:
        s = m.group(1)
    return _PERIOD_NORM.get(s.strip().lower()) or _PERIOD_NORM.get(s.strip())


def infer_period_code(report_period, time_role: str) -> str:
    """返回纯 period code：FY / Q1 / HY / Q3"""
    if report_period:
        code = _period_code(str(report_period))
        if code:
            return code
        su = str(report_period).strip().upper()
        if su in ("FY", "Q1", "HY", "Q3"):
            return su

    t = str(time_role).strip()
    m = re.search(r"[Qq]([123])", t)
    if m:
        return {"1": "Q1", "2": "HY", "3": "Q3"}[m.group(1)]
    if re.fullmatch(r"\d{4}", t):
        return "FY"
    for kw, code in [("三季", "Q3"), ("q3", "Q3"), ("一季", "Q1"), ("q1", "Q1"),
                     ("半年", "HY"), ("hy", "HY"), ("h1", "HY")]:
        if kw in t.lower():
            return code
    return "FY"


def infer_year(report_year, time_role: str) -> int | str:
    if report_year is not None:
        try:
            return int(report_year)
        except (TypeError, ValueError):
            pass
    t = str(time_role).strip()
    m = re.match(r"(\d{4})", t)
    return int(m.group(1)) if m else ""


def to_wan(value, unit: str, col: str = ""):
    """元 → 万元；百分比、比率、指定列不转换"""
    if value is None:
        return None
    if col in _KEEP_YUAN_COLS:
        return value
    if str(unit).strip() in ("元", "人民币元", "CNY", "RMB"):
        try:
            return round(float(value) / 10000, 4)
        except (TypeError, ValueError):
            return value
    return value


def resolve_col(metric_std: str) -> str | None:
    """
    将 metric_std 解析为 CSV 目标列名：
    1. 直接是合法列名 → 直接用
    2. 在 ALIAS_MAP → 映射
    3. 无法识别 → None
    """
    if metric_std in ALL_VALID_COLS:
        return metric_std
    return ALIAS_MAP.get(metric_std)


def find_table(col: str, preferred_key: str) -> str:
    """
    根据列名确定归属表。
    优先用 preferred_key（来自 statement 字段），
    如果该列不在 preferred_key 对应的表里，则遍历其他表。
    特殊处理：net_profit_10k_yuan 只属于 core；net_profit 只属于 income。
    """
    if col in TABLE_COL_SET.get(preferred_key, set()):
        return preferred_key
    for tk, col_set in TABLE_COL_SET.items():
        if col in col_set:
            return tk
    return preferred_key


# ══════════════════════════════════════════════════════════════════════════════
# 解析单个 JSON 文件
# ══════════════════════════════════════════════════════════════════════════════

def parse_file(path: Path) -> dict:
    """
    返回结构：
    {
      "meta":     {stock_code, stock_abbr, report_year, report_period},
      "core":     {col: value} 或 None,
      "balance":  {col: value} 或 None,
      "income":   {col: value} 或 None,
      "cashflow": {col: value} 或 None,
    }
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"[跳过] {path.name}: {e}")
        return {}

    facts = data.get("facts", [])
    if not isinstance(facts, list) or not facts:
        return {}

    stock_code = str(data.get("stock_code", "")).strip()
    stock_abbr = str(data.get("stock_abbr", "")).strip()

    # 用第一条 fact 的 time_role 辅助推断
    first_time_role = str(facts[0].get("time_role", "")) if facts else ""
    report_year   = infer_year(data.get("report_year"), first_time_role)
    period_code   = infer_period_code(data.get("report_period"), first_time_role)
    report_period = f"{report_year}{period_code}" if report_year else period_code

    meta = {
        "stock_code":    stock_code,
        "stock_abbr":    stock_abbr,
        "report_year":   report_year,
        "report_period": report_period,
    }

    # buffers[table_key][col] = (value, priority)
    buffers: dict[str, dict[str, tuple]] = {
        "core": {}, "balance": {}, "income": {}, "cashflow": {}
    }
    unmapped: set[str] = set()

    for fact in facts:
        if not isinstance(fact, dict):
            continue

        stmt         = fact.get("statement", "")
        preferred_tk = STMT_TO_KEY.get(stmt)
        if preferred_tk is None:
            continue

        metric_std   = str(fact.get("metric_std",  "")).strip()
        metric_alias = str(fact.get("metric_alias", "")).strip()
        value        = fact.get("value")
        unit         = str(fact.get("unit", ""))
        table_title  = fact.get("table_title", "")
        priority     = _title_pri(table_title)

        # 解析目标列名
        col = resolve_col(metric_std) or resolve_col(metric_alias)
        # core_indicator 语境下 net_profit → net_profit_10k_yuan
        if col == "net_profit" and preferred_tk == "core":
            col = "net_profit_10k_yuan"
        if not col:
            unmapped.add(metric_std)
            continue

        # 确定归属表
        tk = find_table(col, preferred_tk)

        # 单位换算
        converted = to_wan(value, unit, col)

        # 优先级去重（priority 数字小的优先）
        existing = buffers[tk].get(col)
        if existing is None or priority < existing[1]:
            buffers[tk][col] = (converted, priority)

    if unmapped:
        logger.debug(f"[{path.name}] 未映射字段({len(unmapped)}): {sorted(unmapped)[:8]}")

    # 组装 row
    COLS_MAP = {
        "core":     COLS_CORE,
        "balance":  COLS_BALANCE,
        "income":   COLS_INCOME,
        "cashflow": COLS_CASHFLOW,
    }
    SKIP = {"serial_number", "stock_code", "stock_abbr", "report_period", "report_year"}

    result = {"meta": meta}
    for tk, cols in COLS_MAP.items():
        row = {c: None for c in cols}
        row.update(meta)
        for col, (val, _) in buffers[tk].items():
            if col in row:
                row[col] = val

        has_data = any(row.get(c) is not None for c in cols if c not in SKIP)
        result[tk] = row if has_data else None

    return result


# ══════════════════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════════════════

TABLE_META = {
    "core":     ("core_performance_indicators_sheet.csv", COLS_CORE),
    "balance":  ("balance_sheet.csv",                     COLS_BALANCE),
    "income":   ("income_sheet.csv",                      COLS_INCOME),
    "cashflow": ("cash_flow_sheet.csv",                   COLS_CASHFLOW),
}


def _load_abbr_map(project_root: Path) -> dict[str, str]:
    """从附件1加载 股票代码 → A股简称 的权威映射"""
    xlsx = project_root / "示例数据" / "附件1：中药上市公司基本信息（截至到2025年12月22日）.xlsx"
    if not xlsx.exists():
        return {}
    try:
        import openpyxl
        wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
        ws = wb.active
        mapping: dict[str, str] = {}
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                continue  # 跳过表头
            code, abbr = str(row[1]).strip(), str(row[2]).strip()
            if code and abbr:
                mapping[code] = abbr
        return mapping
    except Exception as e:
        logger.warning(f"附件1加载失败: {e}")
        return {}


def run(input_dir: Path, output_dir: Path, project_root: Path | None = None):
    output_dir.mkdir(parents=True, exist_ok=True)

    abbr_map = _load_abbr_map(project_root or input_dir.parent.parent.parent.parent)

    json_files = sorted(input_dir.rglob("*.json"))
    if not json_files:
        logger.error(f"在 {input_dir} 下未找到任何 JSON 文件")
        return

    logger.info(f"共找到 {len(json_files)} 个 JSON 文件，附件1映射 {len(abbr_map)} 家公司")

    # company_data[stock_code][tk] = [row, ...]  —— 以 stock_code 为 key 避免简称不同导致分裂
    company_data: dict[str, dict[str, list]] = {}
    code_to_folder: dict[str, str] = {}  # stock_code → 最终 folder 名

    for path in json_files:
        result = parse_file(path)
        if not result:
            continue

        meta       = result["meta"]
        stock_code = meta["stock_code"]
        # 用附件1权威简称，没有则用提取到的简称
        stock_abbr = abbr_map.get(stock_code) or meta["stock_abbr"]
        meta["stock_abbr"] = stock_abbr
        # 同步更新所有 row 里的 stock_abbr
        for tk in TABLE_META:
            if result.get(tk):
                result[tk]["stock_abbr"] = stock_abbr

        folder = f"{stock_code}_{stock_abbr}" if stock_abbr else stock_code
        code_to_folder[stock_code] = folder

        if stock_code not in company_data:
            company_data[stock_code] = {k: [] for k in TABLE_META}

        for tk in TABLE_META:
            row = result.get(tk)
            if not row:
                continue
            key = (row.get("report_year"), row.get("report_period"))
            existing = next(
                (r for r in company_data[stock_code][tk]
                 if (r.get("report_year"), r.get("report_period")) == key),
                None,
            )
            if existing is None:
                company_data[stock_code][tk].append(row)
            else:
                for col, val in row.items():
                    if val is not None and existing.get(col) is None:
                        existing[col] = val

        logger.info(
            f"  {path.name} → {stock_code} {stock_abbr} "
            f"[{meta['report_year']} {meta['report_period']}]"
        )

    logger.info(f"共 {len(company_data)} 家公司，输出 CSV...")

    for code, tables in sorted(company_data.items()):
        folder = code_to_folder.get(code, code)
        company_dir = output_dir / folder
        company_dir.mkdir(parents=True, exist_ok=True)

        written = []
        for tk, (fname, cols) in TABLE_META.items():
            rows = tables[tk]
            if not rows:
                continue
            df = pd.DataFrame(rows, columns=cols)
            df.sort_values(["report_year", "report_period"],
                           inplace=True, ignore_index=True)
            df["serial_number"] = range(1, len(df) + 1)
            df.to_csv(company_dir / fname, index=False, encoding="utf-8-sig")
            written.append(f"{fname}({len(df)}行)")

        logger.info(f"  [{folder}] " + "  ".join(written))

    logger.info(f"完成 ✓  输出: {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="JSON财报 → 4张CSV（v2）")
    parser.add_argument("--input",  default="./json_data", help="JSON文件夹路径")
    parser.add_argument("--output", default="./output",    help="CSV输出文件夹")
    args = parser.parse_args()
    run(Path(args.input), Path(args.output))


if __name__ == "__main__":
    main()
"""
fill_derived.py — 为 output/ 下所有公司的 CSV 填充可计算的派生列

原则：
  - 只填写当前为空的格，不覆盖已有值
  - 计算公式与原始数据保持单位一致（全部已是万元或百分比）
  - net_cash_flow 在 schema 里标注为"元"，但 CF 分项为"万元"；
    占比统一用三分项之和作分母，保证内部一致且总和 = 100%

运行：
  python core/data_extract/fill_derived.py          # 处理默认 output/ 目录
  python core/data_extract/fill_derived.py --dir /path/to/output
"""

import argparse
import csv
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════════════════════════════════

def _f(v) -> float | None:
    """字符串 → float，空值返回 None"""
    if v in (None, "", "None", "null", "NaN", "nan"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pct(num, den, digits=2) -> str | None:
    """num / den × 100，保留 digits 位小数；分母为 0 或缺失返回 None"""
    n, d = _f(num), _f(den)
    if n is None or d is None or d == 0:
        return None
    return str(round(n / d * 100, digits))


def _growth(curr, prev, digits=2) -> str | None:
    """(curr - prev) / |prev| × 100"""
    c, p = _f(curr), _f(prev)
    if c is None or p is None or p == 0:
        return None
    return str(round((c - p) / abs(p) * 100, digits))


def _sum_notnull(*vals) -> float | None:
    """对非空值求和；全部为空则返回 None"""
    nums = [_f(v) for v in vals]
    notnull = [x for x in nums if x is not None]
    return sum(notnull) if notnull else None


def _fill(row: dict, col: str, val) -> None:
    """只在列为空时填入值"""
    if val is not None and row.get(col, "") in ("", None, "None", "null", "NaN"):
        row[col] = val


# ════════════════════════════════════════════════════════════════════════════
# 报告期排序键
# ════════════════════════════════════════════════════════════════════════════

_PERIOD_ORDER = {"Q1": 1, "HY": 2, "Q3": 3, "FY": 4}


def _period_key(row: dict) -> tuple:
    period = str(row.get("report_period", ""))
    year = _f(row.get("report_year", 0)) or 0
    # "2024FY" → year=2024, suffix="FY"
    for suffix, order in _PERIOD_ORDER.items():
        if period.endswith(suffix):
            return (year, order)
    return (year, 0)


# ════════════════════════════════════════════════════════════════════════════
# 单表派生列计算
# ════════════════════════════════════════════════════════════════════════════

def fill_cashflow(rows: list[dict]) -> None:
    for r in rows:
        op = _f(r.get("operating_cf_net_amount"))
        inv = _f(r.get("investing_cf_net_amount"))
        fin = _f(r.get("financing_cf_net_amount"))
        total = _sum_notnull(op, inv, fin)

        if total is not None and total != 0:
            _fill(r, "operating_cf_ratio_of_net_cf",
                  str(round((op or 0) / total * 100, 2)) if op is not None else None)
            _fill(r, "investing_cf_ratio_of_net_cf",
                  str(round((inv or 0) / total * 100, 2)) if inv is not None else None)
            _fill(r, "financing_cf_ratio_of_net_cf",
                  str(round((fin or 0) / total * 100, 2)) if fin is not None else None)

    # YoY 增长
    _fill_yoy(rows, "net_cash_flow", "net_cash_flow_yoy_growth")


def fill_income(rows: list[dict]) -> None:
    expense_cols = [
        "operating_expense_cost_of_sales",
        "operating_expense_selling_expenses",
        "operating_expense_administrative_expenses",
        "operating_expense_financial_expenses",
        "operating_expense_rnd_expenses",
        "operating_expense_taxes_and_surcharges",
    ]
    for r in rows:
        # total_operating_expenses = 各费用之和（有多少加多少）
        total_exp = _sum_notnull(*[r.get(c) for c in expense_cols])
        _fill(r, "total_operating_expenses",
              str(round(total_exp, 4)) if total_exp is not None else None)

        # operating_profit = revenue - total_expenses + other_income
        rev = _f(r.get("total_operating_revenue"))
        exp = _f(r.get("total_operating_expenses")) or total_exp
        other = _f(r.get("other_income")) or 0.0
        if rev is not None and exp is not None:
            op_profit = rev - exp + other
            _fill(r, "operating_profit", str(round(op_profit, 4)))

    # YoY 增长
    _fill_yoy(rows, "net_profit", "net_profit_yoy_growth")
    _fill_yoy(rows, "total_operating_revenue", "operating_revenue_yoy_growth")


def fill_balance(rows: list[dict]) -> None:
    for r in rows:
        # asset_liability_ratio = total_liabilities / total_assets × 100
        _fill(r, "asset_liability_ratio",
              _pct(r.get("liability_total_liabilities"), r.get("asset_total_assets")))

    # YoY
    _fill_yoy(rows, "asset_total_assets", "asset_total_assets_yoy_growth")
    _fill_yoy(rows, "liability_total_liabilities", "liability_total_liabilities_yoy_growth")


def fill_core(rows: list[dict]) -> None:
    for r in rows:
        rev = r.get("total_operating_revenue")
        profit = r.get("net_profit_10k_yuan")

        # net_profit_margin = 净利润 / 营收 × 100
        _fill(r, "net_profit_margin", _pct(profit, rev))

    # YoY / QoQ 增长
    _fill_yoy(rows, "total_operating_revenue", "operating_revenue_yoy_growth")
    _fill_yoy(rows, "net_profit_10k_yuan", "net_profit_yoy_growth")
    _fill_qoq(rows, "total_operating_revenue", "operating_revenue_qoq_growth")
    _fill_qoq(rows, "net_profit_10k_yuan", "net_profit_qoq_growth")


# ════════════════════════════════════════════════════════════════════════════
# YoY / QoQ 增长率（同比 / 环比）
# ════════════════════════════════════════════════════════════════════════════

def _fill_yoy(rows: list[dict], val_col: str, growth_col: str) -> None:
    """同比增长 = (current - same_period_last_year) / |same_period_last_year| × 100"""
    # 建立 (year, period_suffix) → row 的索引
    idx: dict[tuple, dict] = {}
    for r in rows:
        period = str(r.get("report_period", ""))
        year = _f(r.get("report_year"))
        if year is None:
            continue
        for suffix in _PERIOD_ORDER:
            if period.endswith(suffix):
                idx[(int(year), suffix)] = r
                break

    for (year, suffix), r in idx.items():
        if r.get(growth_col, "") not in ("", None, "None", "null"):
            continue
        prev_row = idx.get((year - 1, suffix))
        if prev_row is None:
            continue
        val = _growth(r.get(val_col), prev_row.get(val_col))
        _fill(r, growth_col, val)


def _fill_qoq(rows: list[dict], val_col: str, growth_col: str) -> None:
    """环比增长 = (current - prev_period) / |prev_period| × 100"""
    sorted_rows = sorted(rows, key=_period_key)

    # 按报告期顺序，找前一个报告期
    period_seq = ["Q1", "HY", "Q3", "FY"]

    def prev_period_key(year: int, suffix: str):
        idx = period_seq.index(suffix)
        if idx == 0:
            return (year - 1, "FY")
        return (year, period_seq[idx - 1])

    idx: dict[tuple, dict] = {}
    for r in sorted_rows:
        period = str(r.get("report_period", ""))
        year = _f(r.get("report_year"))
        if year is None:
            continue
        for suffix in period_seq:
            if period.endswith(suffix):
                idx[(int(year), suffix)] = r
                break

    for (year, suffix), r in idx.items():
        if r.get(growth_col, "") not in ("", None, "None", "null"):
            continue
        prev_key = prev_period_key(year, suffix)
        prev_row = idx.get(prev_key)
        if prev_row is None:
            continue
        val = _growth(r.get(val_col), prev_row.get(val_col))
        _fill(r, growth_col, val)


# ════════════════════════════════════════════════════════════════════════════
# 跨表派生列（roe、gross_profit_margin、operating_cf_per_share）
# ════════════════════════════════════════════════════════════════════════════

def fill_cross_sheet(core_rows, balance_rows, income_rows, cashflow_rows) -> None:
    # 建立 report_period → row 的索引
    def idx_by_period(rows):
        return {str(r.get("report_period", "")): r for r in rows if r}

    balance_idx = idx_by_period(balance_rows)
    income_idx = idx_by_period(income_rows)
    cashflow_idx = idx_by_period(cashflow_rows)

    for r in core_rows:
        period = str(r.get("report_period", ""))
        bal = balance_idx.get(period, {})
        inc = income_idx.get(period, {})
        cf = cashflow_idx.get(period, {})

        # roe = 净利润(万元) / 股东权益(万元) × 100
        _fill(r, "roe", _pct(r.get("net_profit_10k_yuan"), bal.get("equity_total_equity")))

        # gross_profit_margin = (营收 - 营业支出) / 营收 × 100
        # 使用 income_sheet 的 total_operating_revenue 和 cost_of_sales
        inc_rev = _f(inc.get("total_operating_revenue"))
        inc_cost = _f(inc.get("operating_expense_cost_of_sales"))
        if inc_rev is not None and inc_cost is not None and inc_rev != 0:
            gpm = (inc_rev - inc_cost) / inc_rev * 100
            _fill(r, "gross_profit_margin", str(round(gpm, 2)))

        # operating_cf_per_share = 经营CF / 股数；股数 = 净利润 / EPS
        # 单位：CF 万元, 净利润 万元, EPS 元/股 → 需转换
        # shares(亿) = net_profit_10k_yuan(万元) × 10000 / eps(元/股) / 10^8
        # 可简化为：operating_cf_per_share = operating_cf(万元) × 10000 / (net_profit_10k_yuan × 10000 / eps)
        #          = operating_cf × eps / net_profit_10k_yuan (元/股)
        op_cf = _f(cf.get("operating_cf_net_amount"))
        eps = _f(r.get("eps"))
        np_val = _f(r.get("net_profit_10k_yuan"))
        if op_cf is not None and eps is not None and np_val is not None and np_val != 0:
            cf_per_share = op_cf * eps / np_val
            _fill(r, "operating_cf_per_share", str(round(cf_per_share, 4)))

    # roe_weighted_excl_non_recurring: 需要扣非净利润 / 权益，近似计算
    for r in core_rows:
        period = str(r.get("report_period", ""))
        bal = balance_idx.get(period, {})
        _fill(r, "roe_weighted_excl_non_recurring",
              _pct(r.get("net_profit_excl_non_recurring"), bal.get("equity_total_equity")))


# ════════════════════════════════════════════════════════════════════════════
# CSV 读写
# ════════════════════════════════════════════════════════════════════════════

def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    if not path.exists():
        return [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return list(fieldnames), rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ════════════════════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════════════════════

def process_company(company_dir: Path) -> None:
    sheets = {
        "income": company_dir / "income_sheet.csv",
        "balance": company_dir / "balance_sheet.csv",
        "cashflow": company_dir / "cash_flow_sheet.csv",
        "core": company_dir / "core_performance_indicators_sheet.csv",
    }

    data: dict[str, tuple] = {}
    for key, path in sheets.items():
        fields, rows = read_csv(path)
        data[key] = (fields, rows)

    income_rows = data["income"][1]
    balance_rows = data["balance"][1]
    cashflow_rows = data["cashflow"][1]
    core_rows = data["core"][1]

    # 单表派生列
    if cashflow_rows:
        fill_cashflow(cashflow_rows)
    if income_rows:
        fill_income(income_rows)
    if balance_rows:
        fill_balance(balance_rows)
    if core_rows:
        fill_core(core_rows)

    # 跨表派生列
    if core_rows:
        fill_cross_sheet(core_rows, balance_rows, income_rows, cashflow_rows)

    # 写回
    for key, path in sheets.items():
        fields, rows = data[key]
        if rows:
            write_csv(path, fields, rows)


def run(output_dir: Path) -> None:
    companies = sorted(
        d for d in output_dir.iterdir() if d.is_dir()
    )
    logger.info(f"共 {len(companies)} 家公司，开始填充派生列...")

    filled = 0
    for company_dir in companies:
        try:
            process_company(company_dir)
            filled += 1
        except Exception as e:
            logger.error(f"[{company_dir.name}] 处理失败: {e}", exc_info=True)

    logger.info(f"完成 ✓  成功处理 {filled}/{len(companies)} 家公司")


def main() -> None:
    parser = argparse.ArgumentParser(description="填充 CSV 中可计算的派生列")
    parser.add_argument(
        "--dir",
        default=str(Path(__file__).resolve().parent / "output"),
        help="output 文件夹路径",
    )
    args = parser.parse_args()
    run(Path(args.dir))


if __name__ == "__main__":
    main()

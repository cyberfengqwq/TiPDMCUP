# debug_pdf_single.py
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from core.pdf.aggregator import metric_records_to_rows
from core.pdf.company_id_resolver import resolve_company_id
from core.pdf.metric_extractor import extract_metric_records
from core.pdf.pipeline import _infer_report_meta_from_filename
from core.pdf.reader import PDFReader


def records_to_debug_df(records):
    rows = []
    for r in records:
        rows.append(
            {
                "table_name": r.table_name,
                "field_key": r.field_key,
                "value": r.value,
                "confidence": r.confidence,
                "stock_code": r.stock_code,
                "stock_abbr": r.stock_abbr,
                "report_period": r.report_period,
                "report_year": r.report_year,
                "report_quarter": r.report_quarter,
                "source_page": r.source_page,
                "source_text": r.source_text,
            }
        )
    return pd.DataFrame(rows)


def build_hit_summary(records):
    """
    统计每个表命中了哪些字段、命中次数
    """
    summary = {}
    for r in records:
        t = r.table_name
        k = r.field_key
        summary.setdefault(t, {})
        summary[t][k] = summary[t].get(k, 0) + 1
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, help="PDF 文件路径")
    parser.add_argument("--out", default="./data/debug_single", help="调试输出目录")
    parser.add_argument("--stock-abbr", default=None, help="可选，股票简称")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 不存在: {pdf_path}")

    reader = PDFReader()

    stock_code = resolve_company_id(pdf_path)
    report_period, report_year, report_quarter = _infer_report_meta_from_filename(
        pdf_path
    )

    if report_quarter == "Q4":
        report_type = "annual"
    elif report_quarter == "Q2":
        report_type = "semiannual"
    else:
        report_type = "quarterly" if report_quarter in ("Q1", "Q3") else None

    raw_tables = reader.read_tables(pdf_path)
    print(f"[INFO] raw_tables={len(raw_tables)}")

    records = extract_metric_records(
        raw_tables=raw_tables,
        stock_code=stock_code,
        stock_abbr=args.stock_abbr,
        report_period=report_period,
        report_year=report_year,
        report_type=report_type,
        report_quarter=report_quarter,
    )
    print(f"[INFO] metric_records={len(records)}")

    # 1) 命中明细
    detail_df = records_to_debug_df(records)
    detail_file = out_dir / f"{pdf_path.stem}_metric_records_detail.csv"
    detail_df.to_csv(detail_file, index=False, encoding="utf-8-sig")
    print(f"[OK] 明细已输出: {detail_file}")

    # 2) 命中摘要
    hit_summary = build_hit_summary(records)
    summary_file = out_dir / f"{pdf_path.stem}_field_hit_summary.json"
    with summary_file.open("w", encoding="utf-8") as f:
        json.dump(hit_summary, f, ensure_ascii=False, indent=2)
    print(f"[OK] 摘要已输出: {summary_file}")

    # 3) 聚合后四张表
    rows_by_table = metric_records_to_rows(records)
    for tname, rows in rows_by_table.items():
        for r in rows:
            r.pop("_report_quarter", None)  # 清理调试字段
        df = pd.DataFrame(rows)
        out_csv = out_dir / f"{pdf_path.stem}_{tname}.csv"
        df.to_csv(out_csv, index=False, encoding="utf-8-sig")
        print(f"[OK] {tname} rows={len(df)} -> {out_csv}")

    # 4) 总报告
    report = {
        "pdf": str(pdf_path),
        "stock_code": stock_code,
        "stock_abbr": args.stock_abbr,
        "report_period": report_period,
        "report_year": report_year,
        "report_quarter": report_quarter,
        "report_type": report_type,
        "raw_tables_count": len(raw_tables),
        "metric_records_count": len(records),
        "table_rows_count": {k: len(v) for k, v in rows_by_table.items()},
        "outputs": {
            "detail_csv": str(detail_file),
            "summary_json": str(summary_file),
        },
    }
    report_file = out_dir / f"{pdf_path.stem}_debug_report.json"
    with report_file.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"[OK] 总报告已输出: {report_file}")


if __name__ == "__main__":
    main()

# core/pdf/pipeline.py

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Union, Optional, Tuple, List, Dict

import pandas as pd

from config.db_schema import DATABASE_SCHEMA_DICT
from core.pdf.aggregator import metric_records_to_rows
from core.pdf.company_id_resolver import resolve_company_id
from core.pdf.exporter import SchemaExporter
from core.pdf.metric_extractor import extract_metric_records
from core.pdf.reader import PDFReader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _infer_report_meta_from_filename(
    pdf_path: Path,
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    从文件名推断 report_period / report_year / report_quarter
    适配示例：
      600080_20240427_0WKP.pdf
      华润三九：2024年三季度报告.pdf
      华润三九：2024年半年度报告.pdf
      华润三九：2024年年度报告.pdf

    Arg:
        pdf_path (Path) : PDF 文件路径

    Return:
        report_period, report_year, report_quarter (tuple) : 报告默认日期；年份；季度
    """
    # 去掉后缀，纯文件名
    name = pdf_path.stem

    # 用正则表达式抓 20 开头的四位数字，如果抓到，转换为 int 保存
    year_match = re.search(r"(20\d{2})", name)
    report_year = int(year_match.group(1)) if year_match else None

    report_quarter = None
    report_period = None
    # 季度/半年度/年度识别，最后一个参数兼容小写
    if re.search(r"(一季度|第?一季|Q1)", name, re.IGNORECASE):
        report_quarter = "Q1"
    elif re.search(r"(半年度|中报|Q2)", name, re.IGNORECASE):
        report_quarter = "Q2"
    elif re.search(r"(三季度|第?三季|Q3)", name, re.IGNORECASE):
        report_quarter = "Q3"
    elif re.search(r"(年度|年报|Q4)", name, re.IGNORECASE):
        report_quarter = "Q4"

    # 报告期按季度标识（YYYYQx）
    if report_year and report_quarter == "Q1":
        report_period = f"{report_year}Q1"
    elif report_year and report_quarter == "Q2":
        report_period = f"{report_year}Q2"
    elif report_year and report_quarter == "Q3":
        report_period = f"{report_year}Q3"
    elif report_year and report_quarter == "Q4":
        report_period = f"{report_year}Q4"

    return report_period, report_year, report_quarter


def _nonnull_ratio(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    nonnull = series.notna() & (series.astype(str).str.strip() != "")
    return float(nonnull.sum()) / float(len(series))


def _table_fill_report(df: pd.DataFrame, table_name: str) -> Dict:
    """
    生成字段填充率报告：每列非空比例
    """
    report = {
        "table_name": table_name,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "fill_rate_by_col": {},
        "avg_fill_rate": 0.0,
    }

    if df.empty:
        return report

    fill_rates = {}
    for c in df.columns:
        fill_rates[c] = round(_nonnull_ratio(df[c]), 4)

    # 去掉主键/标识列后的“业务字段平均填充率”
    biz_cols = [
        c
        for c in df.columns
        if c
        not in {
            "serial_number",
            "stock_code",
            "stock_abbr",
            "report_period",
            "report_year",
        }
    ]
    avg_fill = 0.0
    if biz_cols:
        avg_fill = float(sum(fill_rates[c] for c in biz_cols)) / float(len(biz_cols))

    report["fill_rate_by_col"] = fill_rates
    report["avg_fill_rate"] = round(avg_fill, 4)
    return report


def _warn_missing_key_fields(df: pd.DataFrame, table_name: str) -> None:
    """
    对关键字段做缺失告警（你可按业务继续加）
    """
    key_fields_map = {
        "core_performance_indicators_sheet": [
            "eps",
            "total_operating_revenue",
            "net_profit_10k_yuan",
        ],
        "balance_sheet": [
            "asset_total_assets",
            "liability_total_liabilities",
            "equity_total_equity",
        ],
        "income_sheet": ["total_operating_revenue", "net_profit", "total_profit"],
        "cash_flow_sheet": [
            "net_cash_flow",
            "operating_cf_net_amount",
            "financing_cf_net_amount",
        ],
    }
    fields = key_fields_map.get(table_name, [])
    if df.empty:
        logger.warning(f"[{table_name}] 空表，关键字段全部缺失")
        return

    for f in fields:
        if f not in df.columns:
            logger.warning(f"[{table_name}] 缺少字段列: {f}")
            continue
        ratio = _nonnull_ratio(df[f])
        if ratio < 0.3:
            logger.warning(f"[{table_name}] 关键字段填充率过低: {f}={ratio:.2%}")


class PDFPipeline:
    def __init__(self) -> None:
        self.reader = PDFReader()

    def process_one_pdf(
        self,
        pdf_path: Union[str, Path],
        stock_abbr: Optional[str] = None,
    ) -> Dict[str, List[Dict]]:
        pdf_path = Path(pdf_path)
        logger.info(f"开始处理 {pdf_path}")

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

        raw_tables = self.reader.read_tables(pdf_path)
        logger.info(f"[{pdf_path.name}] 读取原始表格数量: {len(raw_tables)}")

        records = extract_metric_records(
            raw_tables=raw_tables,
            stock_code=stock_code,
            stock_abbr=stock_abbr,
            report_period=report_period,
            report_year=report_year,
            report_type=report_type,
            report_quarter=report_quarter,
        )
        logger.info(f"[{pdf_path.name}] 抽取指标记录数量: {len(records)}")

        rows_by_table = metric_records_to_rows(records)
        for tname, rows in rows_by_table.items():
            logger.info(f"[{pdf_path.name}] 表={tname}, 聚合行数={len(rows)}")

        logger.info(f"完成处理 {pdf_path}")
        return rows_by_table

    def process_company_folder(
        self,
        folder: Union[str, Path],
        out_dir: Union[str, Path],
        dump_debug_report: bool = True,
    ) -> None:
        folder = Path(folder)
        out_dir = Path(out_dir)
        company_id = folder.name

        company_out_dir = out_dir / company_id
        if company_out_dir.exists():
            shutil.rmtree(company_out_dir)

        pdf_files = sorted(folder.glob("*.pdf"))
        logger.info(f"[{company_id}] 待处理 PDF 数量: {len(pdf_files)}")

        # 按表名、股票代码、报告期分组
        aggregated_groups: Dict[str, Dict[Tuple[str, str], Dict]] = {
            "core_performance_indicators_sheet": {},
            "balance_sheet": {},
            "income_sheet": {},
            "cash_flow_sheet": {},
        }

        for pdf in pdf_files:
            rows_by_table = self.process_one_pdf(pdf)
            for tname, rows in rows_by_table.items():
                for row in rows:
                    stock_code = row.get("stock_code")
                    report_period = row.get("report_period")
                    if not stock_code or not report_period:
                        continue
                    key = (stock_code, report_period)
                    
                    # 如果该键不存在，直接添加
                    if key not in aggregated_groups[tname]:
                        aggregated_groups[tname][key] = row
                    else:
                        # 否则，合并行，优先保留非空值
                        existing_row = aggregated_groups[tname][key]
                        for k, v in row.items():
                            if existing_row.get(k) is None or pd.isna(existing_row.get(k)):
                                existing_row[k] = v

        # 转换为列表格式
        aggregated = {}
        for tname, groups in aggregated_groups.items():
            aggregated[tname] = list(groups.values())

        debug_reports: List[Dict] = []

        for tname, rows in aggregated.items():
            # 按报告期排序
            if tname in DATABASE_SCHEMA_DICT:
                cols = DATABASE_SCHEMA_DICT[tname]
                if "report_period" in cols:
                    rows.sort(key=lambda x: x.get("report_period", "9999-99-99"))
            
            # 补充序号
            if "serial_number" in DATABASE_SCHEMA_DICT.get(tname, {}):
                for i, r in enumerate(rows, start=1):
                    r["serial_number"] = i
            
            df = SchemaExporter.build_df(tname, rows)
            SchemaExporter.save_csv(
                df,
                tname,
                out_dir / company_id / f"{company_id}_{tname}.csv",
            )

            # 统计报告
            report = _table_fill_report(df, tname)
            debug_reports.append(report)

            logger.info(
                f"[{company_id}] 导出完成: {tname}.csv | rows={report['rows']} | avg_fill_rate={report['avg_fill_rate']:.2%}"
            )
            _warn_missing_key_fields(df, tname)

        # 可选导出 debug json
        if dump_debug_report:
            debug_path = out_dir / company_id / f"{company_id}_debug_fill_report.json"
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            with debug_path.open("w", encoding="utf-8") as f:
                json.dump(debug_reports, f, ensure_ascii=False, indent=2)
            logger.info(f"[{company_id}] 调试报告已输出: {debug_path}")

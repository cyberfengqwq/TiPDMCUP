# core/pdf/pipeline.py

from pathlib import Path

from core.pdf.aggregator import metric_records_to_rows
from core.pdf.company_id_resolver import resolve_company_id
from core.pdf.exporter import SchemaExporter
from core.pdf.metric_extractor import extract_metric_records
from core.pdf.reader import PDFReader


def _infer_report_meta_from_filename(
    pdf_path: Path,
) -> tuple[str | None, int | None, str | None]:
    """
    从文件名推断 report_period / report_year / report_quarter
    适配示例：
      600080_20240427_0WKP.pdf
      华润三九：2024年三季度报告.pdf
      华润三九：2024年半年度报告.pdf
      华润三九：2024年年度报告.pdf
    """
    name = pdf_path.stem

    # 年份
    year_match = re.search(r"(20\d{2})", name)
    report_year = int(year_match.group(1)) if year_match else None

    report_quarter = None
    report_period = None

    # 季度/半年度/年度识别
    if re.search(r"(一季度|第?一季|Q1)", name, re.IGNORECASE):
        report_quarter = "Q1"
    elif re.search(r"(半年度|中报|Q2)", name, re.IGNORECASE):
        report_quarter = "Q2"
    elif re.search(r"(三季度|第?三季|Q3)", name, re.IGNORECASE):
        report_quarter = "Q3"
    elif re.search(r"(年度|年报|Q4)", name, re.IGNORECASE):
        report_quarter = "Q4"

    # 报告期默认日期（可后续由文本解析替换为精确日期）
    if report_year and report_quarter == "Q1":
        report_period = f"{report_year}-03-31"
    elif report_year and report_quarter == "Q2":
        report_period = f"{report_year}-06-30"
    elif report_year and report_quarter == "Q3":
        report_period = f"{report_year}-09-30"
    elif report_year and report_quarter == "Q4":
        report_period = f"{report_year}-12-31"

    return report_period, report_year, report_quarter


class PDFPipeline:
    def __init__(self) -> None:
        self.reader = PDFReader()

    def process_one_pdf(
        self,
        pdf_path: str | Path,
        stock_abbr: str | None = None,
    ) -> dict[str, list[dict]]:
        pdf_path = Path(pdf_path)

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

        records = extract_metric_records(
            raw_tables=raw_tables,
            stock_code=stock_code,
            stock_abbr=stock_abbr,
            report_period=report_period,
            report_year=report_year,
            report_type=report_type,
            report_quarter=report_quarter,
        )

        return metric_records_to_rows(records)

    def process_company_folder(self, folder: str | Path, out_dir: str | Path) -> None:
        folder = Path(folder)
        out_dir = Path(out_dir)
        pdf_files = sorted(folder.glob("*.pdf"))

        aggregated = {
            "core_performance_indicators_sheet": [],
            "balance_sheet": [],
            "income_sheet": [],
            "cash_flow_sheet": [],
        }

        for pdf in pdf_files:
            rows_by_table = self.process_one_pdf(pdf)
            for tname, rows in rows_by_table.items():
                aggregated[tname].extend(rows)

        company_id = folder.name
        for tname, rows in aggregated.items():
            # 去掉中间调试字段，确保严格 schema
            for r in rows:
                r.pop("_report_quarter", None)

            df = SchemaExporter.build_df(tname, rows)
            SchemaExporter.save_csv(
                df, tname, out_dir / company_id / f"{company_id}_{tname}.csv"
            )

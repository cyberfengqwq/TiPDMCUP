# core/pdf/models.py
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class RawTable:
    pdf_path: Path
    page_no: int
    table_no: int
    df: pd.DataFrame


@dataclass
class MetricRecord:
    table_name: str
    field_key: str
    value: object
    report_period: str | None = None
    report_year: str | None = None
    stock_code: str | None = None
    stock_abbr: str | None = None
    unit: str | None = None
    confidence: str | None = None
    source_page: str | None = None
    source_text: str | None = None


@dataclass
class CompanyReportResult:
    core_performance_indicators_sheet_rows: list[dict] = field(
        default_factory=list[dict]
    )
    balance_sheet_rowws: list[dict] = field(default_factory=list[dict])
    income_sheet_rows: list[dict] = field(default_factory=list[dict])
    cash_flow_sheet_rows: list[dict] = field(default_factory=list[dict])

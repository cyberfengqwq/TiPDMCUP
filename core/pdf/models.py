# core/pdf/models.py
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass
class RawTable:
    """
    原始表格对象：记录来源信息，方便追溯
    """

    pdf_path: Path
    page_no: int
    table_no: int
    df: pd.DataFrame


@dataclass
class MetricRecord:
    """
    指标记录：按行抽取后的标准单元
    """

    table_name: str  # balance_sheet / income_sheet / cash_flow_sheet / core_performance_indicators_sheet
    field_key: str  # schema key
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
    """
    单个 PDF 输出的（行 dict 列表） —— 用于后续导出
    """

    core_performance_indicators_sheet_rows: list[dict] = field(
        default_factory=list[dict]
    )
    balance_sheet_rows: list[dict] = field(default_factory=list[dict])
    income_sheet_rows: list[dict] = field(default_factory=list[dict])
    cash_flow_sheet_rows: list[dict] = field(default_factory=list[dict])

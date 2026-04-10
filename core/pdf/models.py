# core/pdf/models.py
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict

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

    table_name: str  # 归属四大表的哪一个
    field_key: str  # schema key
    value: object  # 该字段的值

    report_period: Optional[str] = None  # 报告期信息
    report_year: Optional[int] = None  # 报告期信息

    # 新增：季度维度（中间层使用，不影响最终CSV schema）
    report_type: Optional[str] = None  # annual / semiannual / quarterly
    report_quarter: Optional[str] = None  # Q1 / Q2 / Q3 / Q4

    stock_code: Optional[str] = None  # 公司身份
    stock_abbr: Optional[str] = None  # 公司身份

    unit: Optional[str] = None  # 单位
    confidence: float = 0.0  # 置信度
    source_page: Optional[int] = None  # 溯源信息
    source_text: Optional[str] = None  # 溯源信息


@dataclass
class CompanyReportResult:
    """
    单个 PDF 输出的（行 dict 列表） —— 用于后续导出
    """

    core_performance_indicators_sheet_rows: List[Dict] = field(
        default_factory=list
    )
    balance_sheet_rows: List[Dict] = field(default_factory=list)
    income_sheet_rows: List[Dict] = field(default_factory=list)
    cash_flow_sheet_rows: List[Dict] = field(default_factory=list)

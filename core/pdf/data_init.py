from dataclasses import dataclass, field

import pandas as pd


@dataclass
class DF:
    """
    初始化一系列目标 DataFrame
    """

    annual_dfs: list[pd.DataFrame] = field(default_factory=list)
    quarter_dfs: list[pd.DataFrame] = field(default_factory=list)

    # 最终的 4 个目标表格
    core_performance_indicators_sheet: pd.DataFrame = field(
        default_factory=pd.DataFrame
    )  # 业绩指标pd
    balance_sheet: pd.DataFrame = field(default_factory=pd.DataFrame)  # 资产负债pd
    income_sheet: pd.DataFrame = field(default_factory=pd.DataFrame)  # 利润pd
    cash_flow_sheet: pd.DataFrame = field(default_factory=pd.DataFrame)  # 现金流pd

    processed_dfs: list[list[pd.DataFrame]] = field(default_factory=list[list])

    def __post_init__(self) -> None:
        if not self.processed_dfs:
            self.processed_dfs = [self.annual_dfs, self.quarter_dfs]


@dataclass
class Table:
    """
    初始化处理过程中的表格
    """

    raw_tables: list[pd.DataFrame] = field(
        default_factory=list[pd.DataFrame]
    )  # "生"表格
    tables_all: list[pd.DataFrame] = field(
        default_factory=list[pd.DataFrame]
    )  # "熟"表格

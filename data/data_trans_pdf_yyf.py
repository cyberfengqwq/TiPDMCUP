from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pdfplumber


@dataclass
class DF:
    """
    四大关键词对应的目标数据表
    初始化为空的 DataFrame
    """

    annual_dfs: list[pd.DataFrame] = field(default_factory=list[pd.DataFrame])  # 年度
    quarter_dfs: list[pd.DataFrame] = field(default_factory=list[pd.DataFrame])  # 季度

    process_dfs: list[list[pd.DataFrame]] = field(
        default_factory=list[list[pd.DataFrame]]
    )

    kpi: pd.DataFrame = field(default_factory=pd.DataFrame)  # 业绩指标
    bs: pd.DataFrame = field(default_factory=pd.DataFrame)  # 资产负债
    profit: pd.DataFrame = field(default_factory=pd.DataFrame)  # 利润
    cashflow: pd.DataFrame = field(default_factory=pd.DataFrame)  # 现金流

    def __post_init__(self) -> None:
        if not self.process_dfs:
            self.process_dfs = [self.annual_dfs, self.quarter_dfs]


@dataclass
class Table:
    """
    初始化表格
    """

    raw_tables: list[pd.DataFrame] = field(default_factory=list)  # "生"表格
    tables_all: list[pd.DataFrame] = field(default_factory=list)  # "熟"表格


class TransPDF:
    def __init__(self) -> None:
        # 初始化 dataclasses
        self.df = DF()
        self.table = Table()

    # 核心成员函数
    def extract_all_tables(self, file_path: Path) -> None:
        """
        1. 从 PDF 中提取所有表格为Datarame,
           并放在 "生"表格 列表当中
        """
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                tables: list[list] = page.extract_tables()
                for table in tables:
                    if table:
                        self.table.raw_tables.append(pd.DataFrame(table))

    def identify_target_tables(self) -> None:
        """
        2. 根据关键字识别目标数据
        """

        for df in self.table.raw_tables:
            # 初步去掉表格中的 "/n" 和 " ", 方便接下来的识别
            head_str = df.head(len(df)).to_string().replace("\n", "").replace(" ", "")

            # 识别年度表和季度表
            if (
                "总资产" in head_str and "营业收入" in head_str
            ) or "本年比上年" in head_str:
                self.df.annual_dfs.append(df)
            elif any(q in head_str for q in ["一季度", "第一季度", "Q1"]):
                self.df.quarter_dfs.append(df)

    def clean_and_format(self) -> None:
        """
        3. 清洗 DataFrame : 处理表头、换行符、数字‘，’
        """
        for dfs in self.df.process_dfs:
            for df in dfs:
                df_clean: pd.DataFrame = df.copy()

    def merge_and_split(self, annual_df, quater_df):
        """
        4. 合并表格，打上来源标签，分配到四个空的主要目标 DataFrame 中
        """

    def process(self, file_path: Path):
        """
        执行全套 PDF 转换流程：
        提取 -> 识别 -> 清洗 -> 合并 & 分类
        """
        print(f"正在处理：{file_path.name}")
        self.extract_all_tables(file_path)
        self.extract_all_tables(file_path)
        self.identify_target_tables()

    # 打印清洗后的 DataFrame
    def print_tables(self) -> None:
        count: int = 1

        if self.table.raw_tables:
            for table in self.table.raw_tables:
                print(f"第{count}个表格")
                print(table)

                count += 1
        else:
            print("没有表格！！")


def main() -> None:
    file_path: Path = Path(
        "示例数据/附件2：财务报告/reports-上交所/600080_20230428_FQ2V.pdf"
    )
    transpdf = TransPDF()
    transpdf.process(file_path)
    # transpdf.print_tables()
    print(transpdf.df.annual_dfs)
    print(transpdf.df.quarter_dfs)


if __name__ == "__main__":
    main()

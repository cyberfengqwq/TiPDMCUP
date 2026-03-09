import os
from dataclasses import dataclass, field

import pandas as pd
import pdfplumber


@dataclass
class DF:
    KPI: pd.DataFrame = field(default_factory=pd.DataFrame)  # 业绩指标pd
    BS: pd.DataFrame = field(default_factory=pd.DataFrame)  # 资产负债pd
    Profit: pd.DataFrame = field(default_factory=pd.DataFrame)  # 利润pd
    CashFlow: pd.DataFrame = field(default_factory=pd.DataFrame)  # 现金流


class TransPDF:
    def __init__(self, file_path: str) -> None:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件未找到：{file_path}")

        # public
        self.file_path = file_path
        # 提取文件名，作为入库SQL时的溯源标签
        self.source_filename = os.path.basename(file_path)

        # private, 不用在类的外部调用
        self._raw_tables: list[pd.DataFrame] = []  # "生"表格
        self._tables_all: list[pd.DataFrame] = []  # "熟"表格

        """
        四大关键词对应的目标数据表
        初始化为空的 DataFrame
        """
        self._KPI: pd.DataFrame = pd.DataFrame()  # 业绩指标
        self._BS: pd.DataFrame = pd.DataFrame()  # 资产负债
        self._Profit: pd.DataFrame = pd.DataFrame()  # 利润
        self._CashFlow: pd.DataFrame = pd.DataFrame()  # 现金流

        """
        利用 @property 装饰器，让目标表格作为属性只读
        """

        @property
        def KPI_table(self):
            return self._KPI

        @property
        def BS_table(self):
            return self._BS

        @property
        def Profit_table(self):
            return self._Profit

        @property
        def CashFlow_table(self):
            return self._CashFlow

    # 核心成员函数

    # 内部私有方法
    def _extract_all_tables(self) -> None:
        """
        Args:

        Returns:



        1. 从 PDF 中提取所有表格为Datarame，
           并放在 "生"表格 列表当中
        """
        self._raw_tables = []
        with pdfplumber.open(self.file_path) as pdf:
            for page in pdf.pages:
                tables: list[list] = page.extract_tables()
                for table in tables:
                    if table:
                        df = pd.DataFrame(table)
                        self._raw_tables.append(table)

    def _identify_target_tables(
        self,
    ) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
        """
        2. 根据关键字识别目标数据
        """
        annual_df, quarter_df = None, None

        for df in self._raw_dfs:
            # 初步去掉表格前 10 行的 "/n" 和 " ", 方便接下来的识别
            head_str = df.head(10).to_string().replace("\n", "").replace(" ", "")

            # 识别年度表和季度表
            if (
                "总资产" in head_str and "营业收入" in head_str
            ) or "本年比上年" in head_str:
                annual_df = df
            elif any(q in head_str for q in ["一季度", "第一季度", "Q1"]):
                quarter_df = df

        return annual_df, quarter_df

    def _clean_and_format(self, df):
        """
        3. 清洗 DataFrame : 处理表头、换行符、数字‘，’
        """
        df_clean: pd.DataFrame = df.copy()

    def _merge_and_split(self, annual_df, quater_df):
        """
        4. 合并表格，打上来源标签，分配到四个空的主要目标 DataFrame 中
        """

    def process(self):
        """
        执行全套 PDF 转换流程：
        提取 -> 识别 -> 清洗 -> 合并 & 分类
        """
        print(f"正在处理：{self.source_filename}")
        self._extract_all_tables()
<<<<<<< HEAD
        self._extract_all_tables()

    # （3）打印清洗后的 DataFrame
    def print_tables(self) -> None:
        count: int = 1

        if self.raw_tables:
            for table in self.raw_tables:
                print(f"第{count}个表格")
                print(table)

                count += 1
        else:
            print("没有表格！！")
=======
>>>>>>> 9757dd9bf027b54bcdd3a6b46fb7b2dce3d5970d


def main() -> None:
    file_path: str = "示例数据/附件2：财务报告/reports-上交所/600080_20230428_FQ2V.pdf"
    transpdf = TransPDF()
    transpdf.trans_pdf(file_path)
    transpdf.print_tables()


if __name__ == "__main__":
    main()

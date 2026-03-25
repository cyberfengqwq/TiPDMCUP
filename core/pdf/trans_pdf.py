import

from pathlib import Path

import pandas as pd
import pdfplumber

from core.pdf.data_init import DF, Table

class TransPDF:
    def __init__(self) -> None:
        # 初始化 dataclasses
        self.df = DF()
        self.table = Table()
        self.source_filename = ""

    # 核心成员函数
    def extract_all_tables(self, file_path: str | Path) -> None:
        """1. 从 PDF 中提取所有表格为Datarame,
           并放在 "生"表格 列表当中

        Args:
            file_path (str | Path): 文件相对路径
        """
        self.source_filename = Path(file_path).name

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                tables: list[list] | None = page.extract_table()
                assert tables is not None
                for table in tables:
                    if table:
                        cleaned_table = [row for row in table
                                            if any(cell for cell in row) ]
                        if cleaned_table:
                            self.table.raw_tables.append(pd.DataFrame(table))

    def identify_target_tables(self) -> None:
        """
        2. 根据关键字识别目标数据
        """

        for df in self.table.raw_tables:
            # 初步清洗表格中的 "/n" 和 " ", 方便接下来的识别
            head_str = df.head(len(df)).to_string().replace("\n", "").replace(" ", "")

            # 识别年度表和季度表
            if (
                "总资产" in head_str and "营业收入" in head_str
            ) or "本年比上年" in head_str:
                self.df.annual_dfs.append(df)
            elif any(q in head_str for q in ["一季度", "第一季度", "Q1", "第三季度", "Q3"]):
                self.df.quarter_dfs.append(df)

    def _clean_and_format(self):
        """
        3. 清洗 DataFrame : 处理表头、换行符、数字‘，’、空值
        """
        for dfs in self.df.processed_dfs:
            for i in range(len(dfs)):
                df_raw: pd.DataFrame = dfs[i].copy()

                # 1. 替换所有换行符
                df_raw = df_raw.replace(r'\\n', '', regex=True)

                # 2. 去除数字中的千分位逗号
                df_raw = df_raw.map(lambda x: str(x).replace(',', ''))

                # 3.
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


def main() -> None:
    file_path: str = "示例数据/附件2：财务报告/reports-上交所/600080_20230428_FQ2V.pdf"
    transpdf = TransPDF()
    transpdf.trans_pdf(file_path)
    transpdf.print_tables()


if __name__ == "__main__":
    main()

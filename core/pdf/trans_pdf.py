from pathlib import Path

import pandas as pd
import pdfplumber
from pdf.data_init import DF, Table

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
                if not tables:
                    return

                for table in tables:
                    if table:
                        cleaned_table = [
                            row for row in table if any(cell for cell in row)
                        ]
                        if cleaned_table:
                            self.table.raw_tables.append(pd.DataFrame(cleaned_table))

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
            elif any(
                q in head_str for q in ["一季度", "第一季度", "Q1", "第三季度", "Q3"]
            ):
                self.df.quarter_dfs.append(df)

    def clean_and_format(self) -> None:
        """
        3. 清洗 DataFrame : 处理表头、换行符、数字‘，’、空值
        """
        for dfs in self.df.processed_dfs:
            for i in range(len(dfs)):
                df: pd.DataFrame = dfs[i].copy()

                # 1. 替换所有换行符
                df = df.replace(r"\\n", "", regex=True)

                # 2. 去除数字中的千分位逗号
                df = df.map(lambda x: str(x).replace(",", ""))

                # 3. 将能转数字的列转换为 numeric 数据类型
                for col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="ignore")

                # 4. 删除全空的列和行
                df.dropna(how="all", axis=0, inplace=True)
                df.dropna(how="all", axis=1, inplace=True)

                dfs[i] = df

    def merge_and_split(self, annual_df, quater_df):
        """
        4. 合并表格，打上来源标签，分配到四个空的主要目标 DataFrame 中
        """

    def process(self, file_path: str | Path) -> None:
        """
        执行全套 PDF 转换流程：
        提取 -> 识别 -> 清洗 -> 合并 & 分类
        """
        print(f"正在提取：{file_path}")
        self.extract_all_tables(file_path)
        print(f"成功提取了 {len(self.table.raw_tables)} 个原始表格。开始识别")

        self.identify_target_tables()
        print(
            f"识别到 {len(self.df.annual_dfs)}个年度片段, {len(self.df.quarter_dfs)} 个季度片段。开始清洗..."
        )

        self.clean_and_format()

        print(f"{self.source_filename} 的提取与清洗完成")

    def debug_summary(self, limit: int = 3, preview_rows: int = 3) -> None:
        """
        调试用：打印原始表格摘要，而不是全量打印
        """
        total = len(self.table.raw_tables)
        print(f"raw_tables 总数: {total}")
        if total == 0:
            print("没有提取到表格！！")
            return

        for idx, table in enumerate(self.table.raw_tables[:limit], start=1):
            print(f"\n--- 原始表格 #{idx} ---")
            print(f"shape = {table.shape}")
            print(table.head(preview_rows))

        print(f"\nannual_dfs 数量: {len(self.df.annual_dfs)}")
        print(f"quarter_dfs 数量: {len(self.df.quarter_dfs)}")


def main() -> None:
    file_path: str = "示例数据/附件2：财务报告/reports-上交所/600080_20230428_FQ2V.pdf"
    transpdf = TransPDF()
    try:
        transpdf.process(file_path)

        if transpdf.df.annual_dfs:
            print("\n>>> 年度表格清洗结果示例 (前5行):")
            print(transpdf.df.annual_dfs[0].head(5))
    except FileNotFoundError:
        print(f"找不到文件: {file_path}，请修改为实际测试文件路径。")


if __name__ == "__main__":
    main()

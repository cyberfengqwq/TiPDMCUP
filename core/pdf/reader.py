# core/pdf/reader.py
from pathlib import Path

import pandas as pd
import pdfplumber

from core.pdf.models import RawTable


class PDFReader:
    def read_tables(self, pdf_path: str | Path) -> list[RawTable]:
        # 统一为 Path 路径格式
        pdf_path = Path(pdf_path)
        # 准备一个空列表，最终返回装满 raw_table 的列表
        results: list[RawTable] = []

        with pdfplumber.open(pdf_path) as pdf:
            # Loop_1: 一页一页的遍历 PDF 提取表格为 df 格式，同时获取溯源页码
            for p_idx, page in enumerate(pdf.pages, start=1):
                # 提取表格
                tables = page.extract_tables()
                if not tables:
                    continue

                # Loop_1.1: 一张一张的遍历每页 PDF 上的表格，同时获取溯源表格序号
                for t_idx, table in enumerate(tables, start=1):
                    # 如果表格为空，丢掉
                    if not table:
                        continue

                    # Loop_1.1.1: 扁平化处理，将 初步处理的表格放进 cleaned 列表
                    cleaned = [
                        row
                        for row in table
                        if row
                        and any(
                            # 检查表格的每一个单元格
                            cell is not None and str(cell).strip() != ""
                            for cell in row
                        )
                    ]
                    # 如果整张表都为空，丢掉
                    if not cleaned:
                        continue

                    # 清洗结束，允许进入 results 列表，带上四个属性！
                    results.append(
                        RawTable(
                            pdf_path=pdf_path,
                            page_no=p_idx,
                            table_no=t_idx,
                            df=pd.DataFrame(cleaned),
                        )
                    )
        return results

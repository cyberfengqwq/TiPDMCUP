import pandas as pd
import pdfplumber

file_path: str = "示例数据/附件2：财务报告/reports-上交所/600080_20230428_FQ2V.pdf"


def trans_pdf(file_path: str) -> list[pd.DataFrame]:
    tables: list[pd.DataFrame] = []

    with pdfplumber.open(file_path) as pdf:
        pages: list = pdf.pages

        for page in pages:
            table = page.extract_table()

            if table:
                df: pd.DataFrame = pd.DataFrame(table)
                tables.append(df)

    return tables

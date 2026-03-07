import pandas as pd
import pdfplumber


class TransPDF:
    def __init__(self) -> None:
        self.tables: list[pd.DataFrame] = []

    def trans_pdf(self, file_path: str) -> list[pd.DataFrame]:
        with pdfplumber.open(file_path) as pdf:
            pages: list = pdf.pages

            for page in pages:
                table = page.extract_table()

                if table:
                    df: pd.DataFrame = pd.DataFrame(table)
                    self.tables.append(df)

        return self.tables

    def clean_format_pdf(self, file_path: str):
        for table in self.tables:
            clean_table: pd.DataFrame = table
            

    def print_tables(self) -> None:
        count: int = 1

        if self.tables:
            for table in self.tables:
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

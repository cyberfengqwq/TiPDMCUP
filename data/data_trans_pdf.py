import pandas as pd
import pdfplumber
import os

class TransPDF:
    def __init__(self, file_path: str) -> None:
        if not os.path.exsists(file_path):
            raise FileNotFoundError(f"文件未找到：{file_path}")
        
        # public
        self.file_path = file_path
        # 提取文件名，作为入库SQL时的溯源标签
        self.source_filename = os.path.basename(file_path)
        
        # private, 不用在类的外部调用
        self._raw_tables: list[pd.DataFrame] = [] # "生"表格
        self._tables_all: list[pd.DataFrame] = [] # "熟"表格
        
        """
        四大关键词对应的目标数据表
        初始化为空的 DataFrame
        """
        self._KPI: pd.DataFrame = pd.DataFrame()       # 业绩指标
        self._BS: pd.DataFrame = pd.DataFrame()        # 资产负债
        self._Profit: pd.DataFrame = pd.DataFrame()    # 利润
        self._CashFlow: pd.DataFrame = pd.DataFrame()  # 现金流
        
        """
        利用 @property 装饰器，让目标表格作为属性只读
        """
        @property
        def KPI_table(self): return self._KPI      
        @property
        def BS_table(self): return self._BS
        @property
        def Profit_table(self): return self._Profit
        @property
        def CashFlow_table(self): return self._CashFlow
        
        
        # 核心成员函数
        
        # 内部私有方法
        def _extract_all_tables(self):
            """
            功能：从 PDF 中提取所有表格为Datarame
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
                    
        
        
        
        
        
        def process(self):
            """
            执行全套 PDF 转换流程：
            提取 -> 识别与清洗 -> 合并 -> 分类
            """
            print(f"正在处理：{self.source_filename}")
            self._extract_all_tables()
            
            
        
        
        

    # （1）将 PDF 中的表格转化为 DataFrame 格式
    def trans_pdf(self, file_path: str) -> list[pd.DataFrame]:
        with pdfplumber.open(file_path) as pdf:
            pages: list = pdf.pages

            for page in pages:
                table = page.extract_table()

                if table:
                    df: pd.DataFrame = pd.DataFrame(table)
                    self.raw_tables.append(df)

        return self.raw_tables

    # （2）根据关键词清洗 DataFrame
    def clean_format_pdf(self, file_path: str):
        for table in self.raw_tables:
            clean_table: pd.DataFrame = table
            
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

import pdfplumber

# 读取PDF文件
pdf_path = '示例数据/附件2：财务报告/reports-上交所/600080_20230428_FQ2V.pdf'

with pdfplumber.open(pdf_path) as pdf:
    # 查看第5页的表格，这是包含财务数据的页面
    page = pdf.pages[4]  # 第5页（索引为4）
    tables = page.extract_tables()
    
    print('第5页表格数量:', len(tables))
    
    # 打印所有表格的内容
    for i, table in enumerate(tables):
        print(f'\n=== 表格{i+1} ===')
        for row in table:
            print(row)
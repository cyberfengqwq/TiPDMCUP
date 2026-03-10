# config/db_schema.py

# 1. 数据库表结构
TABLE_SCHEMA = """
【数据库表结构说明】
表名: income_sheet (利润表)
字段:
- stock_abbr (VARCHAR): 股票简称，如 '金花股份', '华润三九'
- report_period (VARCHAR): 报告期，如 '2024FY' (2024年度), '2025Q3' (2025年第三季度)
- total_profit (DECIMAL): 利润总额(万元)
- total_revenue (DECIMAL): 营业总收入(万元)
"""

# 2. SQL 样例
SQL_EXAMPLES = [
    {
        "question": "金花股份近几年的利润总额变化趋势是什么样的",
        "query": "SELECT report_period, total_profit FROM income_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;",
    },
    {
        "question": "2024年利润最高的top10企业是哪些",
        "query": "SELECT stock_abbr, total_profit FROM income_sheet WHERE report_period LIKE '2024%' ORDER BY total_profit DESC LIMIT 10;",
    },
]

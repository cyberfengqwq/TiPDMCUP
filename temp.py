user_question = "华润三九2024年的净利润和营业总收入分别是多少？"

sql: str = "SELECT net_profit, total_operating_revenue FROM income_sheet WHERE stock_abbr = '华润三九' AND report_year = '2024';"


"""
你是一个 MySQL 顶级专家。请参考以下数据库字典和相似历史 SQL，为用户生成 SQL。

【数据库字典】
income_sheet: 利润表
  - total_profit: 利润总额(万元)
  - report_period: 报告期

【历史相似经验】
历史提问: 金花股份近几年的利润总额变化趋势是什么样的
标准 SQL: SELECT report_period, total_profit FROM income_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;

【当前最新任务】
用户提问: 华润三九近几年的利润趋势是怎样的？
请输出纯 SQL:
"""

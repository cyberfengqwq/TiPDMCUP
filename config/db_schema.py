# config/db_schema.py

DATABASE_SCHEMA_DICT: dict[str, dict[str, str]] = {
    "core_performance_indicators_sheet": {
        "serial_number": "序号",
        "stock_code": "股票代码",
        "stock_abbr": "股票简称",
        "eps": "每股收益（元）",
        "total_operating_revenue": "营业总收入（万元）",
        "operating_revenue_yoy_growth": "营业总收入-同比增长(%)",
        "operating_revenue_qoq_growth": "营业总收入-季度环比增长(%)",
        "net_profit_10k_yuan": "净利润(万元)",
        "net_profit_yoy_growth": "净利润-同比增长(%)",
        "net_profit_qoq_growth": "净利润-季度环比增长(%)",
        "net_asset_per_share": "每股净资产(元)",
        "roe": "净资产收益率(%)",
        "operating_cf_per_share": "每股经营现金流量(元)",
        "net_profit_excl_non_recurring": "扣非净利润（万元）",
        "net_profit_excl_non_recurring_yoy": "扣非净利润同比增长（%）",
        "gross_profit_margin": "销售毛利率(%)",
        "net_profit_margin": "销售净利率（%）",
        "roe_weighted_excl_non_recurring": "加权平均净资产收益率（扣非）（%）",
        "report_period": "报告期",
        "report_year": "报告期-年份",
    },
    "balance_sheet": {
        "serial_number": "序号",
        "stock_code": "股票代码",
        "stock_abbr": "股票简称",
        "asset_cash_and_cash_equivalents": "资产-货币资金(万元)",
        "asset_accounts_receivable": "资产-应收账款(万元)",
        "asset_inventory": "资产-存货(万元)",
        "asset_trading_financial_assets": "资产-交易性金融资产（万元）",
        "asset_construction_in_progress": "资产-在建工程（万元）",
        "asset_total_assets": "资产-总资产(万元)",
        "asset_total_assets_yoy_growth": "资产-总资产同比(%)",
        "liability_accounts_payable": "负债-应付账款(万元)",
        "liability_advance_from_customers": "负债-预收账款(万元)",
        "liability_total_liabilities": "负债-总负债(万元)",
        "liability_total_liabilities_yoy_growth": "负债-总负债同比(%)",
        "liability_contract_liabilities": "负债-合同负债（万元）",
        "liability_short_term_loans": "负债-短期借款（万元）",
        "asset_liability_ratio": "资产负债率(%)",
        "equity_unappropriated_profit": "股东权益-未分配利润（万元）",
        "equity_total_equity": "股东权益合计(万元)",
        "report_period": "报告期",
        "report_year": "报告期-年份",
    },
    "income_sheet": {
        "serial_number": "序号",
        "stock_code": "股票代码",
        "stock_abbr": "股票简称",
        "net_profit": "净利润(万元)",
        "net_profit_yoy_growth": "净利润同比(%)",
        "other_income": "其他收益（万元）",
        "total_operating_revenue": "营业总收入(万元)",
        "operating_revenue_yoy_growth": "营业总收入同比(%)",
        "operating_expense_cost_of_sales": "营业总支出-营业支出(万元)",
        "operating_expense_selling_expenses": "营业总支出-销售费用(万元)",
        "operating_expense_administrative_expenses": "营业总支出-管理费用(万元)",
        "operating_expense_financial_expenses": "营业总支出-财务费用(万元)",
        "operating_expense_rnd_expenses": "营业总支出-研发费用（万元）",
        "operating_expense_taxes_and_surcharges": "营业总支出-税金及附加（万元）",
        "total_operating_expenses": "营业总支出(万元)",
        "operating_profit": "营业利润(万元)",
        "total_profit": "利润总额(万元)",
        "asset_impairment_loss": "资产减值损失（万元）",
        "credit_impairment_loss": "信用减值损失（万元）",
        "report_period": "报告期",
        "report_year": "报告期-年份",
    },
    "cash_flow_sheet": {
        "serial_number": "序号",
        "stock_code": "股票代码",
        "stock_abbr": "股票简称",
        "net_cash_flow": "净现金流(元)",
        "net_cash_flow_yoy_growth": "净现金流-同比增长(%)",
        "operating_cf_net_amount": "经营性现金流-现金流量净额(万元)",
        "operating_cf_ratio_of_net_cf": "经营性现金流-净现金流占比(%)",
        "operating_cf_cash_from_sales": "经营性现金流-销售商品收到的现金（万元）",
        "investing_cf_net_amount": "投资性现金流-现金流量净额(万元)",
        "investing_cf_ratio_of_net_cf": "投资性现金流-净现金流占比(%)",
        "investing_cf_cash_for_investments": "投资性现金流-投资支付的现金（万元）",
        "investing_cf_cash_from_investment_recovery": "投资性现金流-收回投资收到的现金（万元）",
        "financing_cf_cash_from_borrowing": "融资性现金流-取得借款收到的现金（万元）",
        "financing_cf_cash_for_debt_repayment": "融资性现金流-偿还债务支付的现金（万元）",
        "financing_cf_net_amount": "融资性现金流-现金流量净额(万元)",
        "financing_cf_ratio_of_net_cf": "融资性现金流-净现金流占比(%)",
        "report_period": "报告期",
        "report_year": "报告期-年份",
    },
}

# 2. SQL 样例
SQL_EXAMPLES = [
    {
        "question": "金花股份近几年的利润总额变化趋势是什么样的",
        "query": "SELECT report_period, total_profit FROM income_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;",
    },
    {
        "question": "金花股份近几年的每股收益变化趋势是什么样的",
        "query": "SELECT report_period, eps FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;",
    },
    {
        "question": "金花股份2024年度的净资产收益率是多少",
        "query": "SELECT roe FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' AND report_year = '2024';",
    },
    {
        "question": "金花股份2024年Q1到Q3的营业总收入同比增长率",
        "query": "SELECT report_period, operating_revenue_yoy_growth FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' AND report_period LIKE '2024Q%';",
    },
    {
        "question": "金花股份最近3个季度的净利润环比增长率",
        "query": "SELECT report_period, net_profit_qoq_growth FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period DESC LIMIT 3;",
    },
    {
        "question": "金花股份每股经营现金流量最高的报告期是哪个",
        "query": "SELECT report_period, operating_cf_per_share FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' ORDER BY operating_cf_per_share DESC LIMIT 1;",
    },
    {
        "question": "金花股份2023年和2024年的每股净资产对比",
        "query": "SELECT report_year, net_asset_per_share FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' AND report_year IN ('2023', '2024');",
    },
    {
        "question": "金花股份扣非净利润最近5个报告期的变化",
        "query": "SELECT report_period, net_profit_excl_non_recurring FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period DESC LIMIT 5;",
    },
    {
        "question": "金花股份销售毛利率最高的报告期是什么时候",
        "query": "SELECT report_period, gross_profit_margin FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' ORDER BY gross_profit_margin DESC LIMIT 1;",
    },
    {
        "question": "金花股份营业总收入同比增长最快的季度",
        "query": "SELECT report_period, operating_revenue_yoy_growth FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' ORDER BY operating_revenue_yoy_growth DESC LIMIT 1;",
    },
    {
        "question": "金花股份2024年全年的销售净利率",
        "query": "SELECT net_profit_margin FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' AND report_period = '2024FY';",
    },
    {
        "question": "金花股份加权平均净资产收益率的历年变化",
        "query": "SELECT report_year, roe_weighted_excl_non_recurring FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' ORDER BY report_year;",
    },
    {
        "question": "金花股份净利润同比增长最高的报告期",
        "query": "SELECT report_period, net_profit_yoy_growth FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' ORDER BY net_profit_yoy_growth DESC LIMIT 1;",
    },
    {
        "question": "金花股份2023年Q4的核心业绩指标有哪些",
        "query": "SELECT eps, total_operating_revenue, net_profit_10k_yuan, roe FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' AND report_period = '2023Q4';",
    },
    {
        "question": "金花股份扣非净利润同比增长最高的报告期",
        "query": "SELECT report_period, net_profit_excl_non_recurring_yoy FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' ORDER BY net_profit_excl_non_recurring_yoy DESC LIMIT 1;",
    },
    {
        "question": "金花股份营业总收入季度环比增长的最新数据",
        "query": "SELECT report_period, operating_revenue_qoq_growth FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period DESC LIMIT 1;",
    },
    {
        "question": "金花股份2024年所有报告期的每股收益汇总",
        "query": "SELECT report_period, eps FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' AND report_year = '2024';",
    },
    {
        "question": "金花股份净利润与扣非净利润的差异",
        "query": "SELECT report_period, net_profit_10k_yuan, net_profit_excl_non_recurring FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份';",
    },
    {
        "question": "金花股份最近12个月的毛利率趋势",
        "query": "SELECT report_period, gross_profit_margin FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period DESC LIMIT 4;",
    },
    {
        "question": "金花股份2024年上半年的净资产收益率",
        "query": "SELECT report_period, roe FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' AND report_period IN ('2024Q1', '2024Q2');",
    },
    {
        "question": "金花股份最高的销售净利率是多少",
        "query": "SELECT MAX(net_profit_margin) as max_net_profit_margin FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份';",
    },
    {
        "question": "金花股份所有报告期的每股经营现金流平均值",
        "query": "SELECT AVG(operating_cf_per_share) as avg_cf FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份';",
    },
    {
        "question": "金花股份过去5年的营业收入增长情况",
        "query": "SELECT report_year, total_operating_revenue FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' ORDER BY report_year;",
    },
    {
        "question": "金花股份最近一年净利润的波动情况",
        "query": "SELECT report_period, net_profit_yoy_growth FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' AND report_year = '2024';",
    },
    {
        "question": "金花股份ROE最高和最低的报告期分别是什么",
        "query": "SELECT report_period, roe FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' ORDER BY roe DESC LIMIT 1 UNION SELECT report_period, roe FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' ORDER BY roe ASC LIMIT 1;",
    },
    {
        "question": "金花股份2024年营业总收入环比增长率",
        "query": "SELECT report_period, operating_revenue_qoq_growth FROM core_performance_indicators_sheet WHERE stock_abbr = '金花股份' AND report_year = '2024';",
    },
    # Core Performance Indicators Sheet - 华润三九 (25 examples)
    {
        "question": "华润三九近几年的每股收益变化趋势是什么样的",
        "query": "SELECT report_period, eps FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period;",
    },
    {
        "question": "华润三九2024年度的净资产收益率是多少",
        "query": "SELECT roe FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' AND report_year = '2024';",
    },
    {
        "question": "华润三九2024年Q1到Q3的营业总收入同比增长率",
        "query": "SELECT report_period, operating_revenue_yoy_growth FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' AND report_period LIKE '2024Q%';",
    },
    {
        "question": "华润三九最近3个季度的净利润环比增长率",
        "query": "SELECT report_period, net_profit_qoq_growth FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period DESC LIMIT 3;",
    },
    {
        "question": "华润三九每股经营现金流量最高的报告期是哪个",
        "query": "SELECT report_period, operating_cf_per_share FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' ORDER BY operating_cf_per_share DESC LIMIT 1;",
    },
    {
        "question": "华润三九2023年和2024年的每股净资产对比",
        "query": "SELECT report_year, net_asset_per_share FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' AND report_year IN ('2023', '2024');",
    },
    {
        "question": "华润三九扣非净利润最近5个报告期的变化",
        "query": "SELECT report_period, net_profit_excl_non_recurring FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period DESC LIMIT 5;",
    },
    {
        "question": "华润三九销售毛利率最高的报告期是什么时候",
        "query": "SELECT report_period, gross_profit_margin FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' ORDER BY gross_profit_margin DESC LIMIT 1;",
    },
    {
        "question": "华润三九营业总收入同比增长最快的季度",
        "query": "SELECT report_period, operating_revenue_yoy_growth FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' ORDER BY operating_revenue_yoy_growth DESC LIMIT 1;",
    },
    {
        "question": "华润三九2024年全年的销售净利率",
        "query": "SELECT net_profit_margin FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' AND report_period = '2024FY';",
    },
    {
        "question": "华润三九加权平均净资产收益率的历年变化",
        "query": "SELECT report_year, roe_weighted_excl_non_recurring FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' ORDER BY report_year;",
    },
    {
        "question": "华润三九净利润同比增长最高的报告期",
        "query": "SELECT report_period, net_profit_yoy_growth FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' ORDER BY net_profit_yoy_growth DESC LIMIT 1;",
    },
    {
        "question": "华润三九2023年Q4的核心业绩指标有哪些",
        "query": "SELECT eps, total_operating_revenue, net_profit_10k_yuan, roe FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' AND report_period = '2023Q4';",
    },
    {
        "question": "华润三九扣非净利润同比增长最高的报告期",
        "query": "SELECT report_period, net_profit_excl_non_recurring_yoy FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' ORDER BY net_profit_excl_non_recurring_yoy DESC LIMIT 1;",
    },
    {
        "question": "华润三九营业总收入季度环比增长的最新数据",
        "query": "SELECT report_period, operating_revenue_qoq_growth FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period DESC LIMIT 1;",
    },
    {
        "question": "华润三九2024年所有报告期的每股收益汇总",
        "query": "SELECT report_period, eps FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' AND report_year = '2024';",
    },
    {
        "question": "华润三九净利润与扣非净利润的差异",
        "query": "SELECT report_period, net_profit_10k_yuan, net_profit_excl_non_recurring FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九';",
    },
    {
        "question": "华润三九最近12个月的毛利率趋势",
        "query": "SELECT report_period, gross_profit_margin FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period DESC LIMIT 4;",
    },
    {
        "question": "华润三九2024年上半年的净资产收益率",
        "query": "SELECT report_period, roe FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' AND report_period IN ('2024Q1', '2024Q2');",
    },
    {
        "question": "华润三九最高的销售净利率是多少",
        "query": "SELECT MAX(net_profit_margin) as max_net_profit_margin FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九';",
    },
    {
        "question": "华润三九所有报告期的每股经营现金流平均值",
        "query": "SELECT AVG(operating_cf_per_share) as avg_cf FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九';",
    },
    {
        "question": "华润三九过去5年的营业收入增长情况",
        "query": "SELECT report_year, total_operating_revenue FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' ORDER BY report_year;",
    },
    {
        "question": "华润三九最近一年净利润的波动情况",
        "query": "SELECT report_period, net_profit_yoy_growth FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' AND report_year = '2024';",
    },
    {
        "question": "华润三九ROE最高和最低的报告期分别是什么",
        "query": "SELECT report_period, roe FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' ORDER BY roe DESC LIMIT 1 UNION SELECT report_period, roe FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' ORDER BY roe ASC LIMIT 1;",
    },
    {
        "question": "华润三九2024年营业总收入环比增长率",
        "query": "SELECT report_period, operating_revenue_qoq_growth FROM core_performance_indicators_sheet WHERE stock_abbr = '华润三九' AND report_year = '2024';",
    },
    # Balance Sheet - 金花股份 (15 examples)
    {
        "question": "金花股份最近几个报告期的总资产变化",
        "query": "SELECT report_period, asset_total_assets FROM balance_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period DESC LIMIT 5;",
    },
    {
        "question": "金花股份2024年的资产负债率是多少",
        "query": "SELECT asset_liability_ratio FROM balance_sheet WHERE stock_abbr = '金花股份' AND report_year = '2024';",
    },
    {
        "question": "金花股份货币资金最高的报告期",
        "query": "SELECT report_period, asset_cash_and_cash_equivalents FROM balance_sheet WHERE stock_abbr = '金花股份' ORDER BY asset_cash_and_cash_equivalents DESC LIMIT 1;",
    },
    {
        "question": "金花股份总负债同比增长率的变化",
        "query": "SELECT report_year, liability_total_liabilities_yoy_growth FROM balance_sheet WHERE stock_abbr = '金花股份';",
    },
    {
        "question": "金花股份应收账款与存货的对比",
        "query": "SELECT report_period, asset_accounts_receivable, asset_inventory FROM balance_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;",
    },
    {
        "question": "金花股份股东权益的变化趋势",
        "query": "SELECT report_period, equity_total_equity FROM balance_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;",
    },
    {
        "question": "金花股份未分配利润最高的报告期",
        "query": "SELECT report_period, equity_unappropriated_profit FROM balance_sheet WHERE stock_abbr = '金花股份' ORDER BY equity_unappropriated_profit DESC LIMIT 1;",
    },
    {
        "question": "金花股份短期借款最近的数据",
        "query": "SELECT report_period, liability_short_term_loans FROM balance_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period DESC LIMIT 1;",
    },
    {
        "question": "金花股份在建工程的投入情况",
        "query": "SELECT report_period, asset_construction_in_progress FROM balance_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period DESC;",
    },
    {
        "question": "金花股份应付账款与预收账款的变化",
        "query": "SELECT report_period, liability_accounts_payable, liability_advance_from_customers FROM balance_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;",
    },
    {
        "question": "金花股份交易性金融资产的规模",
        "query": "SELECT report_period, asset_trading_financial_assets FROM balance_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;",
    },
    {
        "question": "金花股份合同负债的最新数据",
        "query": "SELECT report_period, liability_contract_liabilities FROM balance_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period DESC LIMIT 1;",
    },
    {
        "question": "金花股份资产与负债的对比",
        "query": "SELECT report_period, asset_total_assets, liability_total_liabilities FROM balance_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;",
    },
    {
        "question": "金花股份2024年所有季度的资产负债率",
        "query": "SELECT report_period, asset_liability_ratio FROM balance_sheet WHERE stock_abbr = '金花股份' AND report_year = '2024';",
    },
    {
        "question": "金花股份总资产同比增长最快的报告期",
        "query": "SELECT report_period, asset_total_assets_yoy_growth FROM balance_sheet WHERE stock_abbr = '金花股份' ORDER BY asset_total_assets_yoy_growth DESC LIMIT 1;",
    },
    # Balance Sheet - 华润三九 (15 examples)
    {
        "question": "华润三九最近几个报告期的总资产变化",
        "query": "SELECT report_period, asset_total_assets FROM balance_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period DESC LIMIT 5;",
    },
    {
        "question": "华润三九2024年的资产负债率是多少",
        "query": "SELECT asset_liability_ratio FROM balance_sheet WHERE stock_abbr = '华润三九' AND report_year = '2024';",
    },
    {
        "question": "华润三九货币资金最高的报告期",
        "query": "SELECT report_period, asset_cash_and_cash_equivalents FROM balance_sheet WHERE stock_abbr = '华润三九' ORDER BY asset_cash_and_cash_equivalents DESC LIMIT 1;",
    },
    {
        "question": "华润三九总负债同比增长率的变化",
        "query": "SELECT report_year, liability_total_liabilities_yoy_growth FROM balance_sheet WHERE stock_abbr = '华润三九';",
    },
    {
        "question": "华润三九应收账款与存货的对比",
        "query": "SELECT report_period, asset_accounts_receivable, asset_inventory FROM balance_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period;",
    },
    {
        "question": "华润三九股东权益的变化趋势",
        "query": "SELECT report_period, equity_total_equity FROM balance_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period;",
    },
    {
        "question": "华润三九未分配利润最高的报告期",
        "query": "SELECT report_period, equity_unappropriated_profit FROM balance_sheet WHERE stock_abbr = '华润三九' ORDER BY equity_unappropriated_profit DESC LIMIT 1;",
    },
    {
        "question": "华润三九短期借款最近的数据",
        "query": "SELECT report_period, liability_short_term_loans FROM balance_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period DESC LIMIT 1;",
    },
    {
        "question": "华润三九在建工程的投入情况",
        "query": "SELECT report_period, asset_construction_in_progress FROM balance_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period DESC;",
    },
    {
        "question": "华润三九应付账款与预收账款的变化",
        "query": "SELECT report_period, liability_accounts_payable, liability_advance_from_customers FROM balance_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period;",
    },
    {
        "question": "华润三九交易性金融资产的规模",
        "query": "SELECT report_period, asset_trading_financial_assets FROM balance_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period;",
    },
    {
        "question": "华润三九合同负债的最新数据",
        "query": "SELECT report_period, liability_contract_liabilities FROM balance_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period DESC LIMIT 1;",
    },
    {
        "question": "华润三九资产与负债的对比",
        "query": "SELECT report_period, asset_total_assets, liability_total_liabilities FROM balance_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period;",
    },
    {
        "question": "华润三九2024年所有季度的资产负债率",
        "query": "SELECT report_period, asset_liability_ratio FROM balance_sheet WHERE stock_abbr = '华润三九' AND report_year = '2024';",
    },
    {
        "question": "华润三九总资产同比增长最快的报告期",
        "query": "SELECT report_period, asset_total_assets_yoy_growth FROM balance_sheet WHERE stock_abbr = '华润三九' ORDER BY asset_total_assets_yoy_growth DESC LIMIT 1;",
    },
    # Income Sheet - 金花股份 (10 examples)
    {
        "question": "金花股份近几年的利润总额变化趋势",
        "query": "SELECT report_period, total_profit FROM income_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;",
    },
    {
        "question": "金花股份2024年的营业利润是多少",
        "query": "SELECT operating_profit FROM income_sheet WHERE stock_abbr = '金花股份' AND report_year = '2024';",
    },
    {
        "question": "金花股份各项费用的构成情况",
        "query": "SELECT report_period, operating_expense_selling_expenses, operating_expense_administrative_expenses, operating_expense_financial_expenses FROM income_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;",
    },
    {
        "question": "金花股份资产减值损失的最高值",
        "query": "SELECT report_period, asset_impairment_loss FROM income_sheet WHERE stock_abbr = '金花股份' ORDER BY asset_impairment_loss DESC LIMIT 1;",
    },
    {
        "question": "金花股份研发费用投入情况",
        "query": "SELECT report_period, operating_expense_rnd_expenses FROM income_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;",
    },
    {
        "question": "金花股份净利润与利润总额的关系",
        "query": "SELECT report_period, net_profit, total_profit FROM income_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;",
    },
    {
        "question": "金花股份信用减值损失的变化",
        "query": "SELECT report_period, credit_impairment_loss FROM income_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;",
    },
    {
        "question": "金花股份营业总支出最高的报告期",
        "query": "SELECT report_period, total_operating_expenses FROM income_sheet WHERE stock_abbr = '金花股份' ORDER BY total_operating_expenses DESC LIMIT 1;",
    },
    {
        "question": "金花股份其他收益对利润的贡献",
        "query": "SELECT report_period, other_income, total_profit FROM income_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;",
    },
    {
        "question": "金花股份营业支出占比最高的成分",
        "query": "SELECT report_period, operating_expense_cost_of_sales FROM income_sheet WHERE stock_abbr = '金花股份' ORDER BY operating_expense_cost_of_sales DESC LIMIT 1;",
    },
    # Income Sheet - 华润三九 (10 examples)
    {
        "question": "华润三九近几年的利润总额变化趋势",
        "query": "SELECT report_period, total_profit FROM income_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period;",
    },
    {
        "question": "华润三九2024年的营业利润是多少",
        "query": "SELECT operating_profit FROM income_sheet WHERE stock_abbr = '华润三九' AND report_year = '2024';",
    },
    {
        "question": "华润三九各项费用的构成情况",
        "query": "SELECT report_period, operating_expense_selling_expenses, operating_expense_administrative_expenses, operating_expense_financial_expenses FROM income_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period;",
    },
    {
        "question": "华润三九资产减值损失的最高值",
        "query": "SELECT report_period, asset_impairment_loss FROM income_sheet WHERE stock_abbr = '华润三九' ORDER BY asset_impairment_loss DESC LIMIT 1;",
    },
    {
        "question": "华润三九研发费用投入情况",
        "query": "SELECT report_period, operating_expense_rnd_expenses FROM income_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period;",
    },
    {
        "question": "华润三九净利润与利润总额的关系",
        "query": "SELECT report_period, net_profit, total_profit FROM income_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period;",
    },
    {
        "question": "华润三九信用减值损失的变化",
        "query": "SELECT report_period, credit_impairment_loss FROM income_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period;",
    },
    {
        "question": "华润三九营业总支出最高的报告期",
        "query": "SELECT report_period, total_operating_expenses FROM income_sheet WHERE stock_abbr = '华润三九' ORDER BY total_operating_expenses DESC LIMIT 1;",
    },
    {
        "question": "华润三九其他收益对利润的贡献",
        "query": "SELECT report_period, other_income, total_profit FROM income_sheet WHERE stock_abbr = '华润三九' ORDER BY report_period;",
    },
    {
        "question": "华润三九营业支出占比最高的成分",
        "query": "SELECT report_period, operating_expense_cost_of_sales FROM income_sheet WHERE stock_abbr = '华润三九' ORDER BY operating_expense_cost_of_sales DESC LIMIT 1;",
    },
]

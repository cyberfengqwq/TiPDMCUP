import argparse
from pathlib import Path

from pipeline import run_extract, run_prepare, run_rebuild, run_screen


DEFAULT_SCREEN_RULE_TEXT = (
    "如果文本包含主要会计数据、主要财务指标、分季度财务指标、资产负债表、利润表、现金流量表，"
    "或者包含与以下指标直接相关的数值或表格，则回答 YES：营业收入、营业总收入、净利润、扣非净利润、"
    "每股收益、净资产收益率、总资产、总负债、货币资金、应收账款、存货、营业成本、销售费用、管理费用、"
    "财务费用、研发费用、经营活动产生的现金流量净额、投资活动产生的现金流量净额、筹资活动产生的现金流量净额、"
    "收回投资收到的现金、投资支付的现金、取得借款收到的现金、偿还债务支付的现金。"
    "如果文本主要是风险提示、公司治理、审计套话、社会责任、管理层空泛表述、股东信息、非财务介绍，"
    "且不包含上述可抽取财务数据，则回答 NO。只能回答 YES 或 NO。"
)


DEFAULT_EXTRACT_SCHEMA_TEXT = (
    '{\n'
    '  "doc_id": "文档名",\n'
    '  "stock_code": null,\n'
    '  "stock_abbr": null,\n'
    '  "report_year": null,\n'
    '  "report_period": null,\n'
    '  "facts": [\n'
    '    {\n'
    '      "statement": "core_indicator | balance_sheet | income_sheet | cash_flow_sheet | supplementary",\n'
    '      "scope": "consolidated | parent | unknown",\n'
    '      "metric_std": "下方映射表中对应的英文字段名，无匹配则填 null",\n'
    '      "metric_alias": "原文指标名（中文）",\n'
    '      "value": 0,\n'
    '      "value_raw": "原文数值",\n'
    '      "unit": "元 | 万元 | % | 元/股 | 股 | unknown",\n'
    '      "time_role": "YYYY 或 YYYYQX，例如 2023 表示年度，2023Q1 表示一季度，2023Q3 表示三季度",\n'
    '      "table_title": "表名或小节名",\n'
    '      "source_chunk": "chunk_n",\n'
    '      "source_text": "原文片段"\n'
    '    }\n'
    '  ]\n'
    '}\n\n'
    '【重要】字段类型说明：\n'
    '  - 标注[万元]的字段：value 填数值金额，unit 填"万元"或"元"（元会自动换算）\n'
    '  - 标注[元]的字段：value 填数值金额，unit 填"元"\n'
    '  - 标注[%]的字段：value 填百分比数值（如同比增长12.5%填12.5），unit 填"%"，绝对值通常 <300\n'
    '  - 标注[元/股]的字段：value 填每股数值，unit 填"元/股"\n'
    '  注意：同比增长、环比增长、毛利率等[%]字段绝对值一般不超过300，若原文是金额变动数请勿填入增长率字段。\n\n'
    'metric_std 映射表（英文字段名=中文含义[类型]）：\n'
    'core_indicator:\n'
    '  eps=每股收益[元/股]\n'
    '  total_operating_revenue=营业总收入[万元]\n'
    '  operating_revenue_yoy_growth=营业总收入同比增长[%]\n'
    '  operating_revenue_qoq_growth=营业总收入季度环比增长[%]\n'
    '  net_profit_10k_yuan=净利润[万元]\n'
    '  net_profit_yoy_growth=净利润同比增长[%]\n'
    '  net_profit_qoq_growth=净利润季度环比增长[%]\n'
    '  net_asset_per_share=每股净资产[元/股]\n'
    '  roe=净资产收益率[%]\n'
    '  operating_cf_per_share=每股经营现金流量[元/股]\n'
    '  net_profit_excl_non_recurring=扣非净利润[万元]\n'
    '  net_profit_excl_non_recurring_yoy=扣非净利润同比增长[%]\n'
    '  gross_profit_margin=销售毛利率[%]\n'
    '  net_profit_margin=销售净利率[%]\n'
    '  roe_weighted_excl_non_recurring=加权平均净资产收益率（扣非）[%]\n'
    'balance_sheet:\n'
    '  asset_cash_and_cash_equivalents=货币资金[万元]\n'
    '  asset_accounts_receivable=应收账款[万元]\n'
    '  asset_inventory=存货[万元]\n'
    '  asset_trading_financial_assets=交易性金融资产[万元]\n'
    '  asset_construction_in_progress=在建工程[万元]\n'
    '  asset_total_assets=总资产[万元]\n'
    '  asset_total_assets_yoy_growth=总资产同比增长[%]\n'
    '  liability_accounts_payable=应付账款[万元]\n'
    '  liability_advance_from_customers=预收账款[万元]\n'
    '  liability_total_liabilities=总负债[万元]\n'
    '  liability_total_liabilities_yoy_growth=总负债同比增长[%]\n'
    '  liability_contract_liabilities=合同负债[万元]\n'
    '  liability_short_term_loans=短期借款[万元]\n'
    '  asset_liability_ratio=资产负债率[%]\n'
    '  equity_unappropriated_profit=未分配利润[万元]\n'
    '  equity_total_equity=股东权益合计[万元]\n'
    'income_sheet:\n'
    '  net_profit=净利润[万元]\n'
    '  net_profit_yoy_growth=净利润同比增长[%]\n'
    '  other_income=其他收益[万元]\n'
    '  total_operating_revenue=营业总收入[万元]\n'
    '  operating_revenue_yoy_growth=营业总收入同比增长[%]\n'
    '  operating_expense_cost_of_sales=营业成本/营业支出[万元]\n'
    '  operating_expense_selling_expenses=销售费用[万元]\n'
    '  operating_expense_administrative_expenses=管理费用[万元]\n'
    '  operating_expense_financial_expenses=财务费用[万元]\n'
    '  operating_expense_rnd_expenses=研发费用[万元]\n'
    '  operating_expense_taxes_and_surcharges=税金及附加[万元]\n'
    '  total_operating_expenses=营业总支出[万元]\n'
    '  operating_profit=营业利润[万元]\n'
    '  total_profit=利润总额[万元]\n'
    '  asset_impairment_loss=资产减值损失[万元]\n'
    '  credit_impairment_loss=信用减值损失[万元]\n'
    'cash_flow_sheet:\n'
    '  net_cash_flow=现金及现金等价物净增加额[元]\n'
    '  net_cash_flow_yoy_growth=净现金流同比增长[%]\n'
    '  operating_cf_net_amount=经营活动现金流量净额[万元]\n'
    '  operating_cf_cash_from_sales=销售商品收到的现金[万元]\n'
    '  investing_cf_net_amount=投资活动现金流量净额[万元]\n'
    '  investing_cf_cash_for_investments=投资支付的现金[万元]\n'
    '  investing_cf_cash_from_investment_recovery=收回投资收到的现金[万元]\n'
    '  financing_cf_cash_from_borrowing=取得借款收到的现金[万元]\n'
    '  financing_cf_cash_for_debt_repayment=偿还债务支付的现金[万元]\n'
    '  financing_cf_net_amount=筹资活动现金流量净额[万元]'
)


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def resolve_workspace_paths(workspace: Path) -> dict[str, Path]:
    return {
        "workspace": workspace,
        "collected_json": workspace / "collected_json",
        "waiting_chunk": workspace / "waiting_chunk",
        "waiting_markdown": workspace / "waiting_markdown",
        "new_chunk": workspace / "new_chunk",
        "extracted_data": workspace / "extracted_data",
        "extracted_json": workspace / "extracted_json",
        "manifest_file": workspace / "chunk_task_manifest.json",
        "screen_results": workspace / "screen_results.json",
        "extract_results": workspace / "extract_results.json",
    }


def run_all(
    root_o: Path,
    workspace: Path,
    model_path: str,
    screen_rule_text: str,
    extract_schema_text: str,
    char_limit: int,
    temperature: float,
    top_p: float,
    screen_max_tokens: int,
    extract_max_tokens: int,
    gpu_memory_utilization: float,
    execute_prepare: bool,
    separator: str,
) -> None:
    paths = resolve_workspace_paths(workspace)
    ensure_dirs(
        paths["workspace"],
        paths["collected_json"],
        paths["waiting_chunk"],
        paths["waiting_markdown"],
        paths["new_chunk"],
        paths["extracted_data"],
        paths["extracted_json"],
    )

    run_prepare(
        root_o=root_o,
        extracted_json_root=paths["collected_json"],
        waiting_chunk_root=paths["waiting_chunk"],
        manifest_file=paths["manifest_file"],
        char_limit=char_limit,
        dry_run=not execute_prepare,
    )
    if not execute_prepare:
        print("prepare 当前是 dry-run，流程在提取阶段后停止。若要继续完整流程，请加 --execute-prepare。")
        return

    run_screen(
        waiting_chunk_root=paths["waiting_chunk"],
        waiting_markdown_root=paths["waiting_markdown"],
        new_chunk_root=paths["new_chunk"],
        results_file=paths["screen_results"],
        model_path=model_path,
        rule_text=screen_rule_text,
        temperature=temperature,
        top_p=top_p,
        max_tokens=screen_max_tokens,
        gpu_memory_utilization=gpu_memory_utilization,
    )
    run_rebuild(
        new_chunk_root=paths["new_chunk"],
        extracted_data_root=paths["extracted_data"],
        separator=separator,
    )
    run_extract(
        extracted_data_root=paths["extracted_data"],
        extracted_json_root=paths["extracted_json"],
        results_file=paths["extract_results"],
        model_path=model_path,
        schema_text=extract_schema_text,
        temperature=temperature,
        top_p=top_p,
        max_tokens=extract_max_tokens,
        gpu_memory_utilization=gpu_memory_utilization,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified extraction entry: prepare -> screen -> rebuild -> extract."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    all_parser = subparsers.add_parser("all", help="运行完整流程")
    all_parser.add_argument("root_o", help="原始总目录 O")
    all_parser.add_argument("--workspace", default="extract_workspace", help="流程工作目录")
    all_parser.add_argument("--model-path", required=True, help="vLLM 模型路径或模型名")
    all_parser.add_argument("--screen-rule-text", default=DEFAULT_SCREEN_RULE_TEXT, help="初筛规则文本")
    all_parser.add_argument("--extract-schema-text", default=DEFAULT_EXTRACT_SCHEMA_TEXT, help="细筛抽取 schema 文本")
    all_parser.add_argument("--char-limit", type=int, default=6000, help="分块字数阈值")
    all_parser.add_argument("--temperature", type=float, default=0.1, help="采样温度")
    all_parser.add_argument("--top-p", type=float, default=0.8, help="top-p")
    all_parser.add_argument("--screen-max-tokens", type=int, default=32, help="初筛最大输出 token 数")
    all_parser.add_argument("--extract-max-tokens", type=int, default=4096, help="细筛最大输出 token 数")
    all_parser.add_argument("--gpu-memory-utilization", type=float, default=0.63, help="显存占用比例")
    all_parser.add_argument("--execute-prepare", action="store_true", help="实际执行提取和删除 A 目录")
    all_parser.add_argument("--separator", default="\n---\n", help="重组时 chunk 断号插入的分隔线")

    prep_parser = subparsers.add_parser("prepare", help="仅运行提取、分块、manifest")
    prep_parser.add_argument("root_o", help="原始总目录 O")
    prep_parser.add_argument("--workspace", default="extract_workspace", help="流程工作目录")
    prep_parser.add_argument("--char-limit", type=int, default=6000, help="分块字数阈值")
    prep_parser.add_argument("--execute-prepare", action="store_true", help="实际执行提取和删除")

    screen_parser = subparsers.add_parser("screen", help="仅运行初筛")
    screen_parser.add_argument("--workspace", default="extract_workspace", help="流程工作目录")
    screen_parser.add_argument("--model-path", required=True, help="vLLM 模型路径或模型名")
    screen_parser.add_argument("--screen-rule-text", default=DEFAULT_SCREEN_RULE_TEXT, help="初筛规则文本")
    screen_parser.add_argument("--temperature", type=float, default=0.1, help="采样温度")
    screen_parser.add_argument("--top-p", type=float, default=0.8, help="top-p")
    screen_parser.add_argument("--screen-max-tokens", type=int, default=32, help="初筛最大输出 token 数")
    screen_parser.add_argument("--gpu-memory-utilization", type=float, default=0.63, help="显存占用比例")

    rebuild_parser = subparsers.add_parser("rebuild", help="仅运行重组")
    rebuild_parser.add_argument("--workspace", default="extract_workspace", help="流程工作目录")
    rebuild_parser.add_argument("--separator", default="\n---\n", help="重组时 chunk 断号插入的分隔线")

    extract_parser = subparsers.add_parser("extract", help="仅运行细筛抽取")
    extract_parser.add_argument("--workspace", default="extract_workspace", help="流程工作目录")
    extract_parser.add_argument("--model-path", required=True, help="vLLM 模型路径或模型名")
    extract_parser.add_argument("--extract-schema-text", default=DEFAULT_EXTRACT_SCHEMA_TEXT, help="细筛抽取 schema 文本")
    extract_parser.add_argument("--temperature", type=float, default=0.1, help="采样温度")
    extract_parser.add_argument("--top-p", type=float, default=0.8, help="top-p")
    extract_parser.add_argument("--extract-max-tokens", type=int, default=4096, help="细筛最大输出 token 数")
    extract_parser.add_argument("--gpu-memory-utilization", type=float, default=0.63, help="显存占用比例")

    args = parser.parse_args()

    workspace = Path(getattr(args, "workspace", "extract_workspace")).resolve()
    paths = resolve_workspace_paths(workspace)

    if args.command == "all":
        run_all(
            root_o=Path(args.root_o).resolve(),
            workspace=workspace,
            model_path=args.model_path,
            screen_rule_text=args.screen_rule_text,
            extract_schema_text=args.extract_schema_text,
            char_limit=args.char_limit,
            temperature=args.temperature,
            top_p=args.top_p,
            screen_max_tokens=args.screen_max_tokens,
            extract_max_tokens=args.extract_max_tokens,
            gpu_memory_utilization=args.gpu_memory_utilization,
            execute_prepare=args.execute_prepare,
            separator=args.separator,
        )
    elif args.command == "prepare":
        ensure_dirs(paths["workspace"], paths["collected_json"], paths["waiting_chunk"])
        run_prepare(
            root_o=Path(args.root_o).resolve(),
            extracted_json_root=paths["collected_json"],
            waiting_chunk_root=paths["waiting_chunk"],
            manifest_file=paths["manifest_file"],
            char_limit=args.char_limit,
            dry_run=not args.execute_prepare,
        )
    elif args.command == "screen":
        ensure_dirs(paths["workspace"], paths["waiting_markdown"], paths["new_chunk"])
        run_screen(
            waiting_chunk_root=paths["waiting_chunk"],
            waiting_markdown_root=paths["waiting_markdown"],
            new_chunk_root=paths["new_chunk"],
            results_file=paths["screen_results"],
            model_path=args.model_path,
            rule_text=args.screen_rule_text,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.screen_max_tokens,
            gpu_memory_utilization=args.gpu_memory_utilization,
        )
    elif args.command == "rebuild":
        ensure_dirs(paths["workspace"], paths["extracted_data"])
        run_rebuild(
            new_chunk_root=paths["new_chunk"],
            extracted_data_root=paths["extracted_data"],
            separator=args.separator,
        )
    elif args.command == "extract":
        ensure_dirs(paths["workspace"], paths["extracted_json"])
        run_extract(
            extracted_data_root=paths["extracted_data"],
            extracted_json_root=paths["extracted_json"],
            results_file=paths["extract_results"],
            model_path=args.model_path,
            schema_text=args.extract_schema_text,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.extract_max_tokens,
            gpu_memory_utilization=args.gpu_memory_utilization,
        )


if __name__ == "__main__":
    main()

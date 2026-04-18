from core.agent.intent_manager import IntentManager


def main() -> None:
    intent = IntentManager()
    print(
        intent.run(
            "查询2025年第三季度短期借款超过货币资金的公司，用表格列出具体数据，并用柱状图对比这两项指标的差额"
        )
    )


if __name__ == "__main__":
    main()

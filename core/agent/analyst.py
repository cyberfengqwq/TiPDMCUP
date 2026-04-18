# core/agent/analyst.py

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

MULTI_INTENT_PROMPT = """
    你是一位资深的券商金融分析师。用户提出了一个多意图查询，系统已拆解为多个子任务并获取了相应数据。
    请综合所有子任务的数据，生成一份连贯、完整的分析报告。

    【用户原始问题】:
    {question}

    【子任务数据】:
    {sub_task_context}

    【相关研报参考】:
    {report_context}

    要求：
    1. 按问题的逻辑顺序依次回答所有子意图
    2. 语言专业，符合券商研报风格
    3. 不要重复列出原始数据，直接给出分析结论
    4. 如有研报参考，结合研报观点进行佐证
    5. 300-600字为宜

    请直接输出分析文字，不要加任何前缀。
"""

ANALYSIS_PROMPT = """
    你是一位资深的券商金融分析师，请根据以下SQL查询结果，生成专业的财务分析结论。

    【用户问题】:
    {question}

    【SQL查询结果】:
    {sql_result}

    【相关研报参考】:
    {report_context}

    要求：
    1. 直接给出分析结论，不要重复列出原始数据
    2. 语言专业，符合券商研报风格
    3. 指出关键趋势、亮点和风险
    4. 结论简洁有力，200-400字为宜
    5. 如有研报参考，结合研报观点进行佐证

    请直接输出分析文字，不要加任何前缀。
"""


class Analyst:
    def __init__(self, llm) -> None:
        self.llm = llm

    def analyze(
        self,
        question: str,
        sql_result: Any,
        report_refs: list,
    ) -> str:
        """
        根据SQL查询结果生成分析文字

        Args:
            question:    用户原始问题
            sql_result:  SQL执行结果（list of dict 或 字符串）
            report_refs: 研报检索结果列表

        Returns:
            分析文字字符串
        """
        # 格式化SQL结果
        if isinstance(sql_result, list):
            if len(sql_result) == 0:
                sql_str = "查询结果为空"
            elif len(sql_result) <= 20:
                sql_str = json.dumps(sql_result, ensure_ascii=False, indent=2)
            else:
                # 结果太多只取前20条
                sql_str = json.dumps(sql_result[:20], ensure_ascii=False, indent=2)
                sql_str += f"\n...（共{len(sql_result)}条，仅展示前20条）"
        else:
            sql_str = str(sql_result)

        # 格式化研报参考
        if report_refs:
            report_lines = []
            for i, r in enumerate(report_refs, 1):
                report_lines.append(
                    f"[研报{i}] {r.get('org_name', '')} "
                    f"{r.get('publish_date', '')} "
                    f"{r.get('stock_name', '')}: "
                    f"{r.get('text', '')[:200]}"
                )
            report_context = "\n".join(report_lines)
        else:
            report_context = "无相关研报"

        prompt = ANALYSIS_PROMPT.format(
            question=question,
            sql_result=sql_str,
            report_context=report_context,
        )

        logger.info(f"[Analyst] 生成分析，问题={question[:50]}")

        # 分析文字需要更长的输出
        original_max = self.llm.max_tokens
        self.llm.set_sampling_params(
            _temperature=0.7,
            _top_p=0.9,
            _max_tokens=1024,
        )

        try:
            result = self.llm.chat(prompt).strip()
        finally:
            # 还原参数
            self.llm.set_sampling_params(
                _temperature=self.llm.temperature,
                _top_p=self.llm.top_p,
                _max_tokens=original_max,
            )

        logger.info(f"[Analyst] 分析完成，输出长度={len(result)}")

        return result

    def analyze_multi(
        self,
        question: str,
        sub_results: list[dict],
        report_refs: list,
    ) -> str:
        """
        多意图版本：sub_results = [{"sub_q": ..., "sql": ..., "data": [...]}]
        综合所有子任务数据生成统一分析。
        """
        sub_task_parts = []
        for i, sr in enumerate(sub_results, 1):
            sub_q = sr.get("sub_q", "")
            data = sr.get("data", [])
            if data:
                data_str = json.dumps(data[:10], ensure_ascii=False, indent=2)
                if len(data) > 10:
                    data_str += f"\n...（共{len(data)}条，仅展示前10条）"
            else:
                data_str = "未查询到数据"
            sub_task_parts.append(f"【子任务{i}】{sub_q}\n数据：{data_str}")

        sub_task_context = "\n\n".join(sub_task_parts)

        if report_refs:
            report_lines = [
                f"[研报{i}] {r.get('org_name', '')} {r.get('publish_date', '')} "
                f"{r.get('stock_name', '')}: {r.get('text', '')[:200]}"
                for i, r in enumerate(report_refs, 1)
            ]
            report_context = "\n".join(report_lines)
        else:
            report_context = "无相关研报"

        prompt = MULTI_INTENT_PROMPT.format(
            question=question,
            sub_task_context=sub_task_context,
            report_context=report_context,
        )

        original_max = self.llm.max_tokens
        self.llm.set_sampling_params(_temperature=0.7, _top_p=0.9, _max_tokens=1500)

        try:
            result = self.llm.chat(prompt).strip()
        finally:
            self.llm.set_sampling_params(
                _temperature=self.llm.temperature,
                _top_p=self.llm.top_p,
                _max_tokens=original_max,
            )

        logger.info(f"[Analyst] 多意图分析完成，输出长度={len(result)}")
        return result

# core/agent/intent_manager.py

import json

from pydantic import BaseModel, Field, ValidationError

from config.db_schema import DATABASE_SCHEMA_DICT
from core.services.llm_service import LLM


class QuerySlots(BaseModel):
    company: str | None = Field(default=None, description="上市公司名称")
    year: str | None = Field(default=None, description="查询年份")
    period: str | None = Field(default=None, description="报告期")
    metric: str | None = Field(default=None, description="财务指标英文键名")
    is_complete: bool = Field(default=False, description="核心要素是否完整")
    missing_reason: str | None = Field(default=None, description="缺失原因")


class IntentGatekeeper:
    def __init__(self) -> None:
        self.llm = LLM()
        self.schema_dict = DATABASE_SCHEMA_DICT
        self.valid_metric_keys = self.collect_metric_keys()

    def collect_metric_keys(self) -> list[str]:
        keys: list[str] = []
        for _, fields in self.schema_dict.items():
            keys.extend(list(fields.keys()))
        return sorted(set(keys))

    def analyze(self, user_input: str, history: str = "") -> QuerySlots:
        prompt = f"""
            你是财务问答意图抽取器。提取槽位：company, year, period, metric。
            合法 metric 仅可从以下键中选择：
            {self.valid_metric_keys}

            对话历史：
            {history}

            当前输入：
            {user_input}

            只输出 JSON，不要解释，不要 markdown。
            格式：
            {{
            "company": "... or null",
            "year": "... or null",
            "period": "... or null",
            "metric": "... or null",
            "is_complete": true/false,
            "missing_reason": "... or null"
            }}
            """
        raw = self.llm.chat(prompt).strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(raw)
            slots = QuerySlots.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            return QuerySlots(
                is_complete=False,
                missing_reason="意图解析失败，请补充公司、年份、报告期和指标信息",
            )

        # 二次强校验
        if slots.metric and slots.metric not in self.valid_metric_keys:
            slots.metric = None

        complete = all([slots.company, slots.year, slots.period, slots.metric])
        slots.is_complete = complete
        if not complete and not slots.missing_reason:
            slots.missing_reason = "缺少公司/年份/报告期/指标中的至少一项"

        return slots

# core/agent/intent_manager.py

import json
import logging

from pydantic import BaseModel, Field, ValidationError

from config.db_schema import DATABASE_SCHEMA_DICT
from core.services.vllm_service import LLM

_INTENT_MODEL_PATH = "/home/qwq/models/Qwen3-VL-2B-sty"

logger = logging.getLogger(__name__)


class QuerySlots(BaseModel):
    company: str | None = Field(default=None, description="上市公司名称")
    year: str | None = Field(default=None, description="查询年份")
    period: str | None = Field(default=None, description="报告期")
    metric: str | None = Field(default=None, description="财务指标英文键名")
    is_complete: bool = Field(default=False, description="核心要素是否完整")
    missing_reason: str | None = Field(default=None, description="缺失原因，用于直接回复用户")


# ── Prompt 模板 ───────────────────────────────────────────────────────────────
# 核心设计原则：
#   1. 角色约束放在最前面，强制模型不进入"回答问题"模式
#   2. 用 few-shot 示例固定输出格式，防止模型自由发挥
#   3. 明确列出合法 metric，减少幻觉
#   4. 输出约束重复强调，针对中文大模型爱加前缀的问题
# ─────────────────────────────────────────────────────────────────────────────
_SYSTEM_ROLE = """\
你是一个财务数据库查询系统的意图槽位抽取器。
你的唯一任务是从用户输入中抽取四个槽位：company（公司）、year（年份）、period（报告期）、metric（指标）。
你不会回答问题、不会分析数据、不会预测、不会解释。只做槽位抽取，只输出 JSON。"""

_FEW_SHOT = """\
示例1
输入：金花股份2025年第三季度利润总额是多少
输出：{"company":"金花股份","year":"2025","period":"三季报","metric":"total_profit","is_complete":true,"missing_reason":null}

示例2
输入：比亚迪的净利润
输出：{"company":"比亚迪","year":null,"period":null,"metric":"net_profit_10k_yuan","is_complete":false,"missing_reason":"请问您想查询比亚迪哪个年份和报告期的净利润？例如：2024年年报、2025年三季报。"}

示例3
输入：2024年年报营业收入
输出：{"company":null,"year":"2024","period":"年报","metric":"total_operating_revenue","is_complete":false,"missing_reason":"请问您想查询哪家公司2024年年报的营业收入？"}

示例4
输入：帮我分析一下财报
输出：{"company":null,"year":null,"period":null,"metric":null,"is_complete":false,"missing_reason":"请告诉我您想查询的公司名称、年份、报告期和财务指标，例如：云南白药2024年年报净利润。"}

示例5
输入：宁王最近挣钱了吗
输出：{"company":"宁德时代","year":null,"period":null,"metric":"net_profit_10k_yuan","is_complete":false,"missing_reason":"请问您想查询宁德时代哪个年份和报告期的净利润？例如：2024年年报或2025年三季报。"}

示例6
输入：最近表现好的公司有哪些
输出：{"company":null,"year":null,"period":null,"metric":null,"is_complete":false,"missing_reason":"请补充查询条件：1. 哪个报告期？2. "表现好"您关注的是净利润、营业收入还是ROE等具体指标？"}"""

_METRIC_HINT = "合法 metric 键（只能从中选择，不可自造）：\n{metric_keys}"

_OUTPUT_RULE = """\
输出规则（严格执行）：
- 只输出一个 JSON 对象，不加任何前缀、后缀、解释、markdown
- 第一个字符必须是 {，最后一个字符必须是 }
- missing_reason：意图完整时为 null；意图不完整时写一句中文引导话术，直接对用户说"""

_PROMPT_TEMPLATE = """\
{system_role}

{few_shot}

{metric_hint}

{output_rule}

对话历史（最近几轮，用于理解上下文补全）：
{history}

当前用户输入：
{user_input}

JSON输出："""


class IntentGatekeeper:
    def __init__(self) -> None:
        self.llm = LLM(_modelpath=_INTENT_MODEL_PATH, _gpu_memory_utilization=0.15)
        self.llm.load_model()
        self.schema_dict = DATABASE_SCHEMA_DICT
        self.valid_metric_keys = self._collect_metric_keys()

    def _collect_metric_keys(self) -> list[str]:
        keys: list[str] = []
        for _, fields in self.schema_dict.items():
            keys.extend(list(fields.keys()))
        return sorted(set(keys))

    def _build_prompt(self, user_input: str, history: str) -> str:
        # metric 键太多时只取前60个，避免 context 过长导致模型乱输出
        metric_sample = self.valid_metric_keys[:60]
        metric_hint = _METRIC_HINT.format(metric_keys=", ".join(metric_sample))

        return _PROMPT_TEMPLATE.format(
            system_role=_SYSTEM_ROLE,
            few_shot=_FEW_SHOT,
            metric_hint=metric_hint,
            output_rule=_OUTPUT_RULE,
            history=history.strip() if history.strip() else "（无历史）",
            user_input=user_input.strip(),
        )

    def _parse_raw(self, raw: str) -> dict | None:
        """从模型输出中提取 JSON，兼容模型加了多余前缀/后缀的情况"""
        raw = raw.strip()

        # 去除常见包裹
        for wrap in ["```json", "```", "json"]:
            raw = raw.replace(wrap, "")
        raw = raw.strip()

        # 直接解析
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 找最外层 {...}
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass

        logger.warning(f"[IntentGatekeeper] JSON解析失败，原始输出：{raw[:200]}")
        return None

    def analyze(self, user_input: str, history: str = "") -> QuerySlots:
        prompt = self._build_prompt(user_input, history)

        try:
            raw = self.llm.chat(prompt).strip()
        except Exception as e:
            logger.error(f"[IntentGatekeeper] LLM调用失败: {e}")
            return QuerySlots(
                is_complete=False,
                missing_reason="服务暂时不可用，请稍后重试。",
            )

        logger.debug(f"[IntentGatekeeper] 原始输出: {raw[:300]}")

        data = self._parse_raw(raw)
        if data is None:
            return QuerySlots(
                is_complete=False,
                missing_reason="请告诉我您想查询的公司名称、年份、报告期和财务指标。",
            )

        try:
            slots = QuerySlots.model_validate(data)
        except ValidationError as e:
            logger.warning(f"[IntentGatekeeper] Pydantic校验失败: {e}")
            return QuerySlots(
                is_complete=False,
                missing_reason="请告诉我您想查询的公司名称、年份、报告期和财务指标。",
            )

        # ── 二次强校验 ────────────────────────────────────────────────────────
        # metric 必须是合法键，否则清空（防止模型编造）
        if slots.metric and slots.metric not in self.valid_metric_keys:
            logger.info(
                f"[IntentGatekeeper] 非法metric={slots.metric!r}，已清空"
            )
            slots.metric = None

        # 重新计算 is_complete（不信任模型自己给的值）
        complete = all([slots.company, slots.year, slots.period, slots.metric])
        slots.is_complete = complete

        # 如果完整但 missing_reason 不为 null，清空
        if complete:
            slots.missing_reason = None

        # 如果不完整但没有 missing_reason，自动生成
        if not complete and not slots.missing_reason:
            missing_fields = []
            if not slots.company:
                missing_fields.append("公司名称")
            if not slots.year:
                missing_fields.append("年份")
            if not slots.period:
                missing_fields.append("报告期")
            if not slots.metric:
                missing_fields.append("财务指标")
            slots.missing_reason = (
                f"请补充以下信息：{'、'.join(missing_fields)}。"
                "例如：云南白药2024年年报净利润。"
            )

        logger.info(
            f"[IntentGatekeeper] 解析结果: company={slots.company}, "
            f"year={slots.year}, period={slots.period}, "
            f"metric={slots.metric}, complete={slots.is_complete}"
        )

        return slots
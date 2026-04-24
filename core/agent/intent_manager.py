# core/agent/intent_manager.py

import json
import logging

from pydantic import BaseModel, Field, ValidationError

from config.db_schema import DATABASE_SCHEMA_DICT
from core.services.vllm_service import LLM

_INTENT_MODEL_PATH = "/home/qwq/TiPDMCUP/models/Qwen3-VL-2B-Intent"

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
        self.llm = LLM(
            _modelpath=_INTENT_MODEL_PATH,
            _gpu_memory_utilization=0.15,
            _max_model_len=4096,
            _limit_mm_per_prompt={"image": 0, "video": 0},
            _enforce_eager=True,
        )
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
        # 有年份+报告期 → 有明确的时间范围，SQL 模型可以处理公司/指标的灵活性
        # 没有时间范围 → 查询太模糊，需要引导用户补充
        complete = bool(slots.year and slots.period)
        slots.is_complete = complete

        # 如果完整但 missing_reason 不为 null，清空
        if complete:
            slots.missing_reason = None

        # 如果不完整但没有 missing_reason，自动生成
        if not complete and not slots.missing_reason:
            if slots.company and not slots.year and not slots.period:
                slots.missing_reason = (
                    f"请问您想查询{slots.company}哪个年份和报告期的数据？"
                    "例如：2024年年报、2025年三季报。"
                )
            elif slots.year and not slots.period:
                slots.missing_reason = (
                    f"请问您想查询{slots.year}年的哪个报告期？"
                    "例如：年报、三季报、半年报、一季报。"
                )
            else:
                slots.missing_reason = (
                    "请告诉我您想查询的年份和报告期，"
                    "例如：云南白药2024年年报净利润。"
                )

        logger.info(
            f"[IntentGatekeeper] 解析结果: company={slots.company}, "
            f"year={slots.year}, period={slots.period}, "
            f"metric={slots.metric}, complete={slots.is_complete}"
        )

        return slots


# ── 轻量规则门卫（不依赖 ML 模型，适用于 batch 模式）────────────────────────────

import re as _re

_YEAR_RE = _re.compile(r"20\d{2}")
_PERIOD_KEYWORDS = [
    "年报", "年度报告", "FY",
    "半年报", "半年度", "HY", "上半年",
    "一季报", "一季度", "Q1", "第一季度",
    "三季报", "三季度", "Q3", "第三季度", "前三季度",
]
# 相对时间词：有这些词时视为有隐含时间，不拦截
_RELATIVE_TIME = ["去年", "今年", "最新", "最近", "近几年", "历年", "近三年", "近年来"]
_COMPANY_RE = _re.compile(r"[一-龥]{2,8}(?:股份|集团|制药|医药|药业|药品|生物|科技|健康)")
# 不是公司名的常见词，排除误匹配
_NON_COMPANY = {"销售费用", "研发费用", "管理费用", "财务费用", "营业收入", "净利润", "利润总额",
                "营业利润", "总资产", "总负债", "资产负债", "现金流", "毛利率", "净利率"}


class LiteGatekeeper:
    """
    基于正则规则的轻量意图门卫，无需加载 ML 模型。

    拦截策略（比 ML 门卫宽松）：
    - 只要有年份（如 2024）或报告期关键词 → 放行，让 SQL 模型处理报告期选择
    - 有相对时间（去年/今年/最新）→ 放行
    - 什么时间信息都没有 → 拦截，追问年份和报告期
    """

    def analyze(self, user_input: str, history: str = "") -> QuerySlots:
        combined = (history + " " + user_input).strip()

        # 提取年份（优先从当前输入，兜底从历史）
        year_m = _YEAR_RE.search(user_input) or _YEAR_RE.search(history)
        year = year_m.group(0) if year_m else None

        # 检测报告期关键词
        period = None
        for kw in _PERIOD_KEYWORDS:
            if kw in combined:
                period = kw
                break

        # 相对时间词
        has_relative = any(w in combined for w in _RELATIVE_TIME)

        # 提取公司名（仅从当前输入，用于生成追问话术）
        company = None
        for m in _COMPANY_RE.finditer(user_input):
            candidate = m.group(0)
            if candidate not in _NON_COMPANY and len(candidate) >= 2:
                company = candidate
                break

        # 只要有任何时间线索就放行
        complete = bool(year or period or has_relative)

        if complete:
            return QuerySlots(year=year, period=period, company=company, is_complete=True)

        # 生成追问话术
        company_str = company or "该公司"
        reason = (
            f"请问您想查询{company_str}哪个年份和报告期的数据？"
            "例如：2024年年报、2025年三季报。"
        )

        logger.info(f"[LiteGatekeeper] 意图不完整: year={year}, period={period}")
        return QuerySlots(
            year=year, period=period, company=company,
            is_complete=False, missing_reason=reason,
        )
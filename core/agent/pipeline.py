# core/agent/pipeline.py


import json
import logging
import re
import threading
from pathlib import Path
from typing import Any

from core.agent.analyst import Analyst
from core.agent.intent_manager import IntentGatekeeper, LiteGatekeeper
from core.agent.sql_autocorrector import try_execute_with_autocorrect
from core.agent.visualizer import _detect_chart_type, draw_chart
from core.rag.memory_retrieval import UserProfileRetrieval
from core.rag.provenance_store import ProvenanceStore
from core.rag.report_retriever import ReportRetrieval
from core.rag.sql_retriever import DualRetrieval
from core.services.db_service import DBService  # MySQL执行层，见下方说明
from core.services.vllm_service import LLM, TransformersLLM
from core.stores.chat_store import ChatStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_REPORT_PERSIST = (
    Path(__file__).resolve().parent.parent.parent / "data" / "faiss_report_store"
)
_REPORT_DATA_ROOT = Path.home() / "正式数据" / "附件5：研报数据"
_STOCK_DIR = _REPORT_DATA_ROOT / "个股研报"
_INDUSTRY_DIR = _REPORT_DATA_ROOT / "行业研报"
_STOCK_META = _REPORT_DATA_ROOT / "个股_研报信息.xlsx"
_INDUSTRY_META = _REPORT_DATA_ROOT / "行业_研报信息.xlsx"

_report_retrieval: ReportRetrieval | None = None
_gatekeeper: IntentGatekeeper | None = None
_provenance_store: ProvenanceStore | None = None
_model_lock = threading.Lock()  # 同一时刻只允许一个大模型在 GPU 上运行

_EXTRACTED_JSON_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "core"
    / "data_extract"
    / "extract_workspace"
    / "extracted_json"
)


def _get_provenance_store() -> ProvenanceStore:
    global _provenance_store
    if _provenance_store is None:
        _provenance_store = ProvenanceStore(_EXTRACTED_JSON_DIR)
    return _provenance_store


def _get_gatekeeper() -> IntentGatekeeper:
    global _gatekeeper
    if _gatekeeper is None:
        _gatekeeper = IntentGatekeeper()
    return _gatekeeper


def _get_report_retrieval() -> ReportRetrieval:
    global _report_retrieval
    if _report_retrieval is None:
        r = ReportRetrieval(persist_root=str(_REPORT_PERSIST))
        r.sync_if_changed(
            stock_report_dir=_STOCK_DIR,
            industry_report_dir=_INDUSTRY_DIR,
            stock_meta_xlsx=_STOCK_META if _STOCK_META.exists() else None,
            industry_meta_xlsx=_INDUSTRY_META if _INDUSTRY_META.exists() else None,
        )
        _report_retrieval = r
    return _report_retrieval


class Agent:
    def __init__(
        self,
        user_id: str,
        company_id: str,
        chat_id: str,
        sql_llm: LLM | TransformersLLM,
        analysis_llm: LLM | TransformersLLM,
        skip_gatekeeper: bool = False,
        use_lite_gatekeeper: bool = False,
    ) -> None:
        self.user_id = user_id
        self.company_id = company_id
        self.chat_id = chat_id

        self.rag = DualRetrieval(user_id=user_id)
        self.memory = UserProfileRetrieval(user_id=user_id)
        self.report_retrieval = _get_report_retrieval()
        self.provenance = _get_provenance_store()
        self.chat_store = ChatStore(chat_id=chat_id)
        self.sql_llm = sql_llm
        self.analyst = Analyst(analysis_llm)
        self.db = DBService()
        self.skip_gatekeeper = skip_gatekeeper
        if skip_gatekeeper:
            self.gatekeeper = None
        elif use_lite_gatekeeper:
            self.gatekeeper = LiteGatekeeper()
        else:
            self.gatekeeper = _get_gatekeeper()

    def build_history_text(self, limit: int = 6) -> str:
        history = self.chat_store.get_history()
        if not history:
            return ""
        return "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')}"
            for m in history[-limit:]
        )

    def retrieve_rag_context(self, question: str) -> dict:
        """执行 RAG 检索，返回结构化上下文（可独立保存到日志/JSON）。"""
        rag_result = self.rag.retrieve(question)
        return {
            "similar_questions": [
                {"question": item.get("text", ""), "sql": item.get("sql", ""), "score": item.get("score")}
                for item in rag_result.get("similar_questions", [])
            ],
            "relevant_fields": [
                {"table": item.get("table", ""), "field": item.get("field", ""), "description": item.get("description", ""), "score": item.get("score")}
                for item in rag_result.get("relevant_fields", [])
            ],
            "user_preferences": self.memory.search_preference(question, top_k=3),
        }

    def build_sql_prompt(self, question: str, history_text: str = "", rag_context: dict | None = None) -> str:
        if rag_context is None:
            rag_context = self.retrieve_rag_context(question)
        similar_questions = [{"text": item["question"], "sql": item["sql"]} for item in rag_context.get("similar_questions", [])]
        relevant_fields = [{"table": item["table"], "field": item["field"], "description": item["description"]} for item in rag_context.get("relevant_fields", [])]
        relevant_preferences = rag_context.get("user_preferences", [])

        example_lines = [
            f"[示例{i}] 问题：{item.get('text', '')} SQL：{item.get('sql', '')}"
            for i, item in enumerate(similar_questions, 1)
        ]
        field_lines = [
            f"[字段{i}] 表={item.get('table', '')}, 字段={item.get('field', '')}, 含义={item.get('description', '')}"
            for i, item in enumerate(relevant_fields, 1)
        ]

        prompt = f"""你是一个 MySQL 专家，专门为中药上市公司财务数据库生成精确的 SQL 查询语句。

【数据库核心规则】（必须严格遵守）

1. report_period 合法值（只能从中选择，不得自造）：
   2022FY  2023FY  2023HY  2023Q1  2023Q3
   2024FY  2024HY  2024Q1  2024Q3
   2025HY  2025Q1  2025Q3
   - FY=年报  HY=半年报  Q1=一季报  Q3=三季报
   - 注意：没有 Q2、Q4，"前三季度"对应 Q3，"上半年"对应 HY
   - "最新数据"/"最近"/"最后" → 不要猜期，用 ORDER BY report_period DESC LIMIT n
   - "去年" → 相对当前最新期 2025Q3，去年最近期是 2024FY 或 2024Q3

2. 数值单位：
   - 数据库中金额字段单位为【万元】（标注[元]的字段除外）
   - "200亿" = 200×10000万 = 2000000（万元）
   - "1亿" = 10000（万元）

3. 公司名称模糊匹配：
   - 用户可能用简称/品牌名，如"999"→"华润三九"，"三九"→"华润三九"
   - 不确定时用 stock_abbr LIKE '%关键词%' 或同时列出多个候选

4. 跨表 JOIN 规则：
   - JOIN 时必须同时匹配 stock_abbr 和 report_period（防止笛卡尔积）
   - 示例：JOIN income_sheet i ON cf.stock_abbr=i.stock_abbr AND cf.report_period=i.report_period

5. 问题没有指定时间时：
   - 不要猜测期号，用 ORDER BY report_period DESC LIMIT 1 取最新一期

6. report_year 字段存储字符串，如 '2024'，筛选时用 report_year = '2024'

【四张表结构】
- core_performance_indicators_sheet：每股收益、营业总收入、净利润、ROE、毛利率等核心指标
- balance_sheet：总资产、总负债、应收账款、存货、资产负债率等资产负债表
- income_sheet：营业收入、各项费用、营业利润、净利润等利润表
- cash_flow_sheet：经营/投资/筹资现金流净额等现金流量表

【本轮对话历史】:
{history_text if history_text.strip() else "无"}

【用户专属偏好记忆】:
{chr(10).join([f"- {p}" for p in relevant_preferences]) if relevant_preferences else "无"}

【当前问题】:
{question}

【相似历史问答参考】:
{chr(10).join(example_lines) if example_lines else "无"}

【相关数据库字段】:
{chr(10).join(field_lines) if field_lines else "无"}

只输出一条可执行的 MySQL SQL，不要任何解释、注释或 markdown。"""

        return prompt.strip()

    def _decompose_intents(self, question: str) -> list[str]:
        """
        用分析模型将多意图问题拆解为有序子问题列表。
        单意图问题返回 [question]。
        """
        prompt = (
            "你是一个中药上市公司财务数据库的查询规划器。\n"
            "任务：将用户问题拆解为若干个【可独立查数据库的子问题】，每个子问题只包含一个查询意图。\n\n"
            "拆解规则：\n"
            "1. 只有问题包含明显的多个独立数据需求时才拆解（如：先查A，再查B，再比较）\n"
            "2. 每个子问题必须保留原问题中涉及的公司名、年份、报告期等关键信息\n"
            "3. 如果原问题只有一个数据查询意图，直接返回原问题\n"
            "4. 如果问题涉及数据库中没有的外部信息（如政策文件、医保目录），也返回原问题\n\n"
            "示例：\n"
            '输入："2024年净利润最高的top5企业有哪些？它们的营收同比增长是多少？"\n'
            '输出：["2024年净利润最高的top5中药上市公司有哪些", "这top5公司2024年营收同比增长分别是多少"]\n\n'
            '输入："华润三九2024年的净利润和毛利率"\n'
            '输出：["华润三九2024年的净利润和毛利率"]\n\n'
            "要求：只输出JSON数组，第一个字符必须是[，最后一个字符必须是]，不要任何解释。\n\n"
            f"用户问题：{question}\n"
            "JSON数组："
        )
        try:
            raw = self.analyst.llm.chat(prompt).strip()
            match = re.search(r"\[.*?\]", raw, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                if isinstance(parsed, list) and all(isinstance(q, str) for q in parsed):
                    result = [q.strip() for q in parsed if q.strip()]
                    if result:
                        return result
        except Exception as e:
            logger.warning(f"[Agent] 意图拆解失败: {e}")
        return [question]

    def _run_multi_intent(
        self,
        question: str,
        sub_questions: list[str],
        problem_id: str,
        history_text: str,
    ) -> dict:
        """执行多意图子任务，合并结果，返回标准 Q/A dict。"""
        # Phase 1: 一次性加载 SQL 模型，批量生成所有子问题的 SQL
        sql_list: list[tuple[str, str]] = []
        with _model_lock:
            self.sql_llm.load_model()
            try:
                for sub_q in sub_questions:
                    sql_prompt = self.build_sql_prompt(sub_q, history_text)
                    sql = self.sql_llm.chat(sql_prompt).strip()
                    sql = sql.replace("```sql", "").replace("```", "").strip()
                    sql_list.append((sub_q, sql))
            finally:
                self.sql_llm.unload_model()

        # Phase 2: 执行 SQL（不需要模型）
        sub_results: list[dict] = []
        for sub_q, sql in sql_list:
            data: list = []
            if sql and not sql.startswith("--"):
                try:
                    data = self.db.execute(sql)
                except Exception as e:
                    logger.warning(f"[Agent] 子任务SQL失败 ({sub_q[:30]}): {e}")
            sub_results.append({"sub_q": sub_q, "sql": sql, "data": data})
            logger.info(f"[Agent] 子任务完成: {sub_q[:40]}, 返回{len(data)}行")

        report_refs = self.get_report_references(question)

        # 溯源：汇总所有子任务的数据行
        all_rows: list[dict] = []
        all_sqls = " ".join(sr.get("sql", "") for sr in sub_results)
        for sr in sub_results:
            all_rows.extend(sr.get("data") or [])
        provenance_refs = self.provenance.lookup_rows(all_rows, sql=all_sqls)
        logger.info(
            f"[Agent._run_multi_intent] 溯源找到{len(provenance_refs)}条原文记录"
        )

        # Phase 3: 加载分析模型，合并分析
        with _model_lock:
            self.analyst.llm.load_model()
            try:
                content = self.analyst.analyze_multi(question, sub_results, report_refs)
            finally:
                self.analyst.llm.unload_model()

        # 为有数据的子任务依次绘图（最多3张）
        image_paths: list[str] = []
        chart_type = "none"
        seq = 1
        for sr in sub_results:
            if not sr["data"]:
                continue
            ct = _detect_chart_type(sr["sub_q"], sr["data"])
            if ct == "none":
                continue
            if chart_type == "none":
                chart_type = ct
            path = draw_chart(
                question=sr["sub_q"],
                sql_result=sr["data"],
                problem_id=problem_id,
                seq=seq,
            )
            if path:
                image_paths.append(path)
                seq += 1
            if seq > 3:
                break

        # 存对话历史
        self.chat_store.append_messages(
            [
                {"role": "user", "content": question},
                {"role": "assistant", "content": content},
            ]
        )
        first_sql = next(
            (
                sr["sql"]
                for sr in sub_results
                if sr["sql"] and not sr["sql"].startswith("--")
            ),
            "",
        )
        if first_sql:
            self.rag.add_user_interaction(question, first_sql)

        combined_sql = "\n\n".join(
            f"-- {sr['sub_q']}\n{sr['sql']}"
            for sr in sub_results
            if sr["sql"] and not sr["sql"].startswith("--")
        )

        answer: dict = {
            "content": content,
            "image": image_paths,
            "sql": combined_sql,
            "chart_type": chart_type,
            "sql_corrected": False,
            "sql_result": sub_results,
        }

        multi_refs: list[dict] = []
        for p in provenance_refs:
            multi_refs.append(
                {
                    "type": "provenance",
                    "stock_abbr": p.get("stock_abbr", ""),
                    "metric_alias": p.get("metric_alias", ""),
                    "value_raw": p.get("value_raw", ""),
                    "table_title": p.get("table_title", ""),
                    "source_text": p.get("source_text", ""),
                    "source_chunk": p.get("source_chunk", ""),
                    "doc_id": p.get("doc_id", ""),
                }
            )
        for r in report_refs:
            multi_refs.append(
                {
                    "type": "report",
                    "paper_path": r.get("paper_path", ""),
                    "text": r.get("text", "")[:300],
                    "paper_image": r.get("paper_image", ""),
                }
            )
        if multi_refs:
            answer["references"] = multi_refs
        return {"Q": question, "A": answer}

    def get_report_references(self, question: str) -> list:
        """获取赛题references格式的研报引用"""
        if self.report_retrieval.index is None:
            return []
        return self.report_retrieval.search_reports(question, top_k=3)

    def run(self, question: str, problem_id: str = "B0000", task: int = 2) -> dict:
        """
        完整pipeline，返回赛题要求的格式

        Args:
            question:   用户问题
            problem_id: 问题编号，用于图表命名
            task:       2=任务二，3=任务三

        Returns:
            {
                "Q": question,
                "A": {
                    "content": "分析文字",
                    "image": ["./result/B1002_1.jpg"],
                    "sql": "SELECT ...",           # 附加字段，方便调试
                    "references": [...],           # 仅任务三有
                }
            }
        """
        logger.info(f"[Agent.run] 问题={question}, task={task}")

        history_text = self.build_history_text()
        intent_info: dict[str, Any] = {"gatekeeper": None, "decompose": None}

        # ========== Step0: 意图完整性检测（仅任务二）==========
        # 任务三问题常无具体公司名（发现类/模糊意图），跳过 gatekeeper
        if task == 2:
            if self.gatekeeper is None:
                intent_info["gatekeeper"] = {"skipped": True}
            else:
                slots = self.gatekeeper.analyze(question, history_text)
                intent_info["gatekeeper"] = (
                    slots.model_dump() if hasattr(slots, "model_dump") else None
                )
                if not slots.is_complete:
                    hint = (
                        slots.missing_reason
                        or "请补充查询所需的公司名称、年份、报告期和财务指标。"
                    )
                    self.chat_store.append_messages(
                        [
                            {"role": "user", "content": question},
                            {"role": "assistant", "content": hint},
                        ]
                    )
                    logger.info(f"[Agent.run] 意图不完整，已拦截: {hint}")
                    return {
                        "Q": question,
                        "A": {
                            "content": hint,
                            "image": [],
                            "sql": "",
                            "chart_type": "none",
                            "sql_corrected": False,
                            "sql_result": [],
                            "intent_info": intent_info,
                        },
                    }

        # ========== Step0b: 多意图规划（任务三）==========
        if task == 3:
            with _model_lock:
                self.analyst.llm.load_model()
                try:
                    sub_questions = self._decompose_intents(question)
                finally:
                    self.analyst.llm.unload_model()
            intent_info["decompose"] = {"sub_questions": sub_questions}
            if len(sub_questions) > 1:
                logger.info(f"[Agent.run] 多意图拆解为{len(sub_questions)}个子任务")
                result = self._run_multi_intent(
                    question, sub_questions, problem_id, history_text
                )
                result["A"]["intent_info"] = intent_info
                return result

        # ========== Step1: RAG 检索 + 生成SQL ==========
        rag_context = self.retrieve_rag_context(question)
        sql_prompt = self.build_sql_prompt(question, history_text, rag_context)
        with _model_lock:
            self.sql_llm.load_model()
            try:
                sql = self.sql_llm.chat(sql_prompt).strip()
            finally:
                self.sql_llm.unload_model()
        sql = sql.replace("```sql", "").replace("```", "").strip()
        logger.info(f"[Agent.run] 生成SQL={sql}")

        # ========== Step2: 执行SQL ==========
        sql_result: Any = []
        sql_corrected = False
        if sql and not sql.startswith("--"):
            try:
                with _model_lock:
                    self.sql_llm.load_model()
                    try:
                        sql, sql_result, sql_corrected = try_execute_with_autocorrect(
                            db_service=self.db,
                            sql_llm=self.sql_llm,
                            user_question=question,
                            generated_sql=sql,
                            max_retries=1,
                        )
                    finally:
                        self.sql_llm.unload_model()
                logger.info(f"[Agent.run] SQL执行成功，返回{len(sql_result)}行")
            except Exception as e:
                logger.warning(f"[Agent.run] SQL执行失败(含自纠错): {e}")
                sql_result = []

        # ========== Step2b: 溯源查找 ==========
        provenance_refs = []
        if isinstance(sql_result, list) and sql_result:
            provenance_refs = self.provenance.lookup_rows(sql_result, sql=sql)
            logger.info(f"[Agent.run] 溯源找到{len(provenance_refs)}条原文记录")

        # ========== Step3: 检索研报 ==========
        report_refs = []
        if task == 3:
            report_refs = self.get_report_references(question)
            logger.info(f"[Agent.run] 研报检索到{len(report_refs)}条")

        # ========== Step4: 生成分析文字 ==========
        with _model_lock:
            self.analyst.llm.load_model()
            try:
                if sql_result:
                    content = self.analyst.analyze(
                        question=question,
                        sql_result=sql_result,
                        report_refs=report_refs,
                    )
                else:
                    if report_refs:
                        content = self.analyst.analyze(
                            question=question,
                            sql_result="数据库中未查询到相关数据",
                            report_refs=report_refs,
                        )
                    elif task == 3:
                        # task=3 意图模糊类：数据库无法回答，结合问题给出说明
                        content = self.analyst.analyze(
                            question=question,
                            sql_result=(
                                "本数据库仅包含中药上市公司的结构化财务数据（利润表、资产负债表、"
                                "现金流量表、核心指标），暂无该问题所需数据，"
                                "请尝试查询具体公司的财务指标。"
                            ),
                            report_refs=[],
                        )
                    else:
                        content = "未能查询到相关数据，请确认公司名称和报告期是否正确。"
            finally:
                self.analyst.llm.unload_model()

        # ========== Step5: 生成图表 ==========
        image_path = ""
        chart_type = "none"
        if isinstance(sql_result, list) and len(sql_result) > 0:
            chart_type = _detect_chart_type(question, sql_result)
            image_path = draw_chart(
                question=question,
                sql_result=sql_result,
                problem_id=problem_id,
                seq=1,
            )

        # ========== Step6: 存历史 ==========
        self.chat_store.append_messages(
            [
                {"role": "user", "content": question},
                {"role": "assistant", "content": content},
            ]
        )
        if sql and not sql.startswith("--"):
            self.rag.add_user_interaction(question, sql)

        # ========== Step7: 组装返回值 ==========
        answer: dict = {
            "content": content,
            "image": [image_path] if image_path else [],
            "sql": sql,
            "chart_type": chart_type,
            "sql_corrected": sql_corrected,
            "sql_result": sql_result,
            "intent_info": intent_info,
            "rag_context": rag_context,
        }

        references: list[dict] = []

        # 数据溯源：原文出处（任务二、三均提供）
        for p in provenance_refs:
            references.append(
                {
                    "type": "provenance",
                    "stock_abbr": p.get("stock_abbr", ""),
                    "metric_alias": p.get("metric_alias", ""),
                    "value_raw": p.get("value_raw", ""),
                    "table_title": p.get("table_title", ""),
                    "source_text": p.get("source_text", ""),
                    "source_chunk": p.get("source_chunk", ""),
                    "doc_id": p.get("doc_id", ""),
                }
            )

        # 研报引用（仅任务三）
        if task == 3:
            for r in report_refs:
                references.append(
                    {
                        "type": "report",
                        "paper_path": r.get("paper_path", ""),
                        "text": r.get("text", "")[:300],
                        "paper_image": r.get("paper_image", ""),
                    }
                )

        if references:
            answer["references"] = references

        return {"Q": question, "A": answer}

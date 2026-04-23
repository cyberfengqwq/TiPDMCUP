# core/agent/pipeline.py


import json
import logging
import re
import threading
from pathlib import Path
from typing import Any

from core.agent.analyst import Analyst
from core.agent.intent_manager import IntentGatekeeper
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
    / "core" / "data_extract" / "extract_workspace" / "extracted_json"
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
    def __init__(self, user_id: str, company_id: str, chat_id: str, sql_llm: LLM | TransformersLLM, analysis_llm: LLM | TransformersLLM) -> None:
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
        self.gatekeeper = _get_gatekeeper()

    def build_history_text(self, limit: int = 6) -> str:
        history = self.chat_store.get_history()
        if not history:
            return ""
        return "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')}"
            for m in history[-limit:]
        )

    def build_sql_prompt(self, question: str, history_text: str = "") -> str:
        rag_result = self.rag.retrieve(question)
        similar_questions = rag_result.get("similar_questions", [])
        relevant_fields = rag_result.get("relevant_fields", [])
        relevant_preferences = self.memory.search_preference(question, top_k=3)

        example_lines = [
            f"[示例{i}] 问题：{item.get('text', '')} SQL：{item.get('sql', '')}"
            for i, item in enumerate(similar_questions, 1)
        ]
        field_lines = [
            f"[字段{i}] 表={item.get('table', '')}, 字段={item.get('field', '')}, 含义={item.get('description', '')}"
            for i, item in enumerate(relevant_fields, 1)
        ]

        prompt = f"""
        你是一个资深的金融数据分析师。

        【本轮对话历史】:
        {history_text if history_text.strip() else "无"}

        【用户专属偏好记忆】:
        {chr(10).join([f"- {p}" for p in relevant_preferences]) if relevant_preferences else "无"}

        【当前问题】:
        {question}

        【可参考的历史问答与SQL】:
        {chr(10).join(example_lines) if example_lines else "无"}

        【相关数据库字段】:
        {chr(10).join(field_lines) if field_lines else "无"}

        请直接输出一条可执行的 MySQL SQL。不要解释。
        """

        return prompt.strip()

    def _decompose_intents(self, question: str) -> list[str]:
        """
        用分析模型将多意图问题拆解为有序子问题列表。
        单意图问题返回 [question]。
        """
        prompt = (
            "你是一个查询规划器。请将用户的问题拆解为2-5个可独立执行SQL查询的子问题，"
            "每个子问题只包含一个查询意图。\n"
            "如果问题本身是单一意图，直接输出原问题即可。\n"
            "严格以JSON数组格式输出，例如：[\"子问题1\", \"子问题2\"]\n"
            "只输出JSON数组，不要任何解释。\n\n"
            f"用户问题：{question}"
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
        for sr in sub_results:
            all_rows.extend(sr.get("data") or [])
        provenance_refs = self.provenance.lookup_rows(all_rows)
        logger.info(f"[Agent._run_multi_intent] 溯源找到{len(provenance_refs)}条原文记录")

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
        self.chat_store.append_messages([
            {"role": "user", "content": question},
            {"role": "assistant", "content": content},
        ])
        first_sql = next(
            (sr["sql"] for sr in sub_results if sr["sql"] and not sr["sql"].startswith("--")),
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
        }

        multi_refs: list[dict] = []
        for p in provenance_refs:
            multi_refs.append({
                "type": "provenance",
                "stock_abbr": p.get("stock_abbr", ""),
                "metric_alias": p.get("metric_alias", ""),
                "value_raw": p.get("value_raw", ""),
                "table_title": p.get("table_title", ""),
                "source_text": p.get("source_text", ""),
                "source_chunk": p.get("source_chunk", ""),
                "doc_id": p.get("doc_id", ""),
            })
        for r in report_refs:
            multi_refs.append({
                "type": "report",
                "paper_path": r.get("paper_path", ""),
                "text": r.get("text", "")[:300],
                "paper_image": r.get("paper_image", ""),
            })
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

        # ========== Step0: 意图完整性检测（仅任务二）==========
        # 任务三问题常无具体公司名（发现类/模糊意图），跳过 gatekeeper
        if task == 2:
            slots = self.gatekeeper.analyze(question, history_text)
            if not slots.is_complete:
                hint = slots.missing_reason or "请补充查询所需的公司名称、年份、报告期和财务指标。"
                self.chat_store.append_messages([
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": hint},
                ])
                logger.info(f"[Agent.run] 意图不完整，已拦截: {hint}")
                return {"Q": question, "A": {"content": hint, "image": [], "sql": "", "chart_type": "none"}}

        # ========== Step0b: 多意图规划（任务三）==========
        if task == 3:
            with _model_lock:
                self.analyst.llm.load_model()
                try:
                    sub_questions = self._decompose_intents(question)
                finally:
                    self.analyst.llm.unload_model()
            if len(sub_questions) > 1:
                logger.info(f"[Agent.run] 多意图拆解为{len(sub_questions)}个子任务")
                return self._run_multi_intent(question, sub_questions, problem_id, history_text)

        # ========== Step1: 生成SQL ==========
        sql_prompt = self.build_sql_prompt(question, history_text)
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
        if sql and not sql.startswith("--"):
            try:
                sql_result = self.db.execute(sql)
                logger.info(f"[Agent.run] SQL执行成功，返回{len(sql_result)}行")
            except Exception as e:
                logger.warning(f"[Agent.run] SQL执行失败: {e}")
                sql_result = []

        # ========== Step2b: 溯源查找 ==========
        provenance_refs = []
        if isinstance(sql_result, list) and sql_result:
            provenance_refs = self.provenance.lookup_rows(sql_result)
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
        }

        references: list[dict] = []

        # 数据溯源：原文出处（任务二、三均提供）
        for p in provenance_refs:
            references.append({
                "type": "provenance",
                "stock_abbr": p.get("stock_abbr", ""),
                "metric_alias": p.get("metric_alias", ""),
                "value_raw": p.get("value_raw", ""),
                "table_title": p.get("table_title", ""),
                "source_text": p.get("source_text", ""),
                "source_chunk": p.get("source_chunk", ""),
                "doc_id": p.get("doc_id", ""),
            })

        # 研报引用（仅任务三）
        if task == 3:
            for r in report_refs:
                references.append({
                    "type": "report",
                    "paper_path": r.get("paper_path", ""),
                    "text": r.get("text", "")[:300],
                    "paper_image": r.get("paper_image", ""),
                })

        if references:
            answer["references"] = references

        return {"Q": question, "A": answer}

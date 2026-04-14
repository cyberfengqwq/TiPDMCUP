# core/agent/pipeline.py


import logging
from pathlib import Path

# from core.agent.intent_manager import IntentGatekeeper
from core.rag.memory_retrieval import UserProfileRetrieval
from core.rag.report_retriever import ReportRetrieval
from core.rag.sql_retriever import DualRetrieval
from core.services.vllm_service import LLM
from core.stores.chat_store import ChatStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_REPORT_PERSIST = Path(__file__).resolve().parent.parent.parent / "data" / "faiss_report_store"

_REPORT_DATA_ROOT = Path.home() / "正式数据" / "附件5：研报数据"
_STOCK_DIR = _REPORT_DATA_ROOT / "个股研报"
_INDUSTRY_DIR = _REPORT_DATA_ROOT / "行业研报"
_STOCK_META = _REPORT_DATA_ROOT / "个股_研报信息.xlsx"
_INDUSTRY_META = _REPORT_DATA_ROOT / "行业_研报信息.xlsx"

_report_retrieval: ReportRetrieval | None = None


def _get_report_retrieval() -> ReportRetrieval:
    """
    单例。服务首次使用时自动扫描研报目录：
    - 有新增/修改/删除 PDF → 重建索引
    - 无变化 → 直接复用已有索引
    """
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
    def __init__(self, user_id: str, company_id: str, chat_id: str, llm: LLM) -> None:
        self.user_id = user_id
        self.company_id = company_id
        self.chat_id = chat_id

        self.rag = DualRetrieval(user_id=user_id, company_id=company_id)
        self.memory = UserProfileRetrieval(user_id=user_id)
        self.report_retrieval = _get_report_retrieval()
        self.chat_store = ChatStore(chat_id=chat_id)
        self.llm = llm
        # self.intent = IntentGatekeeper()

    def build_history_text(self, limit: int = 6) -> str:
        history: list[dict] = self.chat_store.get_history()
        if not history:
            return ""
        recent = history[-limit:]
        return "\n".join(
            [f"{m.get('role', 'unknown')}: {m.get('content', '')}" for m in recent]
        )

    def build_prompt(self, question: str) -> str:
        rag_result: dict = self.rag.retrieve(question)
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

        report_refs = []
        if self.report_retrieval.index is not None:
            report_refs = self.report_retrieval.search_reports(question, top_k=3)
        report_lines = [
            f"[研报{i}] {r.get('org_name', '')} {r.get('publish_date', '')} {r.get('stock_name', '')}: {r.get('text', '')}"
            for i, r in enumerate(report_refs, 1)
        ]

        prompt = f"""
        你是一个资深的金融数据分析师。

        【用户专属偏好记忆（请尽量迎合）】:
        {chr(10).join([f"- {p}" for p in relevant_preferences]) if relevant_preferences else "无"}

        【当前问题】:
        {question}

        【可参考的历史问答与SQL】:
        {chr(10).join(example_lines) if example_lines else "无"}

        【相关数据库字段】:
        {chr(10).join(field_lines) if field_lines else "无"}

        【相关研报参考】:
        {chr(10).join(report_lines) if report_lines else "无"}

        请直接输出一条可执行的 MySQL SQL。不要解释。
        """

        logger.info(f"RAG生成的提示词：\n{prompt}")
        return prompt.strip()

    def get_report_references(self, question: str) -> list:
        """返回赛题 references 格式的研报引用"""
        if self.report_retrieval.index is None:
            return []
        return self.report_retrieval.search_reports(question, top_k=3)

    def run(self, question: str) -> str:
        # history: str = self.build_history_text()
        # slots = self.intent.analyze(question, history)

        # if not slots.is_complete:
        # return f"-- 信息不足: {slots.missing_reason or '请补充公司、年份、报告期、指标'}"

        logger.info(f"用户输入自然语言：{question}")

        prompt = self.build_prompt(question)

        sql = self.llm.chat(prompt).strip()
        sql = sql.replace("```sql", "").replace("```", "").strip()

        # 存入上下文 JSON
        self.chat_store.append_messages(
            [
                {"role": "user", "content": question},
                {"role": "assistant", "content": sql},
            ]
        )

        if sql and not sql.startswith("-- 信息不足"):
            self.rag.add_user_interaction(question, sql)

        return sql

# core/agent/pipeline.py


import logging
from pathlib import Path
from typing import Any

from core.agent.analyst import Analyst
from core.agent.visualizer import draw_chart
from core.rag.memory_retrieval import UserProfileRetrieval
from core.rag.report_retriever import ReportRetrieval
from core.rag.sql_retriever import DualRetrieval
from core.services.db_service import DBService  # MySQL执行层，见下方说明
from core.services.vllm_service import LLM
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
    def __init__(self, user_id: str, company_id: str, chat_id: str, llm: LLM) -> None:
        self.user_id = user_id
        self.company_id = company_id
        self.chat_id = chat_id

        self.rag = DualRetrieval(user_id=user_id, company_id=company_id)
        self.memory = UserProfileRetrieval(user_id=user_id)
        self.report_retrieval = _get_report_retrieval()
        self.chat_store = ChatStore(chat_id=chat_id)
        self.llm = llm
        self.analyst = Analyst(llm)
        self.db = DBService()  # MySQL连接，见db_service.py

    def build_history_text(self, limit: int = 6) -> str:
        history = self.chat_store.get_history()
        if not history:
            return ""
        return "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')}"
            for m in history[-limit:]
        )

    def build_sql_prompt(self, question: str) -> str:
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

        # ========== Step1: 生成SQL ==========
        sql_prompt = self.build_sql_prompt(question)
        sql = self.llm.chat(sql_prompt).strip()
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

        # ========== Step3: 检索研报 ==========
        report_refs = []
        if task == 3:
            report_refs = self.get_report_references(question)
            logger.info(f"[Agent.run] 研报检索到{len(report_refs)}条")

        # ========== Step4: 生成分析文字 ==========
        if sql_result:
            content = self.analyst.analyze(
                question=question,
                sql_result=sql_result,
                report_refs=report_refs,
            )
        else:
            # SQL无结果时，尝试直接用研报回答（适合任务三意图模糊场景）
            if report_refs:
                content = self.analyst.analyze(
                    question=question,
                    sql_result="数据库中未查询到相关数据",
                    report_refs=report_refs,
                )
            else:
                content = "未能查询到相关数据，请确认公司名称和报告期是否正确。"

        # ========== Step5: 生成图表 ==========
        image_path = ""
        if isinstance(sql_result, list) and len(sql_result) > 0:
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
        }

        if task == 3 and report_refs:
            answer["references"] = [
                {
                    "paper_path": r.get("paper_path", ""),
                    "text": r.get("text", "")[:300],
                    "paper_image": r.get("paper_image", ""),
                }
                for r in report_refs
            ]

        return {"Q": question, "A": answer}

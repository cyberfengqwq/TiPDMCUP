import logging
from pathlib import Path

from core.llm import LLM
from rag.sql_retriever import DualRetrieval

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, session_id: str = "default_session_id") -> None:
        self.session_id = session_id
        self.rag = DualRetrieval(user=session_id)
        self.llm = LLM()
        self.llm.role = (
            "你是一个资深的金融数据分析师。"
            "请根据给定的数据库字段信息和历史SQL示例，把用户问题转为 MySQL SQL。"
            "只输出纯 SQL，不要解释，不要 markdown 代码块。"
        )

    def build_prompt(self, question: str) -> str:
        rag_result: dict = self.rag.retrieve(question)

        similar_questions = rag_result.get("similar_questions", [])
        relevant_fields = rag_result.get("relevant_fields", [])

        example_lines: list[str] = []

        for i, item in enumerate(similar_questions, 1):
            example_lines.append(
                f"[示例{i}]\n问题：{item.get('text', '')}\nSQL：{item.get('sql, ')}"
            )

        field_lines: list[str] = []

        for i, item in enumerate(relevant_fields, 1):
            field_lines.append(
                f"[字段{i}] 表={item.get('table', '')}, "
                f"字段={item.get('field', '')}, "
                f"含义={item.get('description', '')}"
            )

        prompt = f"""
        用户问题:
        {question}

        可参考的历史问答与SQL:
        {chr(10).join(example_lines) if example_lines else "无"}

        相关数据库字段:
        {chr(10).join(field_lines) if field_lines else "无"}

        请直接输出一条可执行的 MySQL SQL。
        """

        logger.info(f"RAG生成的提示词：{prompt}")

        return prompt.strip()

    def run(self, question: str) -> str:
        logger.info(f"用户输入自然语言：{question}")
        prompt = self.build_prompt(question)
        sql = self.llm.chat(prompt).strip()

        sql = sql.replace("```sql", "").replace("```", "").strip()

        if sql and not sql.startswith("-- 信息不足"):
            self.rag.add_user_interaction(question, sql)

        return sql

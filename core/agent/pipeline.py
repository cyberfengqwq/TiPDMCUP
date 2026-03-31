# core/agent/pipeline.py


import logging

from core.rag.memory_retrieval import UserProfileRetrieval
from core.rag.sql_retriever import DualRetrieval
from core.services.llm_service import LLM
from core.stores.chat_store import ChatStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, user_id: str, company_id: str, chat_id: str) -> None:
        self.user_id = user_id
        self.company_id = company_id
        self.chat_id = chat_id

        self.rag = DualRetrieval(user_id=user_id)
        self.memory = UserProfileRetrieval(user_id=user_id)
        self.chat_store = ChatStore(chat_id=chat_id)
        self.llm = LLM()

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

        请直接输出一条可执行的 MySQL SQL。不要解释。
        """

        logger.info(f"RAG生成的提示词：\n{prompt}")
        return prompt.strip()

    def run(self, question: str) -> str:
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

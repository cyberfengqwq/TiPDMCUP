# agent/pipeline.py

from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate

from config.db_schema import TABLE_SCHEMA
from core.llm import LLM
from rag.sql_retriever import DynamicSQLRetriever


class Agent:
    def __init__(self) -> None:
        self.llm = LLM()
        self.retriever = DynamicSQLRetriever()

        self.example_prompt = PromptTemplate(
            input_variables=["question", "query"],
            template="历史问题: {question}\n优质SQL: {query}",
        )

        self.dynamic_prompt_template = FewShotPromptTemplate(
            example_selector=self.retriever.get_selector(),
            example_prompt=self.example_prompt,
            prefix=f"请参考以下表结构和相似的优质历史SQL，为用户的新问题生成准确的SQL语句：\n{TABLE_SCHEMA}\n【参考经验】",
            suffix="\n【当前任务】\n用户问题: {input}\n生成的SQL:",
            input_variables=["input"],
        )

    def run_pipeline(self, user_input: str) -> str:
        prompt: str = self.dynamic_prompt_template.format(input=user_input)

        sql: str = self.llm.chat(prompt)

        clean_sql: str = sql.replace("```sql", "").replace("```", "").strip()
        return clean_sql

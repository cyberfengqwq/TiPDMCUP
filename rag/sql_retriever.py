# rag/sql_retriever.py

from langchain_community.vectorstores import Chroma
from langchain_core.example_selectors import SemanticSimilarityExampleSelector
from langchain_huggingface import HuggingFaceEmbeddings

from config.db_schema import SQL_EXAMPLES


class DynamicSQLRetriever:
    def __init__(self) -> None:
        self.embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3", model_kwargs={"device": "cuda"}
        )

        self.example_selector = SemanticSimilarityExampleSelector.from_examples(
            examples=SQL_EXAMPLES,
            embeddings=self.embeddings,
            vectorstore_cls=Chroma,
            k=1,
        )

    def get_selector(self) -> SemanticSimilarityExampleSelector:
        return self.example_selector

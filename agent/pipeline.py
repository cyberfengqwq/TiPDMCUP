from pathlib import Path

from core.llm import LLM
from rag.sql_retriever import Retrieval


class Agent:
    def __init__(self, user: str = "") -> None:
        base_dir: Path = Path.cwd()
        user_data_dir = base_dir / "user_data"
        self.rag = Retrieval(
            user=user, persist_root=user_data_dir / user / "faiss_dual_store"
        )
        self.llm = LLM()

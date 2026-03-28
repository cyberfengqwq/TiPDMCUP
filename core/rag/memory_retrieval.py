# core/rag/memery_retrieval.py

import logging
import time
from pathlib import Path

import faiss

from core.rag.sql_retriever import Retrieval

logger = logging.getLogger(__name__)

ROOT_DIR: Path = Path.cwd()
USER_DATA_DIR: Path = ROOT_DIR / "data" / "users"
USER_DATA_DIR.mkdir(exist_ok=True, parents=True)


class UserProfileRetrieval(Retrieval):
    def __init__(
        self,
        user_id: str,
        model_name: str = "BAAI/bge-m3",
        dimension: int = 1024,
    ) -> None:
        self.user_id = user_id
        self.profile_dir: Path = USER_DATA_DIR / user_id / "profile_faiss"
        self.profile_dir.mkdir(exist_ok=True, parents=True)

        super().__init__(model_name=model_name, persist_root=self.profile_dir)

    def get_persist_paths(self) -> None:
        self.index_path = self.persist_root / "profile_index.faiss"
        self.meta_path = self.persist_root / "profile_meta.json"

    def add_preferences(self, facts: list[str]) -> None:
        if not facts:
            return

        assert self._lock is not None
        with self._lock:
            if not self.index:
                self.index = faiss.IndexFlatL2(self.dimension)

            new_data = [
                {"text": fact, "type": "user_preference", "timestamp": time.time()}
                for fact in facts
            ]
            self.meta += new_data

            embeddings = self.encode_text(facts)
            self.index.add(embeddings)  # type: ignore

            self.save_index()
            logger.info(
                f"成功将 {len(facts)} 条偏好记忆写入用户 {self.user_id} 的向量库"
            )

    def search_preference(self, qurey: str, top_k: int = 3) -> list:
        results = self.search(qurey, top_k)
        return [result.get("text") for result in results if result.get("text")]

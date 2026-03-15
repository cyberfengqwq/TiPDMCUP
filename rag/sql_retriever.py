# rag/sql_retriever.py

import json
import logging
import os

# from FlagEmbedding import BGEM3FlagModel
from typing import Dict, List, Optional

import faiss
import numpy as np
from langchain_huggingface import HuggingFaceEmbeddings


class Retrieval:
    def __init__(
        self,
        model_name: str = "BAAI/bge-m3-finance",
        dimension: int = 1024,
        user: str = "",
        persist_root: str = "./faiss_dual_store",
    ) -> None:
        self.model_name = model_name
        self.embedding = HuggingFaceEmbeddings(model_name=model_name)
        self.dimension = dimension

        self.persist_root = persist_root
        self.field_dir = os.path.join(persist_root, f"field_store_{user}")
        self.case_dir = os.path.join(persist_root, "case_store")
        os.makedirs(self.field_dir, exist_ok=True)
        os.makedirs(self.case_dir, exist_ok=True)

    def encode_text(self, texts: List[str]) -> List[np.ndarray]:
        embeddings = self.embedding.embed_documents(texts)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings

    def build_filed_index(self, field_data: List[str]):
        if not field_data:
            logger.warning("字段名为空")
            return

        self.field_data = field_data
        embeddings = self.encode_text(field_data)
        self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(embeddings)
        logger.info(f"字段名索引构建完成，共{len(field_data)}个字段")

    def build_case_index(self, field_data: List[str]):
        if not field_data:
            logger.warning("历史用例为空")
            return

        self.case_data = field_data
        embeddings = self.encode_text(field_data)
        self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(embeddings)
        logger.info(f"历史用例索引构建完成，共{len(field_data)}个字段")

    def save(self, index_path: str = None):
        if index_path is None:
            index_path = os.path.join(self.persist_root, "index.faiss")
        faiss.write_index(self.index, index_path)
        logger.info(f"索引保存完成，保存路径：{self.persist_root}")

    def load(self, index_path: str = None):
        if index_path is None:
            index_path = os.path.join(self.persist_root, "index.faiss")
        self.index = faiss.read_index(index_path)
        logger.info(f"索引加载完成，加载路径：{self.persist_root}")

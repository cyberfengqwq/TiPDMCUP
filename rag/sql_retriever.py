# rag/sql_retriever.py

import logging

# from FlagEmbedding import BGEM3FlagModel
from pathlib import Path
from typing import List, Dict, Optional

import faiss
import numpy as np
from langchain_huggingface import HuggingFaceEmbeddings

from config.db_schema import DATABASE_SCHEMA_DICT as SCHEMA, SQL_EXAMPLES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Retrieval:
    """
    基类检索

    """
    def __init__(
        self,
        model_name: str = "BAAI/bge-m3-finance",
        dimension: int = 1024,
        user: str = "",
        persist_root: str | Path = "./faiss_store",
    ) -> None:
        # 初始化模型与参数
        self.model_name = model_name
        self.embedding = HuggingFaceEmbeddings(model_name=model_name)
        self.dimension = dimension

        # 构造目录
        self.persist_root = Path(persist_root)
        self.persist_root.mkdir(parents=True, exist_ok=True)

        # 需子类覆盖的核心属性（Path对象）
        self.index_path: Optional[Path] = None
        self.meta_path: Optional[Path] = None
        self.index: Optional[faiss.Index] = None
        self.meta: List[Dict] = []

        # 初始化流程
        self._get_persist_paths()
        self._load_or_init_index()

    # =============通用操作==============
    def encode_text(self, texts: List[str]) -> np.ndarray:
        """将文本编码为向量"""
        embeddings = self.embedding.embed_documents(texts)
        embeddings = np.array(embeddings, dtype=np.float32)
        embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        return embeddings

    def build_index(self, data: List[Dict]):
        """构建索引"""
        if not data:
            logging.warning("数据为空")
            return

        self.meta = data
        texts = [item["text"] for item in data]
        embeddings = self.encode_text(texts)
        self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(embeddings)
        logging.info(f"索引构建完成，共{len(data)}条数据")

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """搜索最相似的内容"""
        if self.index is None:
            logging.warning("索引未初始化")
            return []

        query_embedding = self.encode_text([query])
        distances, indices = self.index.search(query_embedding, top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.meta):
                result = self.meta[idx].copy()
                result["distance"] = float(distances[0][i])
                results.append(result)
        
        return results

    def save_index(self):
        """保存索引和元数据"""
        if self.index_path is None or self.meta_path is None:
            return
        
        if self.index is not None:
            faiss.write_index(self.index, str(self.index_path))
        
        if self.meta:
            import json
            with open(self.meta_path, "w", encoding="utf-8") as f:
                json.dump(self.meta, f, ensure_ascii=False, indent=2)
        
        logging.info(f"索引已保存到 {self.index_path}")

    def _get_persist_paths(self):
        """子类需要实现此方法来设置索引和元数据的保存路径"""
        pass

    def _load_or_init_index(self):
        """加载已存在的索引或初始化新索引"""
        if self.index_path is None or self.meta_path is None:
            return
        
        if self.index_path.exists() and self.meta_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
                import json
                with open(self.meta_path, "r", encoding="utf-8") as f:
                    self.meta = json.load(f)
                logging.info(f"索引已从 {self.index_path} 加载")
            except Exception as e:
                logging.warning(f"加载索引失败: {e}，将创建新索引")
                self.index = None
                self.meta = []



class UserRetrieval(Retrieval):
    def __init__(self, model_name: str = "BAAI/bge-m3-finance", persist_root: str = "./faiss_global", user: str = ""):
        if hasattr(self, "index_path"):
            return
        self.user = user
        super().__init__(model_name=model_name, persist_root=persist_root)
        self._load_user_history()
    
    def _get_persist_paths(self):
        """设置用户历史问题的索引和元数据保存路径"""
        if self.user:
            user_dir = self.persist_root / self.user
            user_dir.mkdir(parents=True, exist_ok=True)
            self.index_path = user_dir / "user_index.faiss"
            self.meta_path = user_dir / "user_meta.json"
        else:
            self.index_path = self.persist_root / "user_index.faiss"
            self.meta_path = self.persist_root / "user_meta.json"
    
    def _load_user_history(self):
        """从 config 目录加载用户历史问题和 SQL_EXAMPLES"""
        if self.index is not None and len(self.meta) > 0:
            return
        
        import json
        from pathlib import Path
        
        user_data = []
        
        for example in SQL_EXAMPLES:
            user_data.append({
                "text": example.get("question", ""),
                "sql": example.get("query", ""),
                "type": "sql_example"
            })
        
        config_dir = Path(__file__).parent.parent / "config"
        history_file = config_dir / f"{self.user}_history_db.json" if self.user else config_dir / "history_db.json"
        
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    history_data = json.load(f)
                
                if history_data and isinstance(history_data, list):
                    for item in history_data:
                        if item:
                            user_data.append({
                                "text": item.get("question", ""),
                                "sql": item.get("query", ""),
                                "type": "user_question"
                            })
            except Exception as e:
                logging.warning(f"加载用户历史失败: {e}")
        
        if user_data:
            self.build_index(user_data)
            logging.info(f"已加载 {len(user_data)} 条历史记录（含 SQL_EXAMPLES）")
    
    def add_user_question(self, question: str, sql: str):
        """添加用户问题和对应的SQL到索引中"""
        if not hasattr(self, "index") or self.index is None:
            self.index = faiss.IndexFlatL2(self.dimension)
        
        item = {
            "text": question,
            "sql": sql,
            "type": "user_question"
        }
        self.meta.append(item)
        
        embedding = self.encode_text([question])
        self.index.add(embedding)
        logging.info(f"已添加用户问题: {question[:50]}...")
    
    def search_similar_questions(self, query: str, top_k: int = 3) -> List[Dict]:
        """搜索相似的历史问题"""
        return self.search(query, top_k)


class FieldDataRetrieval(Retrieval):
    def __init__(self, model_name: str = "BAAI/bge-m3-finance", persist_root: str = "./faiss_global"):
        if hasattr(self, "index_path"):
            return
        super().__init__(model_name=model_name, persist_root=persist_root)
        self._init_field_index()
    
    def _get_persist_paths(self):
        """设置字段信息的索引和元数据保存路径"""
        self.index_path = self.persist_root / "field_index.faiss"
        self.meta_path = self.persist_root / "field_meta.json"
    
    def _init_field_index(self):
        """初始化数据库字段索引"""
        if self.index is not None and len(self.meta) > 0:
            return
        
        field_data = []
        for table_name, fields in SCHEMA.items():
            for field_name, field_desc in fields.items():
                field_data.append({
                    "text": f"{field_desc} ({field_name})",
                    "table": table_name,
                    "field": field_name,
                    "description": field_desc,
                    "type": "field"
                })
        
        if field_data:
            self.build_index(field_data)
            self.save_index()
    
    def search_relevant_fields(self, query: str, top_k: int = 5) -> List[Dict]:
        """搜索相关的数据库字段"""
        return self.search(query, top_k)
    
    def get_table_fields(self, table_name: str) -> List[Dict]:
        """获取指定表的所有字段"""
        return [item for item in self.meta if item.get("table") == table_name]


class DualRetrieval:
    """双重检索器：同时检索用户历史问题和数据库字段信息"""
    
    _shared_field_retrieval: Optional["FieldDataRetrieval"] = None
    _field_store_path = "./faiss_field_store"
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-m3-finance",
        persist_root: str | Path = "./faiss_dual_store",
        user: str = ""
    ):
        self.persist_root = Path(persist_root)
        self.user = user
        
        user_store_path = self.persist_root / "user_store"
        
        self.user_retrieval = UserRetrieval(
            model_name=model_name,
            persist_root=str(user_store_path),
            user=user
        )
        
        if DualRetrieval._shared_field_retrieval is None:
            DualRetrieval._shared_field_retrieval = FieldDataRetrieval(
                model_name=model_name,
                persist_root=DualRetrieval._field_store_path
            )
        
        self.field_retrieval = DualRetrieval._shared_field_retrieval
    
    def retrieve(self, query: str, top_k_questions: int = 3, top_k_fields: int = 5) -> Dict:
        """执行双重检索：返回相似问题和相关字段"""
        similar_questions = self.user_retrieval.search_similar_questions(query, top_k_questions)
        relevant_fields = self.field_retrieval.search_relevant_fields(query, top_k_fields)
        
        return {
            "similar_questions": similar_questions,
            "relevant_fields": relevant_fields
        }
    
    def add_user_interaction(self, question: str, sql: str):
        """添加用户交互记录"""
        self.user_retrieval.add_user_question(question, sql)
        self.user_retrieval.save_index()
    
    def get_all_tables(self) -> List[str]:
        """获取所有表名"""
        tables = set()
        for item in self.field_retrieval.meta:
            if "table" in item:
                tables.add(item["table"])
        return list(tables)
    
    def get_schema_info(self) -> Dict:
        """获取数据库结构信息"""
        schema_info = {}
        for table_name in self.get_all_tables():
            schema_info[table_name] = self.field_retrieval.get_table_fields(table_name)
        return schema_info

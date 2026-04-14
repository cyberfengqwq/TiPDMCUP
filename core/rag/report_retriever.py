# core/rag/report_retriever.py

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

import fitz  # pymupdf

from .sql_retriever import Retrieval

logger = logging.getLogger(__name__)


class ReportRetrieval(Retrieval):
    """
    研报知识库检索器
    支持个股研报和行业研报的向量化检索
    返回内容包含原文摘要、来源路径、图表引用
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        persist_root: str = "./faiss_report_store",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        super().__init__(model_name=model_name, persist_root=persist_root)

    def get_persist_paths(self):
        self.index_path = self.persist_root / "report_index.faiss"
        self.meta_path = self.persist_root / "report_meta.json"

    def _extract_text_from_pdf(self, pdf_path: Path) -> str:
        """提取PDF全文"""
        try:
            doc = fitz.open(str(pdf_path))
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text.strip()
        except Exception as e:
            logger.warning(f"PDF读取失败 {pdf_path}: {e}")
            return ""

    def _chunk_text(self, text: str) -> List[str]:
        """按固定长度分块，带重叠"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            start += self.chunk_size - self.chunk_overlap
        return [c.strip() for c in chunks if len(c.strip()) > 50]

    def build_from_folders(
        self,
        stock_report_dir: str | Path,
        industry_report_dir: str | Path,
        stock_meta_xlsx: Optional[str | Path] = None,
        industry_meta_xlsx: Optional[str | Path] = None,
    ):
        """
        从研报文件夹构建向量索引
        stock_report_dir:    个股研报文件夹
        industry_report_dir: 行业研报文件夹
        stock_meta_xlsx:     个股_研报信息.xlsx（可选，用于补充公司名/评级等元数据）
        industry_meta_xlsx:  行业_研报信息.xlsx（可选）
        """
        stock_dir = Path(stock_report_dir)
        industry_dir = Path(industry_report_dir)

        # 加载Excel元数据（title→stockName/industryName映射）
        stock_meta_map: Dict[str, Dict] = {}
        industry_meta_map: Dict[str, Dict] = {}

        if stock_meta_xlsx:
            try:
                import pandas as pd

                df = pd.read_excel(stock_meta_xlsx)
                for _, row in df.iterrows():
                    title = str(row.get("title", "")).strip()
                    if title:
                        stock_meta_map[title] = {
                            "stock_name": row.get("stockName", ""),
                            "stock_code": str(row.get("stockCode", "")),
                            "org_name": row.get("orgSName", ""),
                            "rating": row.get("emRatingName", ""),
                            "publish_date": str(row.get("publishDate", ""))[:10],
                            "industry": row.get("indvInduName", ""),
                        }
            except Exception as e:
                logger.warning(f"加载个股元数据失败: {e}")

        if industry_meta_xlsx:
            try:
                import pandas as pd

                df = pd.read_excel(industry_meta_xlsx)
                for _, row in df.iterrows():
                    title = str(row.get("title", "")).strip()
                    if title:
                        industry_meta_map[title] = {
                            "org_name": row.get("orgSName", ""),
                            "rating": row.get("emRatingName", ""),
                            "publish_date": str(row.get("publishDate", ""))[:10],
                            "industry": row.get("industryName", ""),
                        }
            except Exception as e:
                logger.warning(f"加载行业元数据失败: {e}")

        all_chunks: List[Dict] = []

        # 处理个股研报
        for pdf_path in sorted(stock_dir.glob("*.pdf")):
            text = self._extract_text_from_pdf(pdf_path)
            if not text:
                continue

            # 用文件名匹配Excel元数据
            filename_stem = pdf_path.stem
            meta = {}
            for title, m in stock_meta_map.items():
                if title[:8] in filename_stem or filename_stem[:8] in title:
                    meta = m
                    break

            chunks = self._chunk_text(text)
            for i, chunk in enumerate(chunks):
                all_chunks.append(
                    {
                        "text": chunk,
                        "paper_path": str(pdf_path),
                        "report_type": "stock",
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "stock_name": meta.get("stock_name", ""),
                        "stock_code": meta.get("stock_code", ""),
                        "org_name": meta.get("org_name", ""),
                        "rating": meta.get("rating", ""),
                        "publish_date": meta.get("publish_date", ""),
                        "industry": meta.get("industry", ""),
                    }
                )

            logger.info(f"已处理个股研报: {pdf_path.name} → {len(chunks)}块")

        # 处理行业研报
        for pdf_path in sorted(industry_dir.glob("*.pdf")):
            text = self._extract_text_from_pdf(pdf_path)
            if not text:
                continue

            filename_stem = pdf_path.stem
            meta = {}
            for title, m in industry_meta_map.items():
                if title[:8] in filename_stem or filename_stem[:8] in title:
                    meta = m
                    break

            chunks = self._chunk_text(text)
            for i, chunk in enumerate(chunks):
                all_chunks.append(
                    {
                        "text": chunk,
                        "paper_path": str(pdf_path),
                        "report_type": "industry",
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "org_name": meta.get("org_name", ""),
                        "rating": meta.get("rating", ""),
                        "publish_date": meta.get("publish_date", ""),
                        "industry": meta.get("industry", ""),
                    }
                )

            logger.info(f"已处理行业研报: {pdf_path.name} → {len(chunks)}块")

        logger.info(f"共生成 {len(all_chunks)} 个文本块，开始构建向量索引...")
        self.build_index(all_chunks)
        self.save_index()
        logger.info("研报向量索引构建完成")

    # ------------------------------------------------------------------ #
    #  自动同步：检测PDF变化，有变化则重建索引                              #
    # ------------------------------------------------------------------ #

    def _manifest_path(self) -> Path:
        return self.persist_root / "report_manifest.json"

    def _load_manifest(self) -> Dict[str, float]:
        p = self._manifest_path()
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_manifest(self, files: Dict[str, float]):
        with open(self._manifest_path(), "w", encoding="utf-8") as f:
            json.dump(files, f, ensure_ascii=False, indent=2)

    def _scan_pdfs(self, *dirs: Path) -> Dict[str, float]:
        """返回 {pdf绝对路径: mtime}"""
        files: Dict[str, float] = {}
        for d in dirs:
            if d.exists():
                for pdf in sorted(d.glob("*.pdf")):
                    files[str(pdf.resolve())] = pdf.stat().st_mtime
        return files

    def sync_if_changed(
        self,
        stock_report_dir: "str | Path",
        industry_report_dir: "str | Path",
        stock_meta_xlsx: "Optional[str | Path]" = None,
        industry_meta_xlsx: "Optional[str | Path]" = None,
    ):
        """
        服务启动时调用。
        扫描两个目录下的PDF，与上次构建时的 manifest 对比：
        - 有新增 / 修改 / 删除  →  重建整个索引并更新 manifest
        - 无变化且索引已存在    →  直接复用已加载的索引，什么都不做
        """
        stock_dir = Path(stock_report_dir)
        industry_dir = Path(industry_report_dir)

        current = self._scan_pdfs(stock_dir, industry_dir)
        manifest = self._load_manifest()

        if current == manifest and self.index is not None:
            logger.info(f"研报文件无变化（共{len(current)}篇），跳过索引重建")
            return

        added = set(current) - set(manifest)
        removed = set(manifest) - set(current)
        modified = {
            p for p in current
            if p in manifest and current[p] != manifest[p]
        }

        if not added and not removed and not modified and self.index is not None:
            logger.info("研报文件无变化，跳过索引重建")
            return

        logger.info(
            f"检测到研报变化 → 新增={len(added)} 删除={len(removed)} 修改={len(modified)}，开始重建索引..."
        )

        self.build_from_folders(
            stock_report_dir=stock_dir,
            industry_report_dir=industry_dir,
            stock_meta_xlsx=stock_meta_xlsx,
            industry_meta_xlsx=industry_meta_xlsx,
        )
        self._save_manifest(current)
        logger.info("研报索引已更新，manifest 已保存")

    def search_reports(
        self,
        query: str,
        top_k: int = 5,
        report_type: Optional[str] = None,
        stock_name: Optional[str] = None,
    ) -> List[Dict]:
        """
        检索相关研报片段
        report_type: "stock" | "industry" | None（不限）
        stock_name:  过滤特定公司
        返回格式符合赛题references字段要求
        """
        results = self.search(query, top_k=top_k * 3)  # 多取一些再过滤

        # 过滤
        filtered = []
        for r in results:
            if report_type and r.get("report_type") != report_type:
                continue
            if (
                stock_name
                and stock_name not in r.get("stock_name", "")
                and stock_name not in r.get("text", "")
            ):
                continue
            filtered.append(r)

        # 去重：同一篇PDF只保留最相关的块
        seen_papers = {}
        deduped = []
        for r in filtered:
            paper = r["paper_path"]
            if paper not in seen_papers:
                seen_papers[paper] = r
                deduped.append(r)
            if len(deduped) >= top_k:
                break

        # 转换为赛题references格式
        references = []
        for r in deduped:
            references.append(
                {
                    "paper_path": r["paper_path"],
                    "text": r["text"][:300],  # 摘要截取300字
                    "paper_image": "",  # 图表路径（如有需要可扩展）
                    "stock_name": r.get("stock_name", ""),
                    "org_name": r.get("org_name", ""),
                    "publish_date": r.get("publish_date", ""),
                    "score": r.get("score", 0),
                }
            )

        return references

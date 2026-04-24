# core/rag/provenance_store.py

import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_NON_METRIC = {"serial_number", "stock_code", "stock_abbr", "report_period", "report_year"}

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_DEFAULT_PDF_DIRS = [
    _PROJECT_ROOT / "示例数据" / "附件2：财务报告" / "reports-上交所",
    _PROJECT_ROOT / "示例数据" / "附件2：财务报告" / "reports-深交所",
    Path.home() / "正式数据" / "附件2：财务报告" / "reports-上交所",
    Path.home() / "正式数据" / "附件2：财务报告" / "reports-深交所",
]


def _period_to_time_role(report_period: str) -> str:
    """Convert MySQL report_period to extracted-JSON time_role format."""
    if not report_period:
        return ""
    if report_period.endswith("FY"):
        return report_period[:-2]   # "2023FY" → "2023"
    return report_period             # "2023Q1" etc., already match


def extract_metric_cols(row: dict) -> list[str]:
    return [k for k in row if k not in _NON_METRIC]


def _extract_sql_context(sql: str) -> tuple[str, str]:
    """从 SQL WHERE 子句里提取 stock_abbr 和 report_period 作为兜底上下文。"""
    abbr_m = re.search(r"stock_abbr\s*(?:=|LIKE)\s*'([^'%]+)'", sql, re.I)
    period_m = re.search(r"report_period\s*=\s*'([^']+)'", sql, re.I)
    abbr = abbr_m.group(1).strip() if abbr_m else ""
    period = period_m.group(1).strip() if period_m else ""
    return abbr, period


class ProvenanceStore:
    """
    Loads extracted_json/*.json files and builds an in-memory index so that
    any SQL result row can be traced back to the original annual-report text.

    Index key: (stock_code_from_filename, time_role, metric_std)
    
    支持完整溯源链：
    SQL结果 → extracted_json (doc_id, source_text) → 原始PDF文件
    """

    def __init__(
        self, 
        extracted_json_dir: str | Path,
        pdf_dirs: Optional[list[str | Path]] = None,
    ) -> None:
        self._dir = Path(extracted_json_dir)
        self._index: dict[tuple, list[dict]] = {}
        self._abbr_to_code: dict[str, str] = {}
        self._doc_to_pdf: dict[str, Path] = {}
        self._pdf_dirs: list[Path] = []
        
        if pdf_dirs:
            self._pdf_dirs = [Path(p) for p in pdf_dirs if Path(p).exists()]
        else:
            self._pdf_dirs = [p for p in _DEFAULT_PDF_DIRS if p.exists()]
        
        self._load()
        self._build_pdf_index()

    def _load(self) -> None:
        if not self._dir.exists():
            logger.warning(f"[ProvenanceStore] 目录不存在: {self._dir}")
            return

        fact_count = 0
        for json_file in self._dir.glob("*.json"):
            stock_code = json_file.stem.split("_")[0]
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"[ProvenanceStore] 读取失败 {json_file.name}: {e}")
                continue

            stock_abbr = data.get("stock_abbr") or ""
            if stock_abbr and stock_code:
                self._abbr_to_code[stock_abbr] = stock_code

            doc_id = data.get("doc_id") or json_file.stem

            for fact in data.get("facts") or []:
                metric_std = fact.get("metric_std")
                time_role = str(fact.get("time_role") or "")
                if not metric_std or not time_role:
                    continue
                key = (stock_code, time_role, metric_std)
                self._index.setdefault(key, []).append({
                    "doc_id": doc_id,
                    "source_chunk": fact.get("source_chunk", ""),
                    "source_text": fact.get("source_text", ""),
                    "table_title": fact.get("table_title", ""),
                    "metric_alias": fact.get("metric_alias", ""),
                    "value_raw": fact.get("value_raw", ""),
                    "stock_abbr": stock_abbr,
                    "stock_code": stock_code,
                })
                fact_count += 1

        logger.info(
            f"[ProvenanceStore] 加载完成，{fact_count} 条事实，"
            f"{len(self._index)} 个索引键，{len(self._abbr_to_code)} 家公司"
        )

    def _build_pdf_index(self) -> None:
        """
        扫描 PDF 目录，建立 doc_id → PDF 路径的映射。
        
        doc_id 格式：600085_20230429_VQ9H
        PDF 文件名格式：
          - 600085_20230429_VQ9H.pdf (标准格式)
          - 同仁堂：2023年一季度报告.pdf (中文格式)
        """
        if not self._pdf_dirs:
            logger.warning("[ProvenanceStore] 未配置 PDF 目录，跳过 PDF 索引构建")
            return
        
        pdf_count = 0
        for pdf_dir in self._pdf_dirs:
            if not pdf_dir.exists():
                continue
            
            for pdf_path in pdf_dir.rglob("*.pdf"):
                stem = pdf_path.stem
                
                self._doc_to_pdf[stem] = pdf_path
                pdf_count += 1
                
                code_match = re.match(r"^(\d{6})_", stem)
                if code_match:
                    stock_code = code_match.group(1)
                    if stock_code not in self._doc_to_pdf:
                        self._doc_to_pdf[stock_code] = pdf_path
        
        logger.info(
            f"[ProvenanceStore] PDF 索引构建完成，"
            f"扫描 {len(self._pdf_dirs)} 个目录，找到 {pdf_count} 个 PDF 文件"
        )

    def get_pdf_path(self, doc_id: str) -> Optional[Path]:
        """
        根据 doc_id 获取对应的 PDF 文件路径。
        
        Args:
            doc_id: 文档ID，如 "600085_20230429_VQ9H"
            
        Returns:
            PDF 文件路径，未找到返回 None
        """
        return self._doc_to_pdf.get(doc_id)

    def lookup(
        self,
        stock_abbr: str,
        report_period: str,
        metric_cols: list[str],
        max_results: int = 3,
    ) -> list[dict]:
        """
        Return provenance entries for a SQL result row.

        stock_abbr:    e.g. "同仁堂"
        report_period: MySQL format, e.g. "2023FY" or "2023Q1"
        metric_cols:   non-meta column names from the SQL result row
        
        Returns:
            包含溯源信息的字典列表，每个字典包含：
            - doc_id: 文档ID
            - source_chunk: 来源chunk
            - source_text: 原文文本
            - pdf_path: 原始PDF文件路径（如果找到）
            - 其他元数据...
        """
        stock_code = self._abbr_to_code.get(stock_abbr, "")
        if not stock_code:
            return []
        time_role = _period_to_time_role(report_period)
        if not time_role:
            return []

        seen: set[str] = set()
        results: list[dict] = []
        for metric in metric_cols:
            for entry in self._index.get((stock_code, time_role, metric), []):
                dedup_key = (entry.get("source_text", "") or "")[:80]
                if dedup_key and dedup_key not in seen:
                    seen.add(dedup_key)
                    
                    doc_id = entry.get("doc_id", "")
                    pdf_path = self.get_pdf_path(doc_id)
                    
                    result = entry.copy()
                    if pdf_path:
                        result["pdf_path"] = str(pdf_path)
                    
                    results.append(result)
                if len(results) >= max_results:
                    return results
        return results

    def lookup_rows(
        self,
        sql_result: list[dict],
        max_per_query: int = 3,
        sql: str = "",
    ) -> list[dict]:
        """
        Collect provenance for up to the first few distinct (stock_abbr, period) pairs
        in a SQL result list.
        
        完整溯源链：
        SQL结果 → extracted_json (doc_id, source_text) → 原始PDF文件
        
        Returns:
            溯源信息列表，每个元素包含：
            - doc_id: 文档ID
            - source_chunk: 来源chunk
            - source_text: 原文文本
            - pdf_path: 原始PDF文件路径（如果找到）
            - 其他元数据...
        """
        if not sql_result:
            return []

        # SQL WHERE 子句里提取的兜底上下文（当结果行不含 stock_abbr/report_period 时使用）
        sql_abbr, sql_period = _extract_sql_context(sql) if sql else ("", "")

        seen_pairs: set[tuple] = set()
        all_provenance: list[dict] = []

        for row in sql_result:
            stock_abbr = str(row.get("stock_abbr") or "") or sql_abbr
            report_period = str(row.get("report_period") or "") or sql_period
            if not stock_abbr or not report_period:
                continue
            pair = (stock_abbr, report_period)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            metrics = extract_metric_cols(row)
            entries = self.lookup(stock_abbr, report_period, metrics, max_results=max_per_query)
            all_provenance.extend(entries)

            if len(seen_pairs) >= 2:
                break

        return all_provenance[:max_per_query]

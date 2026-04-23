# core/rag/provenance_store.py

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_NON_METRIC = {"serial_number", "stock_code", "stock_abbr", "report_period", "report_year"}


def _period_to_time_role(report_period: str) -> str:
    """Convert MySQL report_period to extracted-JSON time_role format."""
    if not report_period:
        return ""
    if report_period.endswith("FY"):
        return report_period[:-2]   # "2023FY" → "2023"
    return report_period             # "2023Q1" etc., already match


def extract_metric_cols(row: dict) -> list[str]:
    return [k for k in row if k not in _NON_METRIC]


class ProvenanceStore:
    """
    Loads extracted_json/*.json files and builds an in-memory index so that
    any SQL result row can be traced back to the original annual-report text.

    Index key: (stock_code_from_filename, time_role, metric_std)
    """

    def __init__(self, extracted_json_dir: str | Path) -> None:
        self._dir = Path(extracted_json_dir)
        self._index: dict[tuple, list[dict]] = {}
        self._abbr_to_code: dict[str, str] = {}
        self._load()

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
                    results.append(entry)
                if len(results) >= max_results:
                    return results
        return results

    def lookup_rows(
        self,
        sql_result: list[dict],
        max_per_query: int = 3,
    ) -> list[dict]:
        """
        Collect provenance for up to the first few distinct (stock_abbr, period) pairs
        in a SQL result list.
        """
        if not sql_result:
            return []

        seen_pairs: set[tuple] = set()
        all_provenance: list[dict] = []

        for row in sql_result:
            stock_abbr = str(row.get("stock_abbr") or "")
            report_period = str(row.get("report_period") or "")
            if not stock_abbr or not report_period:
                continue
            pair = (stock_abbr, report_period)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            metrics = extract_metric_cols(row)
            entries = self.lookup(stock_abbr, report_period, metrics, max_results=max_per_query)
            all_provenance.extend(entries)

            if len(seen_pairs) >= 2:   # limit to first 2 distinct rows to keep it concise
                break

        return all_provenance[:max_per_query]

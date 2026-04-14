"""
离线脚本：将研报PDF向量化并构建FAISS索引
运行一次即可，之后 Agent 直接加载已存在的索引。

用法：
    cd /home/qwq/TiPDMCUP
    python scripts/build_report_index.py
"""

from pathlib import Path

from core.rag.report_retriever import ReportRetrieval

DATA_ROOT = Path.home() / "正式数据" / "附件5：研报数据"

STOCK_DIR = DATA_ROOT / "个股研报"
INDUSTRY_DIR = DATA_ROOT / "行业研报"
STOCK_META = DATA_ROOT / "个股_研报信息.xlsx"
INDUSTRY_META = DATA_ROOT / "行业_研报信息.xlsx"

PERSIST_ROOT = Path(__file__).resolve().parent.parent / "data" / "faiss_report_store"


def main():
    print(f"索引将保存到: {PERSIST_ROOT}")
    retriever = ReportRetrieval(persist_root=str(PERSIST_ROOT))
    retriever.build_from_folders(
        stock_report_dir=STOCK_DIR,
        industry_report_dir=INDUSTRY_DIR,
        stock_meta_xlsx=STOCK_META if STOCK_META.exists() else None,
        industry_meta_xlsx=INDUSTRY_META if INDUSTRY_META.exists() else None,
    )
    print("索引构建完成！")


if __name__ == "__main__":
    main()

"""
研报RAG调试脚本
逐步测试：PDF读取 → 分块 → 向量化 → 检索
"""

import sys
from pathlib import Path

# ========== 路径配置（按你的实际路径修改） ==========
STOCK_REPORT_DIR = "/home/qwq/正式数据/附件5：研报数据/个股研报"
INDUSTRY_REPORT_DIR = "/home/qwq/正式数据/附件5：研报数据/行业研报"
STOCK_META_XLSX = "/home/qwq/正式数据/附件5：研报数据/个股_研报信息.xlsx"
INDUSTRY_META_XLSX = "/home/qwq/正式数据/附件5：研报数据/行业_研报信息.xlsx"
PERSIST_ROOT = "./faiss_report_store"
BGE_MODEL_PATH = "BAAI/bge-m3"  # 或本地路径如 "/models/bge-m3"
# ====================================================


def step1_check_env():
    """步骤1：检查依赖"""
    print("=" * 50)
    print("步骤1：检查依赖")
    print("=" * 50)
    try:
        import fitz

        print(f"✅ pymupdf: {fitz.__version__}")
    except ImportError:
        print("❌ pymupdf 未安装，运行：pip install pymupdf")
        sys.exit(1)

    try:
        import faiss

        print(f"✅ faiss: 已安装")
    except ImportError:
        print("❌ faiss 未安装，运行：pip install faiss-gpu 或 faiss-cpu")
        sys.exit(1)

    try:
        from langchain_huggingface import HuggingFaceEmbeddings

        print(f"✅ langchain_huggingface: 已安装")
    except ImportError:
        print(
            "❌ langchain_huggingface 未安装，运行：pip install langchain-huggingface"
        )
        sys.exit(1)

    try:
        import pandas as pd

        print(f"✅ pandas: {pd.__version__}")
    except ImportError:
        print("❌ pandas 未安装")
        sys.exit(1)

    print()


def step2_check_files():
    """步骤2：检查文件路径"""
    print("=" * 50)
    print("步骤2：检查文件路径")
    print("=" * 50)

    paths = {
        "个股研报目录": STOCK_REPORT_DIR,
        "行业研报目录": INDUSTRY_REPORT_DIR,
        "个股元数据xlsx": STOCK_META_XLSX,
        "行业元数据xlsx": INDUSTRY_META_XLSX,
    }

    for name, p in paths.items():
        path = Path(p)
        if path.exists():
            if path.is_dir():
                pdfs = list(path.glob("*.pdf"))
                print(f"✅ {name}: {path} （{len(pdfs)} 个PDF）")
            else:
                print(f"✅ {name}: {path}")
        else:
            print(f"❌ {name}: {path} 不存在，请修改路径配置")

    print()


def step3_test_pdf_read():
    """步骤3：测试读取一个PDF"""
    print("=" * 50)
    print("步骤3：测试读取PDF")
    print("=" * 50)

    import fitz

    stock_dir = Path(STOCK_REPORT_DIR)
    pdf_files = list(stock_dir.glob("*.pdf"))

    if not pdf_files:
        print("❌ 没有找到PDF文件")
        return

    pdf_path = pdf_files[0]
    print(f"测试文件: {pdf_path.name}")

    doc = fitz.open(str(pdf_path))
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()

    print(f"✅ 读取成功，总字符数: {len(text)}")
    print(f"前200字内容预览：\n{text[:200]}")
    print()

    return text


def step4_test_chunk(text: str):
    """步骤4：测试文本分块"""
    print("=" * 50)
    print("步骤4：测试文本分块")
    print("=" * 50)

    chunk_size = 500
    chunk_overlap = 50
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if len(chunk) > 50:
            chunks.append(chunk)
        start += chunk_size - chunk_overlap

    print(f"✅ 分块完成，共 {len(chunks)} 块")
    print(f"第1块预览：\n{chunks[0][:200]}")
    print()

    return chunks


def step5_test_embedding(chunks: list):
    """步骤5：测试向量化（只测前3块）"""
    print("=" * 50)
    print("步骤5：测试向量化（前3块）")
    print("=" * 50)

    import numpy as np
    from langchain_huggingface import HuggingFaceEmbeddings

    print(f"加载embedding模型: {BGE_MODEL_PATH}")
    print("（首次加载较慢，请耐心等待...）")

    try:
        embedding = HuggingFaceEmbeddings(
            model_name=BGE_MODEL_PATH,
            model_kwargs={"device": "cuda"},
        )
        test_chunks = chunks[:3]
        vecs = embedding.embed_documents(test_chunks)
        vecs = np.array(vecs)
        print(f"✅ 向量化成功，shape: {vecs.shape}")
        print()
        return embedding
    except Exception as e:
        print(f"❌ 向量化失败: {e}")
        print("如果是CUDA错误，尝试改为 device: cpu")
        return None


def step6_build_index():
    """步骤6：构建完整索引（只用前5个PDF测试）"""
    print("=" * 50)
    print("步骤6：构建索引（前5个PDF）")
    print("=" * 50)

    import json

    import faiss
    import fitz
    import numpy as np
    from langchain_huggingface import HuggingFaceEmbeddings

    stock_dir = Path(STOCK_REPORT_DIR)
    pdf_files = list(stock_dir.glob("*.pdf"))[:5]  # 先只测5个

    embedding = HuggingFaceEmbeddings(
        model_name=BGE_MODEL_PATH,
        model_kwargs={"device": "cuda"},
    )

    all_chunks = []
    for pdf_path in pdf_files:
        try:
            doc = fitz.open(str(pdf_path))
            text = "".join(page.get_text() for page in doc)
            doc.close()

            start = 0
            while start < len(text):
                chunk = text[start : start + 500].strip()
                if len(chunk) > 50:
                    all_chunks.append(
                        {
                            "text": chunk,
                            "paper_path": str(pdf_path),
                            "report_type": "stock",
                        }
                    )
                start += 450

            print(f"  ✅ {pdf_path.name}")
        except Exception as e:
            print(f"  ❌ {pdf_path.name}: {e}")

    print(f"\n共 {len(all_chunks)} 个文本块，开始向量化...")

    texts = [c["text"] for c in all_chunks]
    vecs = embedding.embed_documents(texts)
    vecs = np.array(vecs, dtype=np.float32)
    vecs = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)

    index = faiss.IndexFlatL2(vecs.shape[1])
    index.add(vecs)

    persist = Path(PERSIST_ROOT)
    persist.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(persist / "report_index_test.faiss"))
    with open(persist / "report_meta_test.json", "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"✅ 索引构建完成，保存至 {PERSIST_ROOT}")
    print()

    return index, all_chunks, embedding


def step7_test_search(index, meta, embedding):
    """步骤7：测试检索"""
    print("=" * 50)
    print("步骤7：测试检索")
    print("=" * 50)

    import numpy as np

    test_queries = [
        "华润三九主营业务收入",
        "中药行业毛利率",
        "净利润同比增长",
    ]

    for query in test_queries:
        print(f"\n查询: {query}")
        vec = embedding.embed_documents([query])
        vec = np.array(vec, dtype=np.float32)
        vec = vec / np.linalg.norm(vec, axis=1, keepdims=True)

        distances, indices = index.search(vec, 3)
        for rank, idx in enumerate(indices[0]):
            if idx < len(meta):
                item = meta[idx]
                print(f"  [{rank + 1}] score={distances[0][rank]:.4f}")
                print(f"       来源: {Path(item['paper_path']).name}")
                print(f"       内容: {item['text'][:100]}...")


if __name__ == "__main__":
    step1_check_env()
    step2_check_files()
    text = step3_test_pdf_read()

    if text:
        chunks = step4_test_chunk(text)
        emb = step5_test_embedding(chunks)

        if emb:
            # 确认没问题后构建完整索引
            confirm = input("\n前5步都OK？构建完整测试索引？(y/n): ")
            if confirm.lower() == "y":
                index, meta, emb = step6_build_index()
                step7_test_search(index, meta, emb)
                print("\n✅ 全部调试通过！可以跑完整版了。")

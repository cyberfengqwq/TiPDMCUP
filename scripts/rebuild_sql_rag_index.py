#!/usr/bin/env python3
"""
Rebuild SQL RAG index for a specific user.

Example:
  python scripts/rebuild_sql_rag_index.py --user-id batch_export --device cuda --force
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _remove_existing(user_dir: Path) -> None:
    for name in ("user_index.faiss", "user_meta.json"):
        target = user_dir / name
        if target.exists():
            target.unlink()


def rebuild_index(user_id: str, device: str, force: bool) -> None:
    if device:
        os.environ["EMBEDDING_DEVICE"] = device
    if force:
        os.environ["FORCE_REBUILD_RAG_INDEX"] = "1"

    user_root = ROOT / "data" / "users"
    user_root.mkdir(parents=True, exist_ok=True)
    user_dir = user_root / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    if force:
        _remove_existing(user_dir)

    from config.db_schema import SQL_EXAMPLES
    from core.rag.sql_retriever import UserRetrieval

    print(f"User ID: {user_id}")
    print(f"Embedding device: {device or 'cpu'}")
    print(f"SQL_EXAMPLES: {len(SQL_EXAMPLES)}")

    retriever = UserRetrieval(user=user_id, persist_root=str(user_root))
    if retriever.index is None or not retriever.meta:
        print("WARN: 索引为空，未加载到任何示例或历史问题。")
    else:
        print(f"Loaded items: {len(retriever.meta)}")

    retriever.save_index()

    print("Index saved:")
    print(f"  {retriever.index_path}")
    print(f"  {retriever.meta_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild SQL RAG index for a user.")
    parser.add_argument("--user-id", required=True, help="目标用户 ID")
    parser.add_argument(
        "--device",
        default="cpu",
        help="Embedding 设备（cpu 或 cuda）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重建（清理旧索引）",
    )

    args = parser.parse_args()
    rebuild_index(user_id=args.user_id, device=args.device, force=args.force)


if __name__ == "__main__":
    main()

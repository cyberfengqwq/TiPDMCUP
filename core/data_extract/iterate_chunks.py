import argparse
import json
from pathlib import Path
from typing import Any


def find_chunk_dirs(root_dir: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in root_dir.iterdir()
            if path.is_dir() and any(path.glob("chunk_*.json"))
        ]
    )


def load_chunk(chunk_file: Path) -> list[dict[str, Any]]:
    with chunk_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"chunk 文件不是 block 数组: {chunk_file}")
    return [item for item in data if isinstance(item, dict)]


def summarize_chunk(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    page_markers = [block.get("page") for block in blocks if block.get("type") == "page"]
    return {
        "block_count": len(blocks),
        "page_count": len(page_markers),
        "pages": page_markers,
    }


def iter_chunk_tasks(root_dir: Path) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for chunk_dir in find_chunk_dirs(root_dir):
        chunk_files = sorted(chunk_dir.glob("chunk_*.json"))
        for chunk_file in chunk_files:
            blocks = load_chunk(chunk_file)
            summary = summarize_chunk(blocks)
            tasks.append(
                {
                    "doc_id": chunk_dir.name,
                    "chunk_id": chunk_file.stem,
                    "chunk_file": str(chunk_file.resolve()),
                    "summary": summary,
                }
            )
    return tasks


def write_manifest(tasks: list[dict[str, Any]], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


def print_preview(tasks: list[dict[str, Any]], limit: int) -> None:
    for task in tasks[:limit]:
        print(
            f"{task['doc_id']} | {task['chunk_id']} | "
            f"pages={task['summary']['pages']} | blocks={task['summary']['block_count']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Traverse a root directory containing many chunk folders and build a chunk task manifest."
    )
    parser.add_argument("root_dir", help="包含多个 chunk 文件夹的大目录")
    parser.add_argument(
        "--output",
        default="chunk_task_manifest.json",
        help="输出任务清单 JSON 文件路径",
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=20,
        help="终端预览前多少条任务",
    )
    args = parser.parse_args()

    root_dir = Path(args.root_dir).resolve()
    if not root_dir.exists():
        raise FileNotFoundError(f"目录不存在: {root_dir}")
    if not root_dir.is_dir():
        raise NotADirectoryError(f"必须提供目录: {root_dir}")

    tasks = iter_chunk_tasks(root_dir)
    if not tasks:
        raise FileNotFoundError(f"未找到任何 chunk 文件夹或 chunk 文件: {root_dir}")

    output_file = Path(args.output).resolve()
    write_manifest(tasks, output_file)

    print(f"共生成 {len(tasks)} 条 chunk 任务")
    print(f"任务清单已写入: {output_file}")
    print_preview(tasks, args.preview)


if __name__ == "__main__":
    main()

import argparse
from pathlib import Path

from Reorgnize import chunk_to_markdown, load_chunk


def find_doc_dirs(root_dir: Path) -> list[Path]:
    return sorted(
        [
            path
            for path in root_dir.iterdir()
            if path.is_dir() and any(path.glob("chunk_*.json"))
        ]
    )


def convert_doc_dir(doc_dir: Path, output_root: Path) -> None:
    output_dir = output_root / doc_dir.name
    output_dir.mkdir(parents=True, exist_ok=True)

    chunk_files = sorted(doc_dir.glob("chunk_*.json"))
    for chunk_file in chunk_files:
        blocks = load_chunk(chunk_file)
        markdown = chunk_to_markdown(blocks)
        output_file = output_dir / f"{chunk_file.stem}.md"
        with output_file.open("w", encoding="utf-8") as f:
            f.write(markdown)
        print(f"已生成: {output_file}")


def convert_waiting_chunk(waiting_chunk_root: Path, output_root: Path) -> None:
    if not waiting_chunk_root.exists():
        raise FileNotFoundError(f"目录不存在: {waiting_chunk_root}")
    if not waiting_chunk_root.is_dir():
        raise NotADirectoryError(f"必须提供目录: {waiting_chunk_root}")

    doc_dirs = find_doc_dirs(waiting_chunk_root)
    if not doc_dirs:
        raise FileNotFoundError(f"未找到任何 chunk 文件夹: {waiting_chunk_root}")

    output_root.mkdir(parents=True, exist_ok=True)
    for doc_dir in doc_dirs:
        convert_doc_dir(doc_dir, output_root)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert waiting_chunk folders into per-chunk markdown files for first-pass screening."
    )
    parser.add_argument(
        "waiting_chunk_root",
        nargs="?",
        default="waiting_chunk",
        help="包含多个 chunk 文件夹的大目录",
    )
    parser.add_argument(
        "--output-dir",
        default="waiting_markdown",
        help="输出 markdown 的大目录",
    )
    args = parser.parse_args()

    convert_waiting_chunk(
        waiting_chunk_root=Path(args.waiting_chunk_root).resolve(),
        output_root=Path(args.output_dir).resolve(),
    )


if __name__ == "__main__":
    main()

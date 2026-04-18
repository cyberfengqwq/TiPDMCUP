import argparse
import json
import re
from html import unescape
from pathlib import Path
from typing import Any


KEEP_TYPES = {"title", "paragraph", "table"}
TAG_RE = re.compile(r"<[^>]+>")


def extract_text_spans(spans: list[Any]) -> str:
    parts: list[str] = []
    for span in spans or []:
        if isinstance(span, dict):
            text = span.get("content")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def html_to_text(html: str) -> str:
    plain = TAG_RE.sub("", html or "")
    return unescape(plain)


def normalize_block_type(block_type: Any) -> str:
    if not isinstance(block_type, str):
        return ""
    return block_type.strip().lower()


def simplify_block(block: dict[str, Any]) -> dict[str, Any] | None:
    block_type = normalize_block_type(block.get("type"))
    content = block.get("content", {})

    if block_type not in KEEP_TYPES or not isinstance(content, dict):
        return None

    simplified: dict[str, Any] = {"type": block_type}

    if block_type == "title":
        simplified["level"] = content.get("level")
        simplified["text"] = extract_text_spans(content.get("title_content", []))
    elif block_type == "paragraph":
        simplified["text"] = extract_text_spans(content.get("paragraph_content", []))
    elif block_type == "table":
        simplified["caption"] = extract_text_spans(content.get("table_caption", []))
        simplified["html"] = content.get("html", "")
        footnote = extract_text_spans(content.get("table_footnote", []))
        if footnote:
            simplified["footnote"] = footnote
    else:
        return None

    return simplified


def load_blocks(input_path: Path) -> list[dict[str, Any]]:
    with input_path.open("r", encoding="utf-8") as f:
        pages = json.load(f)

    kept_blocks: list[dict[str, Any]] = []
    for page_index, page in enumerate(pages, start=1):
        if not isinstance(page, list):
            continue
        for block in page:
            if not isinstance(block, dict):
                continue
            simplified = simplify_block(block)
            if simplified:
                simplified["_page"] = page_index
                kept_blocks.append(simplified)
    return kept_blocks


def block_char_count(block: dict[str, Any]) -> int:
    if block["type"] in {"title", "paragraph"}:
        return len(block.get("text", ""))
    if block["type"] == "table":
        return len(block.get("caption", "")) + len(html_to_text(block.get("html", ""))) + len(block.get("footnote", ""))
    return 0


def public_block(block: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in block.items() if key != "_page"}


def inject_page_markers(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    current_page: int | None = None

    for block in blocks:
        page = block.get("_page")
        if page != current_page:
            current_page = page
            output.append({"type": "page", "page": current_page})
        output.append(public_block(block))

    return output


def finalize_chunk(
    output_dir: Path,
    chunk_index: int,
    blocks: list[dict[str, Any]],
) -> None:
    if not blocks:
        return

    output_path = output_dir / f"chunk_{chunk_index}.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(inject_page_markers(blocks), f, ensure_ascii=False, indent=2)


def chunk_blocks(
    blocks: list[dict[str, Any]],
    output_dir: Path,
    char_limit: int,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    chunk_index = 1
    current_blocks: list[dict[str, Any]] = []
    current_chars = 0
    previous_tail: list[dict[str, Any]] = []

    for block in blocks:
        if not current_blocks:
            current_blocks.extend(json.loads(json.dumps(previous_tail, ensure_ascii=False)))
            current_chars = sum(block_char_count(item) for item in current_blocks)

        current_blocks.append(json.loads(json.dumps(block, ensure_ascii=False)))
        current_chars += block_char_count(block)

        if current_chars >= char_limit:
            finalize_chunk(
                output_dir=output_dir,
                chunk_index=chunk_index,
                blocks=current_blocks,
            )
            previous_tail = json.loads(json.dumps(current_blocks[-2:], ensure_ascii=False))
            current_blocks = []
            current_chars = 0
            chunk_index += 1

    if current_blocks:
        finalize_chunk(
            output_dir=output_dir,
            chunk_index=chunk_index,
            blocks=current_blocks,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Split annual report content blocks into chunk JSON files.")
    parser.add_argument(
        "input_json",
        nargs="?",
        help="Path to the source JSON file.",
    )
    parser.add_argument(
        "--char-limit",
        type=int,
        default=6000,
        help="Maximum character count per chunk before closing the window.",
    )
    parser.add_argument(
        "--output-dir",
        default="chunk_json",
        help="Directory used to store chunk_*.json files.",
    )
    args = parser.parse_args()

    if args.input_json:
        input_path = Path(args.input_json).resolve()
    else:
        candidates = sorted(Path.cwd().glob("*content_list_v2.json"))
        if not candidates:
            raise FileNotFoundError("No source JSON matching '*content_list_v2.json' was found in the current directory.")
        input_path = candidates[0].resolve()
    output_dir = Path(args.output_dir).resolve()

    blocks = load_blocks(input_path)
    chunk_blocks(
        blocks=blocks,
        output_dir=output_dir,
        char_limit=args.char_limit,
    )


if __name__ == "__main__":
    main()

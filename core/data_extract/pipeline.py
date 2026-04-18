import argparse
import json
import shutil
from pathlib import Path

from chunk_blocks import chunk_blocks, load_blocks
from iterate_chunks import iter_chunk_tasks, write_manifest
from mv_rm import process_root
from Reorgnize import rebuild_all
from screen_reorganize import convert_waiting_chunk


SUFFIX = "_content_list_v2"


def doc_folder_name(json_file: Path) -> str:
    stem = json_file.stem
    if "__" in stem:
        stem = stem.split("__", 1)[1]
    if stem.endswith(SUFFIX):
        return stem[: -len(SUFFIX)]
    return stem


def chunk_one_json(json_file: Path, waiting_chunk_root: Path, char_limit: int) -> Path:
    output_dir = waiting_chunk_root / doc_folder_name(json_file)
    output_dir.mkdir(parents=True, exist_ok=True)
    blocks = load_blocks(json_file)
    chunk_blocks(blocks=blocks, output_dir=output_dir, char_limit=char_limit)
    return output_dir


def chunk_all_jsons(json_root: Path, waiting_chunk_root: Path, char_limit: int) -> list[Path]:
    json_files = sorted(json_root.glob("*_content_list_v2.json"))
    if not json_files:
        raise FileNotFoundError(f"未找到任何 *_content_list_v2.json: {json_root}")

    waiting_chunk_root.mkdir(parents=True, exist_ok=True)
    created_dirs: list[Path] = []
    for json_file in json_files:
        chunk_dir = chunk_one_json(json_file, waiting_chunk_root, char_limit)
        created_dirs.append(chunk_dir)
        print(f"已分块 {json_file} -> {chunk_dir}")
    return created_dirs


def build_manifest(waiting_chunk_root: Path, manifest_file: Path) -> None:
    tasks = iter_chunk_tasks(waiting_chunk_root)
    if not tasks:
        raise FileNotFoundError(f"未找到任何 chunk 任务: {waiting_chunk_root}")
    write_manifest(tasks, manifest_file)
    print(f"已生成任务清单 {manifest_file}")
    print(f"任务数量: {len(tasks)}")


def build_screen_prompt(markdown_text: str, rule_text: str) -> str:
    return (
        "你是一个严格的文本初筛模型。\n"
        "你的任务是根据给定规则判断下面的文档片段是否应当保留进入下一轮。\n"
        "你只能输出 YES 或 NO，不要输出任何解释、标点、空格或其他内容。\n\n"
        f"筛选规则:\n{rule_text}\n\n"
        "待判断内容:\n"
        f"{markdown_text}"
    )


def build_extract_prompt(markdown_text: str, doc_id: str, schema_text: str) -> str:
    return (
        "你是一个财报结构化抽取助手。\n"
        "你的任务是从下面的财报 markdown 中抽取结构化原子数据，并且只输出 JSON。\n"
        "不要输出解释，不要输出 markdown 代码块，不要输出额外文字。\n"
        "如果没有把握，不要编造；没有抽到的数据可以省略 facts 项中的对应记录。\n"
        "如果该片段没有任何可抽取的财务数据，输出 {\"doc_id\": \"<doc_id>\", \"facts\": []}，不要输出任何解释。\n\n"
        "输出要求：\n"
        "1. 顶层必须是一个 JSON 对象。\n"
        "2. 顶层至少包含 doc_id、stock_code、stock_abbr、report_year、report_period、facts。\n"
        "3. facts 必须是数组，每个元素尽量包含 statement、scope、metric_std、metric_alias、value、value_raw、unit、time_role、table_title、source_chunk、source_text。\n"
        "   metric_std 必须使用 schema 映射表中的英文字段名（如 net_profit、asset_total_assets），metric_alias 填原文中文名。\n"
        "4. 如果无法确定 stock_code、stock_abbr、report_year、report_period，可以填 null。\n"
        "5. 只输出一个 JSON 对象。\n"
        "6. time_role 填写规则：\n"
        "   - 与季度有关（一季度、半年度、三季度等）：填 YYYYQX，如 2023Q1、2023Q2、2023Q3\n"
        "   - 与年度有关（全年、年末等）：填 YYYY，如 2023\n"
        "   - 如无法确定具体年份，填 null。\n\n"
        f"抽取 schema 参考：\n{schema_text}\n\n"
        f"文档标识：{doc_id}\n\n"
        "财报 markdown：\n"
        f"{markdown_text}"
    )


def normalize_screen_result(answer: str) -> str:
    text = answer.strip()
    # Qwen3 thinking mode: 剥掉 <think>...</think> 块，只看最终答案
    if "<think>" in text:
        end = text.rfind("</think>")
        if end != -1:
            text = text[end + len("</think>"):].strip()
    text = text.upper()
    if text == "YES":
        return "YES"
    if text == "NO":
        return "NO"
    if "YES" in text and "NO" not in text:
        return "YES"
    if "NO" in text and "YES" not in text:
        return "NO"
    return "INVALID"


def split_by_token_limit(
    markdown_text: str,
    doc_id: str,
    schema_text: str,
    tokenizer,
    max_input_len: int,
    separator: str = "\n---\n",
) -> list[str]:
    """Split markdown at separator boundaries so each part fits within max_input_len tokens."""
    sections = markdown_text.split(separator)
    if len(sections) <= 1:
        return [markdown_text]

    parts: list[str] = []
    current: list[str] = []

    for section in sections:
        candidate = separator.join(current + [section])
        prompt = build_extract_prompt(candidate, doc_id, schema_text)
        token_ids = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        if len(token_ids) <= max_input_len:
            current.append(section)
        else:
            if current:
                parts.append(separator.join(current))
                current = [section]
            else:
                # Single section already too large: include as-is, batch_chat will truncate
                parts.append(section)

    if current:
        parts.append(separator.join(current))

    return parts if parts else [markdown_text]


def parse_json_response(answer: str) -> dict | None:
    text = answer.strip()
    if not text:
        return None

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1:
        return None

    if end > start:
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            pass

    # 输出被截断：找最后一个完整的 fact 对象，补上 ]} 闭合
    last_close = text.rfind("}")
    if last_close > start:
        for suffix in ("]}}", "]}"):
            try:
                data = json.loads(text[start : last_close + 1] + suffix)
                if isinstance(data, dict):
                    data["_truncated"] = True
                    return data
            except json.JSONDecodeError:
                pass

    return None


def copy_yes_chunk(chunk_json_file: Path, new_chunk_root: Path, doc_id: str) -> Path:
    target_dir = new_chunk_root / doc_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / chunk_json_file.name
    shutil.copy2(chunk_json_file, target_file)
    return target_file


def write_json(data: object, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_screen(
    waiting_chunk_root: Path,
    waiting_markdown_root: Path,
    new_chunk_root: Path,
    results_file: Path,
    model_path: str,
    rule_text: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    gpu_memory_utilization: float,
    doc_filter: list[str] | None = None,
    screen_batch_size: int = 256,
) -> None:
    from vllm_service import LLM

    convert_waiting_chunk(waiting_chunk_root, waiting_markdown_root)

    # ── 断点续传：加载已有结果，跳过已筛 chunk ────────────────────────────────
    results: list[dict[str, str]] = []
    done: set[tuple[str, str]] = set()  # (doc_id, chunk_id)
    if results_file.exists():
        try:
            existing = json.loads(results_file.read_text(encoding="utf-8"))
            if isinstance(existing, list):
                results = existing
                done = {(r["doc_id"], r["chunk_id"]) for r in results}
                print(f"[断点续传] 已加载 {len(done)} 条历史结果，将跳过这些 chunk")
        except Exception as e:
            print(f"[断点续传] 读取历史结果失败，将从头开始: {e}")

    # ── 收集待处理任务（排除已完成）────────────────────────────────────────────
    tasks: list[tuple[str, Path, Path]] = []
    for doc_dir in sorted(p for p in waiting_markdown_root.iterdir() if p.is_dir()):
        doc_id = doc_dir.name
        if doc_filter and not any(doc_id == f or doc_id.startswith(f) for f in doc_filter):
            continue
        for chunk_md_file in sorted(doc_dir.glob("chunk_*.md")):
            if (doc_id, chunk_md_file.stem) in done:
                continue
            chunk_json_file = waiting_chunk_root / doc_id / f"{chunk_md_file.stem}.json"
            tasks.append((doc_id, chunk_md_file, chunk_json_file))

    if not tasks:
        print("所有 chunk 已筛选完毕，无需重新处理。")
        return

    total = len(tasks)
    print(f"共 {total} 个 chunk 待初筛（每批 {screen_batch_size}）...")

    llm = LLM(
        _modelpath=model_path,
        _temperature=temperature,
        _top_p=top_p,
        _max_tokens=min(max_tokens, 4),
        _gpu_memory_utilization=gpu_memory_utilization,
        _enable_thinking=False,
        _max_model_len=8192,
    )
    llm.load_model()

    try:
        for batch_start in range(0, total, screen_batch_size):
            batch = tasks[batch_start: batch_start + screen_batch_size]
            batch_num = batch_start // screen_batch_size + 1
            total_batches = (total + screen_batch_size - 1) // screen_batch_size
            print(f"--- batch {batch_num}/{total_batches}  ({len(batch)} chunks) ---")

            prompts = [
                build_screen_prompt(chunk_md_file.read_text(encoding="utf-8"), rule_text)
                for _, chunk_md_file, _ in batch
            ]
            raw_answers = llm.batch_chat(prompts)

            for (doc_id, chunk_md_file, chunk_json_file), raw_answer in zip(batch, raw_answers):
                screen_result = normalize_screen_result(raw_answer)
                copied_to = ""
                if screen_result == "YES":
                    copied_to = str(copy_yes_chunk(chunk_json_file, new_chunk_root, doc_id).resolve())
                results.append({
                    "doc_id": doc_id,
                    "chunk_id": chunk_md_file.stem,
                    "chunk_markdown_path": str(chunk_md_file.resolve()),
                    "chunk_json_path": str(chunk_json_file.resolve()),
                    "raw_answer": raw_answer.strip(),
                    "screen_result": screen_result,
                    "copied_to": copied_to,
                })
                print(f"[{screen_result}] {doc_id} / {chunk_md_file.stem}")

            # 每批结束后立即存档，断电/超时也不丢进度
            write_json(results, results_file)
            done_count = batch_start + len(batch)
            print(f"[checkpoint] 已保存 {done_count}/{total} 条结果 → {results_file}")
    finally:
        llm.unload_model()

    print(f"初筛完成，共 {len(results)} 条结果 → {results_file}")


def run_prepare(
    root_o: Path,
    extracted_json_root: Path,
    waiting_chunk_root: Path,
    manifest_file: Path,
    char_limit: int,
    dry_run: bool,
) -> None:
    process_root(root_o=root_o, root_x=extracted_json_root, dry_run=dry_run)
    if dry_run:
        print("当前为 dry-run，未执行后续分块和清单生成。")
        return
    chunk_all_jsons(extracted_json_root, waiting_chunk_root, char_limit)
    build_manifest(waiting_chunk_root, manifest_file)


def run_rebuild(new_chunk_root: Path, extracted_data_root: Path, separator: str) -> None:
    rebuild_all(new_chunk_root, extracted_data_root, separator=separator)


def run_extract(
    extracted_data_root: Path,
    extracted_json_root: Path,
    results_file: Path,
    model_path: str,
    schema_text: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    gpu_memory_utilization: float,
    max_model_len: int | None = 28000,
    extract_batch_size: int = 4,
    separator: str = "\n---\n",
    split_output_reserve: int | None = None,
    skip_existing: bool = True,
    tensor_parallel_size: int = 1,
) -> None:
    from vllm_service import LLM

    all_markdown_files = sorted(extracted_data_root.glob("*.md"))
    if not all_markdown_files:
        raise FileNotFoundError(f"未找到任何 markdown 文件: {extracted_data_root}")

    extracted_json_root.mkdir(parents=True, exist_ok=True)

    if skip_existing:
        markdown_files = [
            f for f in all_markdown_files
            if not (extracted_json_root / f"{f.stem}.json").exists()
        ]
        skipped = len(all_markdown_files) - len(markdown_files)
        if skipped:
            print(f"跳过已有 JSON 的 {skipped} 个文档，剩余 {len(markdown_files)} 个待处理")
    else:
        markdown_files = all_markdown_files

    if not markdown_files:
        print("所有文档已处理完毕，无需重新抽取。")
        return

    llm = LLM(
        _modelpath=model_path,
        _temperature=temperature,
        _top_p=top_p,
        _max_tokens=max_tokens,
        _gpu_memory_utilization=gpu_memory_utilization,
        _max_model_len=max_model_len,
        _enable_thinking=False,
        _tensor_parallel_size=tensor_parallel_size,
    )
    llm.load_model()

    reserve = split_output_reserve if split_output_reserve is not None else max_tokens
    max_input_len = (max_model_len - reserve) if max_model_len else None
    total = len(markdown_files)
    print(f"共 {total} 个文档，开始细筛抽取（每批 {extract_batch_size} 个文档）...")

    results: list[dict] = []
    try:
        for batch_start in range(0, total, extract_batch_size):
            batch_files = markdown_files[batch_start: batch_start + extract_batch_size]

            # Each doc may expand into multiple sub-parts if it exceeds max_input_len
            # batch_tasks: list of (md_file, part_idx, total_parts, prompt)
            batch_tasks: list[tuple[Path, int, int, str]] = []
            for md_file in batch_files:
                doc_id = md_file.stem
                text = md_file.read_text(encoding="utf-8")
                if max_input_len is not None and llm.tokenizer is not None:
                    parts = split_by_token_limit(
                        text, doc_id, schema_text, llm.tokenizer, max_input_len, separator
                    )
                else:
                    parts = [text]
                for i, part in enumerate(parts):
                    batch_tasks.append((md_file, i, len(parts), build_extract_prompt(part, doc_id, schema_text)))

            batch_num = batch_start // extract_batch_size + 1
            total_batches = (total + extract_batch_size - 1) // extract_batch_size
            print(f"--- batch {batch_num}/{total_batches} ({len(batch_tasks)} prompts) ---")

            prompts = [prompt for _, _, _, prompt in batch_tasks]
            raw_answers = llm.batch_chat(prompts)
            for (md_file, part_idx, total_parts, _), raw in zip(batch_tasks, raw_answers):
                parsed_part = parse_json_response(raw)
                facts_n = len(parsed_part.get("facts") or []) if parsed_part else 0
                if parsed_part is None:
                    ok = "FAIL"
                elif parsed_part.get("_truncated"):
                    ok = "repaired"
                else:
                    ok = "ok"
                tag = f"[{part_idx+1}/{total_parts}]" if total_parts > 1 else ""
                print(f"  {md_file.stem}{tag} [{ok}] facts={facts_n}")
                if not parsed_part:
                    preview = raw.strip()[:400].replace("\n", " ")
                    print(f"    raw: {preview}")

            # Merge parts per doc and write results
            for md_file in batch_files:
                doc_id = md_file.stem
                doc_answers = [
                    (part_idx, total_parts, raw)
                    for (f, part_idx, total_parts, _), raw in zip(batch_tasks, raw_answers)
                    if f == md_file
                ]

                merged: dict | None = None
                parse_errors: list[str] = []
                for part_idx, total_parts, raw_answer in doc_answers:
                    parsed = parse_json_response(raw_answer)
                    if parsed is None:
                        parse_errors.append(f"part {part_idx + 1}/{total_parts}")
                    elif merged is None:
                        merged = parsed
                    else:
                        for field in ("stock_code", "stock_abbr", "report_year", "report_period"):
                            if not merged.get(field) and parsed.get(field):
                                merged[field] = parsed[field]
                        merged.setdefault("facts", [])
                        merged["facts"].extend(parsed.get("facts") or [])

                output_file = extracted_json_root / f"{doc_id}.json"
                first_raw = doc_answers[0][2] if doc_answers else ""

                if merged is None:
                    status = "PARSE_ERROR"
                    error = "模型返回内容无法解析为 JSON 对象"
                else:
                    merged.setdefault("doc_id", doc_id)
                    merged.setdefault("stock_code", None)
                    merged.setdefault("stock_abbr", None)
                    merged.setdefault("report_year", None)
                    merged.setdefault("report_period", None)
                    if not isinstance(merged.get("facts"), list):
                        merged["facts"] = []
                    write_json(merged, output_file)
                    status = "PARTIAL" if parse_errors else "SUCCESS"
                    error = f"部分片段解析失败: {', '.join(parse_errors)}" if parse_errors else ""

                results.append({
                    "doc_id": doc_id,
                    "markdown_path": str(md_file.resolve()),
                    "output_file": str(output_file.resolve()) if status != "PARSE_ERROR" else "",
                    "status": status,
                    "error": error,
                    "raw_answer": first_raw.strip()[:500],
                })

                if status in ("SUCCESS", "PARTIAL") and merged is not None:
                    facts_count = len(merged.get("facts") or [])
                    stock = merged.get("stock_code") or "?"
                    abbr = merged.get("stock_abbr") or "?"
                    year = merged.get("report_year") or "?"
                    period = merged.get("report_period") or "?"
                    suffix = f"  ({error})" if error else ""
                    print(f"[{status}] {doc_id}  {stock} {abbr}  {year}/{period}  facts={facts_count}{suffix}")
                else:
                    preview = first_raw.strip()[:300].replace("\n", " ")
                    print(f"[{status}] {doc_id}  {error}")
                    print(f"  raw_answer: {preview}")
    finally:
        llm.unload_model()

    write_json(results, results_file)
    print(f"已生成细筛结果 {results_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline controller for prepare, chunking, screening, rebuild, and extraction."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="从 O 中提取 JSON 到集中目录，并分块到 waiting_chunk，再生成 manifest")
    prepare_parser.add_argument("root_o", help="总目录 O，下面包含很多 A 目录")
    prepare_parser.add_argument("--json-root", default="collected_json", help="集中存放提取后 JSON 的目录")
    prepare_parser.add_argument("--waiting-chunk", default="waiting_chunk", help="存放 chunk 文件夹的大目录")
    prepare_parser.add_argument("--manifest", default="chunk_task_manifest.json", help="待筛选任务清单输出路径")
    prepare_parser.add_argument("--char-limit", type=int, default=6000, help="分块字数阈值")
    prepare_parser.add_argument("--execute", action="store_true", help="实际执行提取和删除。默认仅 dry-run")

    chunk_parser = subparsers.add_parser("chunk", help="对已集中存放的 JSON 批量分块")
    chunk_parser.add_argument("json_root", help="存放 *_content_list_v2.json 的目录")
    chunk_parser.add_argument("--waiting-chunk", default="waiting_chunk", help="存放 chunk 文件夹的大目录")
    chunk_parser.add_argument("--char-limit", type=int, default=6000, help="分块字数阈值")

    manifest_parser = subparsers.add_parser("manifest", help="遍历 waiting_chunk，生成待筛选任务清单")
    manifest_parser.add_argument("waiting_chunk_root", help="存放 chunk 文件夹的大目录")
    manifest_parser.add_argument("--output", default="chunk_task_manifest.json", help="任务清单输出路径")

    screen_parser = subparsers.add_parser("screen", help="将 waiting_chunk 转成 waiting_markdown，并调用模型做初筛后写入 new_chunk")
    screen_parser.add_argument("waiting_chunk_root", help="存放待筛选 chunk 文件夹的大目录")
    screen_parser.add_argument("--waiting-markdown", default="waiting_markdown", help="初筛前临时 markdown 输出目录")
    screen_parser.add_argument("--new-chunk", default="new_chunk", help="初筛结果为 YES 的 chunk 输出目录")
    screen_parser.add_argument("--results", default="screen_results.json", help="初筛结果 JSON 输出路径")
    screen_parser.add_argument("--model-path", required=True, help="vLLM 模型路径或模型名")
    screen_parser.add_argument("--rule-text", required=True, help="初筛规则文本")
    screen_parser.add_argument("--temperature", type=float, default=0.1, help="采样温度")
    screen_parser.add_argument("--top-p", type=float, default=0.8, help="top-p")
    screen_parser.add_argument("--max-tokens", type=int, default=32, help="最大输出 token 数")
    screen_parser.add_argument("--gpu-memory-utilization", type=float, default=0.63, help="vLLM 显存占用比例")

    rebuild_parser = subparsers.add_parser("rebuild", help="遍历 new_chunk，重组筛选后的 chunk 为 extracted_data markdown")
    rebuild_parser.add_argument("new_chunk_root", help="存放已筛选 chunk 文件夹的大目录")
    rebuild_parser.add_argument("--output", default="extracted_data", help="markdown 输出目录")
    rebuild_parser.add_argument("--separator", default="\n---\n", help="chunk 编号断开时插入的分隔线")

    extract_parser = subparsers.add_parser("extract", help="对 extracted_data markdown 做细筛抽取并输出 extracted_json")
    extract_parser.add_argument("extracted_data_root", help="存放重组 markdown 的目录")
    extract_parser.add_argument("--output", default="extracted_json", help="抽取 JSON 输出目录")
    extract_parser.add_argument("--results", default="extract_results.json", help="细筛结果 JSON 输出路径")
    extract_parser.add_argument("--model-path", required=True, help="vLLM 模型路径或模型名")
    extract_parser.add_argument("--schema-text", required=True, help="细筛抽取 schema 文本")
    extract_parser.add_argument("--temperature", type=float, default=0.1, help="采样温度")
    extract_parser.add_argument("--top-p", type=float, default=0.8, help="top-p")
    extract_parser.add_argument("--max-tokens", type=int, default=4096, help="最大输出 token 数")
    extract_parser.add_argument("--gpu-memory-utilization", type=float, default=0.63, help="vLLM 显存占用比例")

    args = parser.parse_args()

    if args.command == "prepare":
        run_prepare(
            root_o=Path(args.root_o).resolve(),
            extracted_json_root=Path(args.json_root).resolve(),
            waiting_chunk_root=Path(args.waiting_chunk).resolve(),
            manifest_file=Path(args.manifest).resolve(),
            char_limit=args.char_limit,
            dry_run=not args.execute,
        )
    elif args.command == "chunk":
        chunk_all_jsons(
            json_root=Path(args.json_root).resolve(),
            waiting_chunk_root=Path(args.waiting_chunk).resolve(),
            char_limit=args.char_limit,
        )
    elif args.command == "manifest":
        build_manifest(
            waiting_chunk_root=Path(args.waiting_chunk_root).resolve(),
            manifest_file=Path(args.output).resolve(),
        )
    elif args.command == "screen":
        run_screen(
            waiting_chunk_root=Path(args.waiting_chunk_root).resolve(),
            waiting_markdown_root=Path(args.waiting_markdown).resolve(),
            new_chunk_root=Path(args.new_chunk).resolve(),
            results_file=Path(args.results).resolve(),
            model_path=args.model_path,
            rule_text=args.rule_text,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
            gpu_memory_utilization=args.gpu_memory_utilization,
        )
    elif args.command == "rebuild":
        run_rebuild(
            new_chunk_root=Path(args.new_chunk_root).resolve(),
            extracted_data_root=Path(args.output).resolve(),
            separator=args.separator,
        )
    elif args.command == "extract":
        run_extract(
            extracted_data_root=Path(args.extracted_data_root).resolve(),
            extracted_json_root=Path(args.output).resolve(),
            results_file=Path(args.results).resolve(),
            model_path=args.model_path,
            schema_text=args.schema_text,
            temperature=args.temperature,
            top_p=args.top_p,
            max_tokens=args.max_tokens,
            gpu_memory_utilization=args.gpu_memory_utilization,
        )


if __name__ == "__main__":
    main()

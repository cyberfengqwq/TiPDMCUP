#!/usr/bin/env python3
"""
批量导出赛题答案到 result_2.xlsx / result_3.xlsx

用法:
    python scripts/batch_export.py 2          # 只导出任务二
    python scripts/batch_export.py 3          # 只导出任务三
    python scripts/batch_export.py all        # 全部导出
    python scripts/batch_export.py 2 --data-dir /path/to/附件 --output-dir ./output
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import openpyxl

from core.agent.pipeline import Agent
from core.services.vllm_service import LLM

ANALYSIS_MODEL = "/home/qwq/models/Qwen2.5-7B-Instruct"
SQL_MODEL = "/home/qwq/models/qwen2_5_7b_sql"

BATCH_USER_ID = "batch_export"
BATCH_COMPANY_ID = "batch"

CHART_TYPE_ZH = {
    "line": "折线图",
    "bar": "柱状图",
    "pie": "饼图",
    "table": "表格",
    "none": "无",
}


def load_llms() -> tuple[LLM, LLM]:
    print("正在加载 SQL 模型...")
    sql_llm = LLM(
        _modelpath=SQL_MODEL,
        _temperature=0.2,
        _top_p=0.9,
        _max_tokens=512,
        _gpu_memory_utilization=0.3,
    )
    sql_llm.load_model()

    print("正在加载分析模型...")
    analysis_llm = LLM(
        _modelpath=ANALYSIS_MODEL,
        _temperature=0.7,
        _top_p=0.8,
        _max_tokens=512,
        _gpu_memory_utilization=0.5,
    )
    analysis_llm.load_model()

    print("模型加载完成\n")
    return sql_llm, analysis_llm


def read_questions(xlsx_path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(xlsx_path)
    ws = wb.active
    rows = []
    first = True
    for row in ws.iter_rows(values_only=True):
        if first:
            first = False
            continue
        if row[0] is None:
            continue
        rows.append(
            {
                "problem_id": str(row[0]),
                "question_type": str(row[1] or ""),
                "questions_raw": str(row[2] or ""),
            }
        )
    return rows


def run_problem(
    sql_llm: LLM,
    analysis_llm: LLM,
    problem_id: str,
    questions: list[str],
    task: int,
) -> dict:
    """为一道题新建 Agent，顺序跑完所有对话轮次，返回汇总结果。"""
    agent = Agent(
        user_id=BATCH_USER_ID,
        company_id=BATCH_COMPANY_ID,
        chat_id=f"batch_{problem_id}",
        sql_llm=sql_llm,
        analysis_llm=analysis_llm,
    )

    qa_pairs: list[dict] = []
    sqls: list[str] = []
    chart_types: list[str] = []

    for q in questions:
        result = agent.run(q, problem_id=problem_id, task=task)
        a = result.get("A", {})

        content = a.get("content", "")
        image = a.get("image", [])
        sql = a.get("sql", "")
        ct = a.get("chart_type", "none")
        references = a.get("references", [])

        if sql and not sql.startswith("--"):
            sqls.append(sql)
        if ct != "none":
            chart_types.append(ct)

        entry: dict = {"Q": q, "A": {"content": content, "image": image}}
        if task == 3 and references:
            entry["A"]["references"] = references
        qa_pairs.append(entry)

    return {
        "qa_pairs": qa_pairs,
        "sqls": sqls,
        "chart_types": chart_types,
    }


def _write_header_row(ws, headers: list[str]) -> None:
    ws.append(headers)
    for cell in ws[1]:
        cell.font = openpyxl.styles.Font(bold=True)


def _set_col_widths(ws, widths: dict[str, int]) -> None:
    for col_letter, width in widths.items():
        ws.column_dimensions[col_letter].width = width
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = openpyxl.styles.Alignment(wrap_text=True, vertical="top")


def export_task2(
    questions_xlsx: Path,
    output_path: Path,
    sql_llm: LLM,
    analysis_llm: LLM,
) -> None:
    rows = read_questions(questions_xlsx)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    _write_header_row(ws, ["编号", "问题", "SQL查询语句", "图形格式", "回答"])

    for row in rows:
        problem_id = row["problem_id"]
        questions_raw = row["questions_raw"]

        try:
            q_list = json.loads(questions_raw)
            questions = [item["Q"] for item in q_list]
        except Exception as e:
            print(f"[{problem_id}] 解析问题失败: {e}")
            continue

        print(f"[{problem_id}] 开始处理 ({len(questions)} 轮)...")
        result = run_problem(sql_llm, analysis_llm, problem_id, questions, task=2)

        sql_str = "\n---\n".join(result["sqls"]) if result["sqls"] else "无"
        chart_str = (
            "；".join(CHART_TYPE_ZH.get(ct, ct) for ct in result["chart_types"])
            if result["chart_types"]
            else "无"
        )
        answer_json = json.dumps(result["qa_pairs"], ensure_ascii=False, indent=None)

        ws.append([problem_id, questions_raw, sql_str, chart_str, answer_json])
        print(f"[{problem_id}] 完成")

    _set_col_widths(ws, {"A": 10, "B": 30, "C": 40, "D": 12, "E": 80})
    wb.save(output_path)
    print(f"\n✓ 已保存: {output_path}")


def export_task3(
    questions_xlsx: Path,
    output_path: Path,
    sql_llm: LLM,
    analysis_llm: LLM,
) -> None:
    rows = read_questions(questions_xlsx)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    _write_header_row(ws, ["编号", "问题", "SQL查询语句", "回答"])

    for row in rows:
        problem_id = row["problem_id"]
        questions_raw = row["questions_raw"]

        try:
            q_list = json.loads(questions_raw)
            questions = [item["Q"] for item in q_list]
        except Exception as e:
            print(f"[{problem_id}] 解析问题失败: {e}")
            continue

        print(f"[{problem_id}] 开始处理 ({len(questions)} 轮)...")
        result = run_problem(sql_llm, analysis_llm, problem_id, questions, task=3)

        sql_str = "\n---\n".join(result["sqls"]) if result["sqls"] else "无"
        answer_json = json.dumps(result["qa_pairs"], ensure_ascii=False, indent=None)

        ws.append([problem_id, questions_raw, sql_str, answer_json])
        print(f"[{problem_id}] 完成")

    _set_col_widths(ws, {"A": 10, "B": 30, "C": 40, "D": 80})
    wb.save(output_path)
    print(f"\n✓ 已保存: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="批量导出赛题答案")
    parser.add_argument("task", choices=["2", "3", "all"], help="导出任务二、三或全部")
    parser.add_argument(
        "--data-dir",
        default="示例数据",
        help="附件所在目录（默认: 示例数据）",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="输出目录（默认: 当前目录）",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sql_llm, analysis_llm = load_llms()

    if args.task in ("2", "all"):
        export_task2(
            questions_xlsx=data_dir / "附件4：问题汇总.xlsx",
            output_path=output_dir / "result_2.xlsx",
            sql_llm=sql_llm,
            analysis_llm=analysis_llm,
        )

    if args.task in ("3", "all"):
        export_task3(
            questions_xlsx=data_dir / "附件6：问题汇总.xlsx",
            output_path=output_dir / "result_3.xlsx",
            sql_llm=sql_llm,
            analysis_llm=analysis_llm,
        )


if __name__ == "__main__":
    main()

from __future__ import annotations

import logging
import re
from typing import Any

from config.db_schema import DATABASE_SCHEMA_DICT

logger = logging.getLogger(__name__)


def build_schema_text() -> str:
    lines: list[str] = []
    for table_name, fields in DATABASE_SCHEMA_DICT.items():
        cols = ", ".join(fields.keys())
        lines.append(f"{table_name}: {cols}")
    return "\n".join(lines)


def _strip_sql_fences(text: str) -> str:
    s = text.strip()
    s = s.replace("```sql", "").replace("```", "").strip()
    m = re.search(r"(?is)\b(select|with)\b", s)
    if m:
        s = s[m.start() :]
    return s.strip()


def _balance_parentheses(sql: str) -> str:
    left = sql.count("(")
    right = sql.count(")")
    if right > left:
        extra = right - left
        out = []
        for ch in reversed(sql):
            if ch == ")" and extra > 0:
                extra -= 1
                continue
            out.append(ch)
        sql = "".join(reversed(out))
    elif left > right:
        sql = sql + (")" * (left - right))
    return sql


def _cheap_fix(sql: str) -> str:
    s = _strip_sql_fences(sql)
    s = re.sub(r";+\s*$", ";", s)
    s = _balance_parentheses(s)
    s = re.sub(r"\bIN\s*\(([^)]*)\)\s*\)", r"IN (\1)", s, flags=re.IGNORECASE)
    return s


def build_repair_prompt(
    bad_sql: str,
    db_error: str,
    user_question: str,
) -> str:
    schema_text = build_schema_text()
    return f"""
你是一个 MySQL SQL 修复器。你的任务是把错误 SQL 修成“可在 MySQL 执行”的正确 SQL。
只输出一条 SQL，不要解释，不要 markdown，不要多条语句。

【用户问题】
{user_question}

【数据库报错】
{db_error}

【错误SQL】
{bad_sql}

【可用表结构（只能使用这些表和字段）】
{schema_text}

修复规则：
1) 仅输出一条可执行 MySQL SQL。
2) 不能使用不存在的字段。
3) 不要使用 median()、DATEDIFF(report_period, ...) 这类不适配写法。
4) report_period 是字符串（如 2022Q3、2024FY），按字符串逻辑处理。
5) 语法必须正确（括号、子查询、聚合、别名等）。
""".strip()


def try_execute_with_autocorrect(
    db_service: Any,
    sql_llm: Any,
    user_question: str,
    generated_sql: str,
    max_retries: int = 1,
) -> tuple[str, list[dict], bool]:
    sql = _cheap_fix(generated_sql)

    try:
        result = db_service.execute(sql)
        return sql, result, False
    except Exception as e:
        last_error = str(e)
        logger.warning(f"[SQLAutoCorrect] 首次执行失败: {last_error}")

    for i in range(max_retries):
        prompt = build_repair_prompt(
            bad_sql=sql,
            db_error=last_error,
            user_question=user_question,
        )
        repaired = sql_llm.chat(prompt).strip()
        repaired = _cheap_fix(repaired)

        logger.info(f"[SQLAutoCorrect] 第{i + 1}次修复后SQL: {repaired}")
        try:
            result = db_service.execute(repaired)
            logger.info(f"[SQLAutoCorrect] 第{i + 1}次修复执行成功")
            return repaired, result, True
        except Exception as e:
            last_error = str(e)
            sql = repaired
            logger.warning(f"[SQLAutoCorrect] 第{i + 1}次修复执行失败: {last_error}")

    raise RuntimeError(f"SQL 自动修复失败: {last_error}")

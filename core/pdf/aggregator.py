# core/pdf/aggregator.py
from collections import defaultdict

import pandas as pd

from config.db_schema import DATABASE_SCHEMA_DICT
from core.pdf.models import MetricRecord


def metric_records_to_rows(
    records: list[MetricRecord],
) -> dict[str, list[dict[str, object]]]:
    """把 MetricRecord 聚合成四张表的 row（dict 列表）

    Arg:
        records (list[MetirRecord]) : metric_extract 中返回的列表，其中有数个 MeticRecord 类

    Return:
        dict[str, list[dict]] : key 是目标表名，value 是一行一行的 CSV 数据
    """
    # 如果下方的 key 对应的 value (list[MetricRecord]) 不存在，系统自动生成空列表
    # 等待填充选拔好的 MR 指标对象 和 他的归属
    grouped: dict[tuple, list[MetricRecord]] = defaultdict(list)

    # Loop_1: 遍历 MR 对象，根据字段创建空列表，等待后续填充
    for r in records:
        key = (
            r.table_name,
            r.stock_code,
            r.report_period,
            r.report_year,
            r.report_quarter,
        )
        grouped[key].append(r)

    # 最终输出结果
    out: dict[str, list[dict]] = {
        "core_performance_indicators_sheet": [],
        "balance_sheet": [],
        "income_sheet": [],
        "cash_flow_sheet": [],
    }

    # Loop_2: 遍历 grouped 中分好的数据拿出来，recs 是指多个 MetricRecord 对象
    for (
        table_name,
        stock_code,
        report_period,
        report_year,
        report_quarter,
    ), recs in grouped.items():
        # 取出表中应有的“标准英文名”到一个列表当中，即对应的 key
        schema_cols: list[str] = list(DATABASE_SCHEMA_DICT[table_name].keys())
        """
        将所有“标准英文名”作为 key, 同时利用扁平化处理自动分配 “空白” 的 None 值;
        每次遍历都有一个 row, 利用 table_name 对应四大目标表格之一
        """
        row: dict[str, object] = {c: pd.NA for c in schema_cols}

        # 开始根据 Loop_2 遍历传的变量，替换 None 值
        if "stock_code" in row:
            row["stock_code"] = stock_code
        if "stock_abbr" in row:
            row["stock_abbr"] = recs[0].stock_abbr
        if "report_period" in row:
            row["report_period"] = report_period
        if "report_year" in row:
            row["report_year"] = report_year

        # 新建临时字典，选拔相同字段中 confidence 最高的
        best_by_field: dict[str, MetricRecord] = {}
        # Loop_2.1: 开始遍历 (选拔) 数个 MetricRecord 对象
        for r in recs:
            # 开始比对，如果该字段不在空白的 row 中，跳过该 MR 对象
            if r.field_key not in row:
                continue
            old = best_by_field.get(r.field_key)

            if old is None or r.confidence > old.confidence:
                """
                若遍历到的 r 之前没有存在 best_by_field 或
                当前对象的置信度（r.confidence）高于旧对象
                """
                # 完成去重，保留置信度更高的对象
                best_by_field[r.field_key] = r

        # Loop_2.2: 把 best_by_field 中选拔出来的 "字段" 和 MR 对象 放入 row（fk == field_key，字段）
        for fk, best_MR in best_by_field.items():
            # 对比字段，填充置信度最高的 MR 对象
            row[fk] = best_MR.value

        # 可选调试：中间层保留季度信息（不写入CSV schema）
        row["_report_quarter"] = report_quarter

        out[table_name].append(row)

    # Loop_3: 补充序号，保证存进 MySQL 时有唯一主键
    for t_name, rows in out.items():
        if "serial_number" in DATABASE_SCHEMA_DICT[t_name]:
            for i, r in enumerate(rows, start=1):
                r["serial_number"] = i
    return out

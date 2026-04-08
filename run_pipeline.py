from pathlib import Path

from core.pdf.pipeline import PDFPipeline


def main() -> None:
    pipeline = PDFPipeline()

    # 1) 单个PDF调试
    single_pdf = Path(
        "示例数据/附件2：财务报告/reports-上交所/600080_20240427_0WKP.pdf"
    )
    rows_by_table = pipeline.process_one_pdf(single_pdf)
    print("===== 单PDF调试结果 =====")
    for tname, rows in rows_by_table.items():
        print(f"{tname}: {len(rows)} rows")
        if rows:
            print("sample row keys:", list(rows[0].keys())[:8])

    # 2) 整个目录批处理导出CSV
    # 注意：这里是“一个公司一个文件夹”的模式，如果你的目录不是这个结构，先用你当前目录做单PDF调试
    # company_folder = Path("示例数据/附件2：财务报告/reports-上交所")
    # out_dir = Path("output")
    # pipeline.process_company_folder(company_folder, out_dir)

    # 3) 根目录批处理（包含多个公司子文件夹时再启用）
    # root_dir = Path("示例数据/附件2：财务报告")
    # out_dir = Path("output")
    # pipeline.process_reports_root(root_dir, out_dir)


if __name__ == "__main__":
    main()

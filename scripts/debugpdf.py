from pathlib import Path

from core.pdf.pipeline import PDFPipeline


def main() -> None:
    pdf = PDFPipeline()

    # 处理上交所的PDF文件
    pdf.process_company_folder(
        "示例数据/附件2：财务报告/reports-上交所",
        "./data/output",
    )

    # 处理深交所的PDF文件
    pdf.process_company_folder(
        "示例数据/附件2：财务报告/reports-深交所",
        "./data/output",
    )


if __name__ == "__main__":
    main()

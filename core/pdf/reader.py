# core/pdf/reader.py
from pathlib import Path

import pandas as pd
import pdfplumber
from matplotlib.table import table

from core.pdf.models import RawTable


class PDFReader:
    def read_tables(self, pdf_path: str | Path) -> list[RawTable]:
        pdf_path = Path(pdf_path)
        results: list[RawTable] = []

        with pdfplumber.open(pdf_path) as pdf:
            for p_idx, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                if not tables:
                    continue
                for t_idx, table in enumerate(tables, start=1):
                    if not table:
                        continue
                    cleaned = [
                        row
                        for row in table
                        if row
                        and any(
                            cell is not None and str(cell).strip() != "" for cell in row
                        )
                    ]
                    if not cleaned:
                        continue
                    results.append(
                        RawTable(
                            pdf_path=pdf_path,
                            page_no=p_idx,
                            table_no=t_idx,
                            df=pd.DataFrame(cleaned),
                        )
                    )
        return results

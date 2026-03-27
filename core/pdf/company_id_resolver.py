# core/pdf/company_id_resolver.py

import re
from pathlib import Path
from typing import Optional

import pdfplumber

_STOCK_CODE_RE = re.compile(r"\b(00\d{4}|30\d{4}|60\d{4}|68\d{4}|8\d{5})\b")


def _extract_stock_code_from_filename(pdf_path: Path) -> Optional[str]:
    """从文件名中获取股票代码作为公司代码

    Arg:
        pdf_path (Path) : PDF 文件路径

    Return:
        Optional[str] : 字符串 or None
    """
    m = _STOCK_CODE_RE.search(pdf_path.stem)  # 在 PDF 的纯文件名中搜索股票代码
    return m.group(1) if m else None  # 如果有，获取正则表达式的第一个股票代码


def _extract_stock_code_from_text_first_pages(
    pdf_path: Path, max_pages: int = 3
) -> Optional[str]:
    """从文件中提取股票代码作为公司代码

    Args:
        pdf_path (Path) : PDF 文件路径
        max_pages (int) : 限制在前三页文件中查找

    Return：
        Optional[str] ： 字符串 or None
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:max_pages]:
                text = page.extract_text() or ""
                m = _STOCK_CODE_RE.search(text)
                if m:
                    return m.group(1)
    except Exception:
        return None
    return None

    def resolve_company_id(
        pdf_path: str | Path,
        stock_code: str | None,
        prefer_stock_code_as_company_id: bool = True,
    ) -> str:
        """统一公司 ID 获取接口

        Args:
            pdf_path (str | Path) : PDF 文件路径
            stock_code (str | None) ： 股票代码
            prefer_stock_code_as_company_id (bool) : 防止要求用“公司名称”或者“文件夹名字”做公司代称

        Return：
            str ： 公司代称
        """

import pandas as pd

from data.data_trans_pdf_yyf import DF


def main() -> None:
    df: DF = DF()
    ex1: list[list[int]] = [[1, 2, 4], [2, 4, 6]]
    df.kpi = pd.DataFrame(ex1)


if __name__ == "__main__":
    main()

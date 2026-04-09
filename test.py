from pathlib import Path

import pandas as pd


def main() -> None:
    file = Path("data/output/reports-上交所/reports-上交所_balance_sheet.csv")
    df = pd.read_csv(file)
    print(df.head())


if __name__ == "__main__":
    main()

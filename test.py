from rag.sql_retriever import DualRetrieval


def main() -> None:
    rag = DualRetrieval(user="test_user")

    rag.get_all_tables()


if __name__ == "__main__":
    main()

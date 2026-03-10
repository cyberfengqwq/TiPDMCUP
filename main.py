# import web.webAPI

# if __name__ == "__main__":
#     web.webAPI.run_app()


from agent.pipeline import Agent


def main() -> None:
    agent = Agent()
    ques: str = "我要看2024年第三季度的财报"

    sql: str = agent.run_pipeline(ques)
    print(sql)


if __name__ == "__main__":
    main()

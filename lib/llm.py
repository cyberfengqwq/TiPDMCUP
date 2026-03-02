import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class LLM:
    def __init__(
        self,
        _api_key=os.getenv("DASHSCOPE_API_KEY"),
        _base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    ) -> None:
        self.client = OpenAI(
            api_key=_api_key,
            base_url=_base_url,
        )
        self.prompt = ""
        self.role = "你是一个资深的金融数据分析师。根据以下 MySQL 表结构，\
                     将用户的自然语言问题转化为 SQL 查询语句。\
                     不要输出任何解释，只能输出纯 SQL 语句！"

        self.model = "qwen3.5-flash"
        self.message: list = [
            {"role": "system", "content": self.role},
            {"role": "user", "content": self.prompt},
        ]

    def chat(self, prompt: str) -> str:
        self.prompt = prompt
        completion = self.client.chat.completions.create(
            model=self.model, messages=self.message
        )
        return str(completion.choices[0].message.content)


def main() -> None:
    pass


if __name__ == "__main__":
    main()

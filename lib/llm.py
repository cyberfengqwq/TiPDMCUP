import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def main() -> None:
    prompt: str = "你好啊"

    message: list = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]
    try:
        client = OpenAI(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        completion = client.chat.completions.create(
            model="qwen3.5-flash", messages=message
        )
        print(completion.choices[0].message.content)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()

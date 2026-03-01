import os

import dashscope
from dashscope import Generation
from dotenv import load_dotenv

load_dotenv()

messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "你是谁？"},
]
response = Generation.call(
    # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key = "sk-xxx",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    model="qwen-plus",  # 模型列表：https://help.aliyun.com/model-studio/getting-started/models
    messages=messages,
    result_format="message",
)

if response.status_code == 200:
    print(response.output.choices[0].message.content)
else:
    print(f"HTTP返回码：{response.status_code}")
    print(f"错误码：{response.code}")
    print(f"错误信息：{response.message}")
    print(
        "请参考文档：https://help.aliyun.com/model-studio/developer-reference/error-code"
    )

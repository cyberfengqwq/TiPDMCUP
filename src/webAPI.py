import uvicorn
from fastapi import FastAPI

from lib.llm import LLM

app = FastAPI(title="ticup")


@app.post("/chat")
async def chat_endpoint(msg: str):
    llm: LLM = LLM()
    return llm.chat(msg)


uvicorn.run(app, host="0.0.0.0", port=1515)

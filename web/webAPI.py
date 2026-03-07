import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from lib.llm import LLM

app = FastAPI(title="ticup")


class ChatRequest(BaseModel):
    prompt: str


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    llm: LLM = LLM()
    return llm.chat(request.prompt)


def run_app() -> None:

    uvicorn.run(app, host="0.0.0.0", port=1515)

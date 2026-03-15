# web/webAPI.py

from dataclasses import dataclass
from threading import Thread

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from agent.pipeline import Agent

app = FastAPI(title="ticup")


class ChatRequest(BaseModel):
    prompt: str


agent = Agent()


@app.post("/chat")
def chat_endpoint(request: ChatRequest) -> str:
    return agent.run_pipeline(request.prompt)


def run_app() -> None:
    uvicorn.run(app, host="0.0.0.0", port=1515)

# web/webAPI.py

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from agent.pipeline import SQLRAGPipeline

app = FastAPI(title="ticup")

sessions: dict[str, SQLRAGPipeline] = {}


def get_or_create_session(session_id: str) -> SQLRAGPipeline:
    if session_id not in sessions:
        sessions[session_id] = SQLRAGPipeline(session_id)
    return sessions[session_id]


class ChatRequest(BaseModel):
    prompt: str
    session_id: str


@app.post("/chat")
def chat_endpoint(request: ChatRequest) -> str:
    user_agent: SQLRAGPipeline = get_or_create_session(request.session_id)

    return user_agent.run(request.prompt)


def run_app() -> None:
    uvicorn.run(app, host="0.0.0.0", port=1515)

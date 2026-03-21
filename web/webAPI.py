# web/webAPI.py

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from agent.pipeline import Agent

app = FastAPI(title="ticup")

sessions: dict[str, Agent] = {}


def get_or_create_session(session_id: str) -> Agent:
    if session_id not in sessions:
        sessions[session_id] = Agent(session_id)
    return sessions[session_id]


class ChatRequest(BaseModel):
    prompt: str
    session_id: str

@app.post("/login")
def login() -> tuple[dict, int]:




@app.post("/chat")
def chat_endpoint(request: ChatRequest) -> str:
    user_agent: Agent = get_or_create_session(request.session_id)

    return user_agent.run(request.prompt)


def run_app() -> None:
    uvicorn.run(app, host="0.0.0.0", port=1515)

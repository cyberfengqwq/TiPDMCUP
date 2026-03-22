# web/webAPI.py

import uvicorn
from fastapi import FastAPI
from flask import request
from pydantic import BaseModel

from agent.pipeline import Agent
from core.company import Company
from core.core import Data

app = FastAPI(title="ticup")

sessions: dict[str, Agent] = {}


def get_or_create_session(session_id: str) -> Agent:
    if session_id not in sessions:
        sessions[session_id] = Agent(session_id)
    return sessions[session_id]


class ChatRequest(BaseModel):
    prompt: str
    session_id: str


datas: Data = Data()
datas.load_data()


@app.post("/login")
def login() -> tuple[dict, int]:
    payload: dict = request.get_json(silent=True) or {}
    name: str = payload["name"]
    psw: str = payload["password"]
    company_name: str = payload["company"]
    if datas.companies.get(company_name, True):
        print("公司不存在！！")
        return {}, 400
    company: Company | None = datas.companies.get(company_name)
    assert company is not None
    if


@app.post("/chat")
def chat_endpoint(request: ChatRequest) -> str:
    user_agent: Agent = get_or_create_session(request.session_id)

    return user_agent.run(request.prompt)


def run_app() -> None:
    uvicorn.run(app, host="0.0.0.0", port=1515)

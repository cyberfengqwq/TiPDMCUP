# web/webAPI.py

import uvicorn
from fastapi import FastAPI
from flask import request
from pydantic import BaseModel

from agent.pipeline import Agent
from core.company import Company
from core.core import Data
from core.user import User

app = FastAPI(title="ticup")

sessions: dict[str, Agent] = {}


def get_or_create_session(session_id: str) -> Agent:
    if session_id not in sessions:
        sessions[session_id] = Agent(session_id)
    return sessions[session_id]


class ChatRequest(BaseModel):
    prompt: str
    session_id: str


class LoginRequset(BaseModel):
    name: str
    password: str
    company: str


datas: Data = Data()
# datas.load_data()


@app.post("/login")
def login(payload: LoginRequset) -> tuple[dict, int]:
    name: str = payload.name
    psw: str = payload.password
    company_name: str = payload.company
    if datas.companies.get(company_name, True):
        print("公司不存在！！")
        return {}, 400
    company: Company | None = datas.companies.get(company_name)
    assert company is not None
    if company.users.get(name, True):
        print("用户不存在！！")
        return {}, 400
    user: User | None = company.users.get(name)
    assert user is not None
    if user.verification_psw(psw):
        return user.user_file_dict, 200
    return {}, 400


@app.post("/chat")
def chat_endpoint(request: ChatRequest) -> str:
    user_agent: Agent = get_or_create_session(request.session_id)

    return user_agent.run(request.prompt)


def run_app() -> None:
    uvicorn.run(app, host="0.0.0.0", port=1515)

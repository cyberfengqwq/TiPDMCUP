# web/webAPI.py

import logging
from pathlib import Path

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from starlette import status

from core.agent.pipeline import Agent
from core.domain.models import SessionPrincipal
from core.services.auth_service import AuthService
from core.services.company_registry import CompanyRegistry
from core.services.profile_service import ProfileService
from core.stores.company_store import CompanyStore
from core.stores.membership_store import MembershipStore
from core.stores.session_store import SessionStore
from core.stores.user_store import UserStore

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="ticup", version="1.0.0")
bearer_scheme = HTTPBearer(auto_error=False)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
USER_JSON = PROJECT_ROOT / "data/users.json"
COMPANY_JSON = PROJECT_ROOT / "data/companies.json"
MEMBERSHIP_JSON = PROJECT_ROOT / "data/memberships.json"
SESSION_JSON = PROJECT_ROOT / "data/sessions.json"


user_store = UserStore(USER_JSON)
company_store = CompanyStore(COMPANY_JSON)
membership_store = MembershipStore(MEMBERSHIP_JSON)
session_store = SessionStore(SESSION_JSON)

company_registry = CompanyRegistry(company_store)
company_registry.reload()

auth_service = AuthService(
    user_store=user_store,
    company_store=company_store,
    membership_store=membership_store,
    session_store=session_store,
)


class LoginRequest(BaseModel):
    user_id: str = Field(
        ..., description="用户ID（当前 AuthService.login 使用 user_id）"
    )
    password: str
    company_id: str | None = Field(None, description="公司ID（推荐字段）")
    compay_id: str | None = Field(None, description="兼容旧字段拼写")


class LoginResponse(BaseModel):
    session_id: str
    user_id: str
    company_id: str
    roles: list[str]
    expires_at: str


class ChatRequest(BaseModel):
    prompt: str
    chat_id: str = Field(..., description="前端对话窗口ID")
    is_end: bool = Field(False, description="是否结束本次会话（用于触发画像更新）")


class ChatResponse(BaseModel):
    answer: str


class LogoutRequest(BaseModel):
    session_id: str | None = None


class MeResponse(BaseModel):
    session_id: str
    user_id: str
    company_id: str
    roles: list[str]
    expires_at: str


def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> SessionPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺失权限：Bearer <session_id>",
        )

    session_id = credentials.credentials.strip()
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    return session


@app.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    company_id = (payload.company_id or payload.compay_id or "").strip()
    if not company_id:
        raise HTTPException(status_code=400, detail="company_id is required")

    session = auth_service.login(
        user_id=payload.user_id,
        password=payload.password,
        company_id=company_id,
    )

    if session is None:
        raise HTTPException(status_code=400, detail="Login Failed")

    return LoginResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        company_id=session.active_company_id,
        roles=session.roles,
        expires_at=session.expires_at.isoformat(),
    )


@app.get("/me", response_model=MeResponse)
def me(current_session=Depends(get_current_session)) -> MeResponse:
    return MeResponse(
        session_id=current_session.session_id,
        user_id=current_session.user_id,
        company_id=current_session.active_company_id,
        roles=current_session.roles,
        expires_at=current_session.expires_at.isoformat(),
    )


@app.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    current_session: SessionPrincipal = Depends(get_current_session),
) -> ChatResponse:
    user_id: str = current_session.user_id
    company_id: str = current_session.active_company_id

    agent = Agent(
        user_id=user_id,
        company_id=company_id,
        chat_id=payload.chat_id,
    )
    answer = agent.run(payload.prompt)

    if payload.is_end:
        profile_service = ProfileService(user_id=user_id, chat_id=payload.chat_id)
        background_tasks.add_task(profile_service.sum_and_update_profile)

    return ChatResponse(answer=answer)


@app.post("/logout")
def logout(
    payload: LogoutRequest,
    current_session=Depends(get_current_session),
):
    target_session_id = payload.session_id or current_session.session_id
    session_store.revoke(target_session_id)
    return {"ok": True}


def run_app() -> None:
    uvicorn.run(app, host="0.0.0.0", port=1515)

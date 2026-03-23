# core/domain/models.py

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Company:
    """
    用来存放公司数据
    """

    id: str
    name: str
    status: str
    created_at: datetime


@dataclass(frozen=True)
class UserRecord:
    """
    用来存放用户数据
    """

    id: str
    username: str
    password_hash: str
    status: str


@dataclass(frozen=True)
class Membership:
    """
    连接用户与公司所属关系
    """

    user_id: str
    company_id: str
    roles: list[str]
    joined_at: datetime


@dataclass
class SessionPrincipal:
    """
    启动服务器时实例化的对象
    """

    session_id: str
    user_id: str
    active_company_id: str
    roles: list[str] = field(default_factory=list[str])
    issued_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime = field(default_factory=datetime.now)

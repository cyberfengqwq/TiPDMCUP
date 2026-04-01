# core/services/auth_service.py

import uuid
from datetime import UTC, datetime, timedelta

from core.domain.models import Company, SessionPrincipal, UserRecord
from core.services.company_registry import CompanyRegistry
from core.services.password_service import PasswordService
from core.stores.company_store import CompanyStore
from core.stores.membership_store import MembershipStore
from core.stores.session_store import SessionStore
from core.stores.user_store import UserStore


class AuthService:
    """
    验证服务类，用来解析用户登陆以及构建 Runtime Session
    """

    def __init__(
        self,
        user_store: UserStore,
        company_store: CompanyStore,
        membership_store: MembershipStore,
        session_store: SessionStore,
    ) -> None:

        self.user_store = user_store
        self.company_store = company_store
        self.membership_store = membership_store
        self.session_store = session_store

        self.company_reg = CompanyRegistry(self.company_store)
        self.company_reg.reload()

    def login(
        self,
        user_id: str,
        password: str,
        company_id: str,
    ) -> SessionPrincipal | None:
        """登陆接口
        Args:
            user_id             : str 用户 id
            password            : str 用户输入的密码
            company_id          : str 公司 id

        Returns:
            SessionPrincipal    : 登陆成功返回 RuntimeSession 数据对象
            None                : 登陆失败
        """

        user: UserRecord | None = self.user_store.get_by_id(user_id)
        if not user:
            return
        login_state: bool = PasswordService.verify_password(
            password, user.password_hash
        )
        if not login_state:
            return
        company: Company | None = self.company_reg.get(company_id)
        if not company:
            return
        member: list[str] | None = self.membership_store.get_role_in_company(
            user_id, company_id
        )
        if not member:
            return

        session_id = str(uuid.uuid4())

        current_time = datetime.now(UTC)
        expire_time = current_time + timedelta(hours=2)
        session: SessionPrincipal = SessionPrincipal(
            session_id=session_id,
            user_id=user_id,
            active_company_id=company_id,
            roles=member,
            issued_at=current_time,
            expires_at=expire_time,
        )
        self.session_store.create(session)

        return session

    def register(
        self,
        user_id: str,
        username: str,
        password: str,
        company_id: str,
        roles: list[str] | None = None,
    ) -> bool:
        """
        给新用户提供注册服务
        Args:
            user_id             : str 用户 ID
            username            : str 用户名
            password            : str 密码
            company_id          : str 公司 ID
            roles               : list[str] [职务, ...]

        Returns:
            True                : 注册成功
            False               : 注册失败 用户已存在或公司不存在
        """
        roles = roles or ["member"]

        exists = self.user_store.get_by_id(user_id)
        if exists is not None:
            return False

        if self.user_store.get_by_username(username) is not None:
            return False

        company = self.company_reg.get(company_id)
        if company is None:
            return False

        pwd_hash = PasswordService.hash_password(password)
        new_user = UserRecord(
            id=user_id,
            username=username,
            password_hash=pwd_hash,
            status="active",
        )

        self.user_store.save([new_user])

        self.membership_store.add_member(
            user_id=user_id,
            company_id=company_id,
            roles=roles,
        )

        return True

    def register_company(self, company_id: str, company_name: str) -> bool:
        """注册新公司
        Args:
            company_id      : str 公司 ID
            company_name    : str 公司名

        Returns:
            bool            : True 注册成功 / False 公司已存在
        """

        if self.company_reg.get(company_id) is not None:
            return False

        new_company = Company(
            id=company_id,
            name=company_name,
            status="active",
            created_at=datetime.now(UTC),
        )
        self.company_store.update(new_company)
        self.company_reg.reload()

        return True

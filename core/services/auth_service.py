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

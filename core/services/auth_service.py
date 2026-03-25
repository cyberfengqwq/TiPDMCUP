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

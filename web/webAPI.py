# web/webAPI.py

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.security import HTTPBearer

from core.services.auth_service import AuthService
from core.services.company_registry import CompanyRegistry
from core.stores.company_store import CompanyStore
from core.stores.membership_store import MembershipStore
from core.stores.session_store import SessionStore
from core.stores.user_store import UserStore

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="ticup", version="1.0.0")
bearer_scheme = HTTPBearer(auto_error=False)

USER_JSON = Path("./data/users/users.json")
COMPANY_JSON = Path("./data/users/companies.json")
MEMBERSHIP_JSON = Path("./data/users/memberships.json")
SESSION_JSON = Path("./data/users/sessions.json")


user_store = UserStore(USER_JSON)
company_store = CompanyStore(COMPANY_JSON)
membership_store = MembershipStore(MEMBERSHIP_JSON)
session_store = SessionStore(SESSION_JSON)

company_registry = CompanyRegistry(company_store)
company_registry.reload()

auth_service = AuthService()

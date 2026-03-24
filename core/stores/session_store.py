# core/stores/session_store.py

from datetime import datetime, timezone

from core.domain.models import SessionPrincipal
from core.stores.base_json_store import BaseJsonStore


class SessionStore(BaseJsonStore):
    def __init__(self, file_path: str) -> None:
        super().__init__(file_path)

        self.raw_sessions: list[dict] = []
        self.session_index: dict[str, dict] = {}

        self.reload_index()

    def reload_index(self) -> None:
        """重载 Json 文件并构建索引"""
        self.raw_sessions = self.read_json()
        self.session_index = {item["session_id"]: item for item in self.raw_sessions}

    def to_model(self, data: dict) -> SessionPrincipal:
        """将字典数据转化为实例对象
        Args:
            data            : dict 包含生命周期对象数据的字典

        Returns:
            SessionPrincipal: 生命周期对象
        """
        return SessionPrincipal(
            session_id=data["session_id"],
            user_id=data["user_id"],
            active_company_id=data["active_company_id"],
            roles=data.get("roles", []),
            issued_at=datetime.fromisoformat(data["issued_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
        )

    def get(self, session_id: str) -> SessionPrincipal | None:
        """通过 session_id 来获取生命周期内用户对象
        Args:
            session_id      : str 用户会话 id

        Returns:
            SessionPrincipal: 生命周期内实例化用户信息
        """
        data: dict | None = self.session_index.get(session_id)

        if data:
            return self.to_model(data)

    def create(self, session: SessionPrincipal) -> None:
        """登录时创建新会话
        Args:
            session: SessionPrincipal 要创建用户对话的实例对象

        """
        with self.__lock:
            session_dict: dict = {
                "session_id": session.session_id,
                "user_id": session.user_id,
                "active_company_id": session.active_company_id,
                "roles": session.roles,
                "issued_at": session.issued_at.isoformat(),
                "expires_at": session.expires_at.isoformat(),
            }

            existing: dict | None = self.session_index.get(session.session_id)
            if existing:
                existing.update(session_dict)
            else:
                self.raw_sessions.append(session_dict)
                self.session_index[session.session_id] = session_dict

            self.write_json_atomic(self.raw_sessions)

    def revoke(self, session_id: str) -> None:
        """用户退出登录时注销会话
        Args:
            session_id: str 生命周期结束的用户会话
        """

        with self.__lock:
            if session_id not in self.session_index:
                return

            self.session_index.pop(session_id, None)
            self.raw_sessions = [
                s for s in self.raw_sessions if s["session_id"] != session_id
            ]

            self.write_json_atomic(self.raw_sessions)

    def cleanup_expired(self) -> int:
        """清理过期会话
        Returns:
            int: 清除掉的过期会话数量
        """
        with self.__lock:
            current_time = datetime.now(timezone.utc)
            valid_session: list[dict] = []

            for session in self.raw_sessions:
                expires_at = datetime.fromisoformat(session["expires_at"])

                if expires_at > current_time:
                    valid_session.append(session)

            remove_count: int = len(self.raw_sessions) - len(valid_session)

            if remove_count > 0:
                self.raw_sessions = valid_session

                self.session_index = {
                    item["session_id"]: item for item in self.raw_sessions
                }

                self.write_json_atomic(self.raw_sessions)

            return remove_count

# core/stores/membership_store.py

from datetime import datetime

from core.domain.models import Membership
from core.stores.base_json_store import BaseJsonStore


class MembershipStore(BaseJsonStore):
    """
    用户与公司对应关系
    """

    def __init__(self, file_path: str) -> None:
        super().__init__(file_path)

        self.raw_data: list[dict] = []

        self.user_index: dict[str, list[dict]] = {}  # user_id -> [membership_dict, ...]
        self.company_index: dict[
            str, list[dict]
        ] = {}  # company_id -> [membership_dict, ...]
        self.pair_index: dict[
            tuple[str, str], dict
        ] = {}  # (user_id, company_id) -> membership_dict

        self.reload_index()

    def reload_index(self) -> None:
        """
        重载用户和公司所对应 json 文件
        """
        self.raw_data = self.read_json()

        user_idx = {}
        comp_idx = {}
        pair_idx = {}

        for item in self.raw_data:
            user_id = item["user_id"]
            company_id = item["company_id"]

            if user_id not in user_idx:
                user_idx[user_id] = []
            user_idx[user_id].append(item)

            if company_id not in comp_idx:
                comp_idx[company_id] = []
            comp_idx[company_id].append(item)

            pair_idx[(user_id, company_id)] = item

        self.user_index = user_idx
        self.company_index = comp_idx
        self.user_index = user_idx

    def to_model(self, data: dict) -> Membership:
        """用字典实例化对象
        Args:
            data        : dict 包含连接信息的字典

        Returns:
            Membership  : 实例对象
        """

        return Membership(
            user_id=data["user_id"],
            company_id=data["company_id"],
            roles=data.get("roles", []),
            joined_at=datetime.fromisoformat(data["joined_at"]),
        )

    def get_by_user(self, user_id: str) -> list[Membership]:
        """通过用户获取链接关系
        Args:
            user_id         : str 用户 id

        Returns:
            list[Membership]: 包含用户与公司链接关系的列表

        """
        items: list[dict] = self.user_index.get(user_id, [])
        return [self.to_model(item) for item in items]

    def get_role_in_company(self, user_id: str, company_id: str) -> list[str]:
        """获取用户在公司的职位
        Args:
            user_id     : str 用户 id
            company_id  : str 公司 id

        Returns:
            list[str]   : 用户在公司的职位
        """
        item: dict = self.pair_index.get((user_id, company_id), {})
        return item["roles"] if item else []

    def save(self, memberships: list[Membership]) -> None:
        """保存成员关系至 Json 文件

        Args:
            memberships: list[Membership] 包含成员与公司关系的列表
        """
        if not memberships:
            return

        with self._lock:
            for m in memberships:
                m_dict: dict = {
                    "user_id": m.user_id,
                    "company_id": m.company_id,
                    "roles": m.roles,
                    "joined_at": m.joined_at.isoformat(),
                }

                key: tuple[str, str] = (m.user_id, m.company_id)
                existing_item: dict | None = self.pair_index.get(key)

                if existing_item:
                    existing_item.update(m_dict)
                else:
                    self.raw_data.append(m_dict)

            self.write_json_atomic(self.raw_data)

            self.reload_index()

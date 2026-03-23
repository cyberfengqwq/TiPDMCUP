# core/stores/user_store.py

from core.domain.models import UserRecord
from core.stores.base_json_store import BaseJsonStore


class UserStore(BaseJsonStore):
    def __init__(self, file_path: str) -> None:
        super().__init__(file_path)

        self.username_index: dict[str, UserRecord] = {}
        self.id_index: dict[str, UserRecord] = {}

        self.reload_index()

    def reload_index(self) -> None:
        """重载用户名以及用户id索引"""

        raw_data = self.read_json()

        new_username_index: dict[str, UserRecord] = {}
        new_id_index: dict[str, UserRecord] = {}

        for item in raw_data:
            user = UserRecord(
                id=item["id"],
                username=item["username"],
                password_hash=item["password_hash"],
                status=item["status"],
            )
            new_username_index[item["username"]] = user
            new_id_index[item["id"]] = user

        self.username_index = new_username_index
        self.id_index = new_id_index

    def get_by_username(self, username: str) -> UserRecord | None:
        """通过用户名查找用户
        Args:
            username    : str 输入的用户名

        Returns:
            UserRecord  : 若成功找到该用户
            None        : 查询不到该用户

        """
        return self.username_index.get(username)

    def get_by_id(self, id: str) -> UserRecord | None:
        return self.id_index.get(id)

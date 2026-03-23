# core/stores/user_store.py

from core.domain.models import UserRecord
from core.stores.base_json_store import BaseJsonStore


class UserStore(BaseJsonStore):
    def __init__(self, file_path: str) -> None:
        super().__init__(file_path)

        self.users: list[dict[str, str]] = []
        self.username_dict: dict[str, dict[str, str]] = {}
        self.id_dict: dict[str, dict[str, str]] = {}

        self.reload_index()

    def reload_index(self) -> None:
        """重载用用户id"""

        raw_data = self.read_json()
        self.users = [item for item in raw_data]
        for user in self.users:
            self.username_dict[user["username"]] = user
            self.id_dict[user["id"]] = user


    def create_user(self, user_data: dict) -> UserRecord:
        """创建用户实例
        Args:
            user_data   : dict  包含用户信息的字典

        Returns:
            UserRecord  : 返回一个用户对象实例

        """
        return UserRecord(**user_data)


    def get_by_username(self, username: str) -> UserRecord | None:
        """通过 username 查找用户
        Args:
            username    : str 输入的username

        Returns:
            UserRecord  : 若成功找到该用户
            None        : 查询不到该用户

        """
        if self.username_dict.get(username) is None:
            return None

        return self.create_user(self.username_dict.get(username, {}))

    def get_by_id(self, id: str) -> UserRecord | None:
        """通过 id 查找用户
        Args:
            id          : str 输入的id

        Returns:
            UserRecord  : 若成功找到该用户
            None        : 查询不到该用户

        """
        if self.id_dict.get(id) is None:
            return None

        return self.create_user(self.id_dict.get(id, {}))


    def save_all(self, )

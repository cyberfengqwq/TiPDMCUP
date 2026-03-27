# core/stores/profile-store.py

from pathlib import Path
from typing import Any

from core.stores.base_json_store import BaseJsonStore

ROOT_DIR: Path = Path.cwd()
USER_DATA_DIR: Path = ROOT_DIR / "data" / "users"
USER_DATA_DIR.mkdir(exist_ok=True, parents=True)


class ProfileStore(BaseJsonStore):
    def __init__(self, user_id: str) -> None:
        self.user_id: str = user_id
        super().__init__(str(USER_DATA_DIR / self.user_id / "profile.json"))

    def get_profile_data(self) -> dict[str, Any]:
        """获取用户个人资料
        Returns:
            dict[str, Any]: 包含用户个人资料的字典
        """
        data = self.read_json()
        if not data:
            return {"summary": "该用户暂无历史偏好", "tags": [], "last_updated": None}

        return data

    def get_summary(self) -> str:
        """获取用户个人画像
        Returns:
            str: 用户个人画像描述
        """
        return self.get_profile_data().get("summary", "该用户暂无历史偏好")

    def update_profile(self, summary: str, tags: list[str], last_update: str) -> None:
        """更新用户个人资料
        Args:
            summary: str 用户个人画像
            tags: list[str] 用户标签
            last_update: str 最新更新时间
        """
        current_data: dict[str, Any] = self.get_profile_data()
        current_data["summary"] = summary
        if tags:
            current_data["tags"] = tags
        if last_update:
            current_data["last_updated"] = last_update

        self.write_json_atomic(current_data)

# core/stores/membership_store.py

from datetime import datetime, timezone
from pathlib import Path

from core.stores.base_json_store import BaseJsonStore


class MembershipStore(BaseJsonStore):
    """
    用户与公司对应关系
    """

    def __init__(self, file_path: str | Path) -> None:
        super().__init__(file_path)
        self.raw_data: list[dict] = []
        self.pair_index: dict[tuple[str, str], dict] = {}
        self.reload_index()

    def reload_index(self) -> None:
        self.raw_data = self.read_json()
        self.pair_index = {
            (item["user_id"], item["company_id"]): item
            for item in self.raw_data
        }

    def get_role_in_company(self, user_id: str, company_id: str) -> list[str] | None:
        item = self.pair_index.get((user_id, company_id), {})
        return item["roles"] if item else None

    def add_member(self, user_id: str, company_id: str, roles: list[str]) -> None:
        with self._lock:
            raw: list[dict] = self.read_json()
            now_iso = datetime.now(timezone.utc).isoformat()

            for item in raw:
                if item.get("user_id") == user_id and item.get("company_id") == company_id:
                    item["roles"] = roles
                    if not item.get("joined_at"):
                        item["joined_at"] = now_iso
                    self.write_json_atomic(raw)
                    self.reload_index()
                    return

            raw.append(
                {
                    "user_id": user_id,
                    "company_id": company_id,
                    "roles": roles,
                    "joined_at": now_iso,
                }
            )
            self.write_json_atomic(raw)
            self.reload_index()

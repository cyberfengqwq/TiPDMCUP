# core/stores/chat_store.py

from pathlib import Path

from core.stores.base_json_store import BaseJsonStore

ROOT_DIR: Path = Path.cwd().parent.parent


class ChatStore(BaseJsonStore):
    def __init__(self, chat_id: str) -> None:
        super().__init__(str(ROOT_DIR / f"{chat_id}.json"))

    def get_history(self) -> list[dict]:
        """读取历史会话
        Returns:
            list[dict] : 包含历史会话信息的列表

        """
        data: list[dict] = self.read_json()
        return data if data else []

    def append_message(self, messages: list[dict]) -> None:
        """追加新的消息
        Args:
            messages: list[dict] 包含新增消息的列表
        """
        history: list[dict] = self.get_history()
        history += messages
        self.write_json_atomic(history)

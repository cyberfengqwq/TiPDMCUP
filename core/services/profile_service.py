# core/services/profile_service.py

import logging

from core.services.llm_service import LLM
from core.stores.chat_store import ChatStore
from core.stores.profile_store import ProfileStore

logger = logging.getLogger(__name__)


class ProfileService:
    def __init__(self, user_id: str, chat_id: str) -> None:
        self.user_id = user_id
        self.chat_id = chat_id

        self.llm = LLM()
        self.profile_store = ProfileStore(user_id)
        self.chat_store = ChatStore(chat_id)

    def get_current_profile_summary(self) -> str:
        """获取用户个人画像
        Returns:
            str: 用户个人画像描述
        """
        return self.profile_store.get_summary()

    def sum_and_update_profile(self) -> str | None:
        old_sum: str = self.profile_store.get_summary()
        chat_history: list[dict] = self.chat_store.get_history()

        if not chat_history or len(chat_history) < 2:
            logger.info("无历史对话记录或对话次数太少，跳过用户画像总结")
            return

        recent_chats = chat_history[-10:]
        chat_text = "\n".join(
            [
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
                for msg in recent_chats
            ]
        )

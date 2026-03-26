# core/services/profile_service.py

import logging

from core.rag.memery_retrieval import UserProfileRetrieval
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

        prompt = f"""
        你是一个AI记忆提取引擎。请分析以下的最新对话记录，提取出用户在财务分析、数据查询上的「行为偏好」或「关注点」。
        如果对话中没有明显的偏好，请直接回复"无"。

        如果有，请用条目化的列表输出，每一条必须是一个完整的陈述句，包含具体内容。
        例如：
        - 用户经常关注新能源汽车行业的财报。
        - 用户偏好使用环比数据而不是同比数据进行分析。

        【最新对话记录】
        {chat_text}
        """

        try:
            response = self.llm.chat(prompt).strip()
            if response == "无" or "无偏好" in response:
                return

            facts = []
            for line in response.split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    facts.append(line[2:].strip())

            if facts:
                memory_retriever = UserProfileRetrieval(user_id=self.user_id)
                memory_retriever.add_preferences(facts)
                logger.info(f"提取并保存了 {len(facts)} 条记忆向量到 Faiss")

        except Exception as e:
            logger.error(f"提取画像记忆时发生错误: {e}")

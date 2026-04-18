# core/services/profile_service.py

import logging
from datetime import datetime, timezone

from core.rag.memory_retrieval import UserProfileRetrieval
from core.services.vllm_service import LLM
from core.stores.chat_store import ChatStore
from core.stores.profile_store import ProfileStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ProfileService:
    def __init__(self, user_id: str, chat_id: str, llm: LLM) -> None:
        self.user_id = user_id
        self.chat_id = chat_id
        self.llm = llm
        self.profile_store = ProfileStore(user_id)
        self.chat_store = ChatStore(chat_id)

    def get_current_profile_summary(self) -> str:
        return self.profile_store.get_summary()

    def sum_and_update_profile(self) -> None:
        chat_history: list[dict] = self.chat_store.get_history()
        if not chat_history or len(chat_history) < 2:
            logger.info("对话轮次太少，跳过画像更新")
            return

        recent_chats = chat_history[-10:]
        chat_text = "\n".join(
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in recent_chats
        )

        # ── Step1: 从本轮对话提取新偏好条目 ─────────────────────────────
        extract_prompt = f"""
你是一个AI记忆提取引擎。请分析以下对话记录，提取用户在财务分析、数据查询上的「行为偏好」或「关注点」。
如果没有明显偏好，直接回复"无"。
有的话用条目列表输出，每条必须是完整陈述句，包含具体内容。
例如：
- 用户经常关注新能源汽车行业的财报。
- 用户偏好使用环比数据进行分析。

【对话记录】
{chat_text}
"""
        try:
            raw = self.llm.chat(extract_prompt).strip()
        except Exception as e:
            logger.error(f"[ProfileService] 提取偏好失败: {e}")
            return

        if raw == "无" or "无偏好" in raw:
            logger.info("[ProfileService] 本轮无新偏好")
            return

        new_facts = [
            line[2:].strip()
            for line in raw.split("\n")
            if line.strip().startswith("- ")
        ]
        if not new_facts:
            return

        # ── Step2: 写入 FAISS 向量库 ─────────────────────────────────────
        try:
            memory_retriever = UserProfileRetrieval(user_id=self.user_id)
            memory_retriever.add_preferences(new_facts)
            logger.info(f"[ProfileService] 写入 {len(new_facts)} 条偏好向量")
        except Exception as e:
            logger.error(f"[ProfileService] FAISS写入失败: {e}")

        # ── Step3: 滚动更新 ProfileStore 文字汇总 ────────────────────────
        old_summary = self.profile_store.get_summary()
        has_old = old_summary and old_summary != "该用户暂无历史偏好"

        if has_old:
            merge_prompt = f"""
你是一个用户画像维护引擎。请将【旧画像】和【新发现的偏好条目】合并，生成一段简洁的用户画像描述（100字以内）。
去除重复内容，保留最有价值的信息。直接输出描述文字，不要加任何前缀。

【旧画像】
{old_summary}

【新偏好条目】
{chr(10).join(f"- {f}" for f in new_facts)}
"""
        else:
            merge_prompt = f"""
请根据以下用户偏好条目，生成一段简洁的用户画像描述（100字以内）。
直接输出描述文字，不要加任何前缀。

【偏好条目】
{chr(10).join(f"- {f}" for f in new_facts)}
"""

        try:
            new_summary = self.llm.chat(merge_prompt).strip()
            now = datetime.now(timezone.utc).isoformat()
            self.profile_store.update_profile(
                summary=new_summary,
                tags=new_facts[:5],
                last_update=now,
            )
            logger.info(f"[ProfileService] 画像汇总已更新: {new_summary[:60]}...")
        except Exception as e:
            logger.error(f"[ProfileService] 画像汇总更新失败: {e}")

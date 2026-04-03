# core/agent/agent_manager.py

import logging
import threading
from typing import Dict, Optional

from core.agent.pipeline import Agent

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Agent 实例管理器
    - 管理所有活跃的 Agent 实例
    - 每个 chat_id 对应一个 Agent 实例
    - 支持线程安全地创建、获取、销毁 Agent
    """

    _instance: Optional["AgentManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "AgentManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._agents: Dict[str, Agent] = {}
                    cls._instance._agents_lock = threading.Lock()
        return cls._instance

    def get_or_create(self, user_id: str, company_id: str, chat_id: str) -> Agent:
        """
        获取或创建 Agent 实例
        如果 chat_id 对应的 Agent 已存在，直接返回
        否则创建新的 Agent 实例

        Args:
            user_id: 用户ID
            company_id: 公司ID
            chat_id: 对话窗口ID

        Returns:
            Agent: Agent 实例
        """
        with self._agents_lock:
            if chat_id not in self._agents:
                logger.info(
                    f"[AgentManager] 创建新 Agent: user_id={user_id}, company_id={company_id}, chat_id={chat_id}"
                )
                self._agents[chat_id] = Agent(
                    user_id=user_id,
                    company_id=company_id,
                    chat_id=chat_id,
                )
            else:
                logger.info(f"[AgentManager] 复用已有 Agent: chat_id={chat_id}")

            return self._agents[chat_id]

    def destroy(self, chat_id: str) -> None:
        """
        销毁 Agent 实例
        在对话结束时调用，保存向量库并清理资源

        Args:
            chat_id: 对话窗口ID
        """
        with self._agents_lock:
            agent = self._agents.pop(chat_id, None)
            if agent:
                logger.info(f"[AgentManager] 销毁 Agent: chat_id={chat_id}")
                agent.rag.user_retrieval.save_index()
                logger.info(f"[AgentManager] 已保存用户向量库: chat_id={chat_id}")

    def get(self, chat_id: str) -> Optional[Agent]:
        """
        获取 Agent 实例

        Args:
            chat_id: 对话窗口ID

        Returns:
            Optional[Agent]: Agent 实例，如果不存在则返回 None
        """
        with self._agents_lock:
            return self._agents.get(chat_id)

    def has(self, chat_id: str) -> bool:
        """
        检查 Agent 实例是否存在

        Args:
            chat_id: 对话窗口ID

        Returns:
            bool: 是否存在
        """
        with self._agents_lock:
            return chat_id in self._agents

    def clear_all(self) -> None:
        """
        清理所有 Agent 实例
        在服务关闭时调用
        """
        with self._agents_lock:
            for chat_id, agent in self._agents.items():
                logger.info(f"[AgentManager] 保存并清理 Agent: chat_id={chat_id}")
                agent.rag.user_retrieval.save_index()
            self._agents.clear()
            logger.info("[AgentManager] 已清理所有 Agent 实例")


agent_manager = AgentManager()

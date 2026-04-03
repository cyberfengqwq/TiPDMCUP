# core/agent/agent_manager.py

import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional, Set

from core.agent.pipeline import Agent

logger = logging.getLogger(__name__)


@dataclass
class AgentEntry:
    """Agent 条目，包含 Agent 实例和元数据"""

    agent: Agent
    user_id: str
    company_id: str
    chat_id: str
    last_active_time: float  # 最后活跃时间戳


class AgentManager:
    """
    Agent 实例管理器
    - 管理所有活跃的 Agent 实例
    - 每个 chat_id 对应一个 Agent 实例
    - 支持线程安全地创建、获取、销毁 Agent
    - 支持超时自动保存和清理
    """

    _instance: Optional["AgentManager"] = None
    _lock = threading.Lock()

    # 超时配置（单位：秒）
    DEFAULT_TIMEOUT = 30 * 60  # 30 分钟无活动自动保存
    CLEANUP_INTERVAL = 5 * 60  # 每 5 分钟检查一次

    def __new__(cls) -> "AgentManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._agents: Dict[str, AgentEntry] = {}
                    cls._instance._user_chats: Dict[str, Set[str]] = {}  # user_id -> set of chat_ids
                    cls._instance._agents_lock = threading.Lock()
                    cls._instance._cleanup_thread: Optional[threading.Thread] = None
                    cls._instance._running = False
                    cls._instance._start_cleanup_thread()
        return cls._instance

    def _start_cleanup_thread(self) -> None:
        """启动后台清理线程"""
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._running = True
            self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
            self._cleanup_thread.start()
            logger.info("[AgentManager] 后台清理线程已启动")

    def _cleanup_loop(self) -> None:
        """后台清理循环"""
        while self._running:
            time.sleep(self.CLEANUP_INTERVAL)
            self._cleanup_expired_agents()

    def _cleanup_expired_agents(self) -> None:
        """清理过期的 Agent"""
        current_time = time.time()
        expired_chats: list[str] = []

        with self._agents_lock:
            for chat_id, entry in self._agents.items():
                if current_time - entry.last_active_time > self.DEFAULT_TIMEOUT:
                    expired_chats.append(chat_id)

        for chat_id in expired_chats:
            logger.info(f"[AgentManager] Agent 超时，自动保存: chat_id={chat_id}")
            self.destroy(chat_id)

    def _update_last_active_time(self, chat_id: str) -> None:
        """更新 Agent 的最后活跃时间"""
        with self._agents_lock:
            if chat_id in self._agents:
                self._agents[chat_id].last_active_time = time.time()

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
                agent = Agent(
                    user_id=user_id,
                    company_id=company_id,
                    chat_id=chat_id,
                )
                self._agents[chat_id] = AgentEntry(
                    agent=agent,
                    user_id=user_id,
                    company_id=company_id,
                    chat_id=chat_id,
                    last_active_time=time.time(),
                )

                # 记录用户与 chat_id 的映射
                if user_id not in self._user_chats:
                    self._user_chats[user_id] = set()
                self._user_chats[user_id].add(chat_id)
            else:
                logger.info(f"[AgentManager] 复用已有 Agent: chat_id={chat_id}")
                self._agents[chat_id].last_active_time = time.time()

            return self._agents[chat_id].agent

    def destroy(self, chat_id: str) -> None:
        """
        销毁 Agent 实例
        在对话结束时调用，保存向量库并清理资源

        Args:
            chat_id: 对话窗口ID
        """
        with self._agents_lock:
            entry = self._agents.pop(chat_id, None)
            if entry:
                logger.info(f"[AgentManager] 销毁 Agent: chat_id={chat_id}")
                entry.agent.rag.user_retrieval.save_index()
                logger.info(f"[AgentManager] 已保存用户向量库: chat_id={chat_id}")

                # 从用户映射中移除
                if entry.user_id in self._user_chats:
                    self._user_chats[entry.user_id].discard(chat_id)
                    if not self._user_chats[entry.user_id]:
                        del self._user_chats[entry.user_id]

    def destroy_user_agents(self, user_id: str) -> None:
        """
        销毁用户的所有 Agent 实例
        在用户退出登录时调用

        Args:
            user_id: 用户ID
        """
        with self._agents_lock:
            chat_ids = self._user_chats.get(user_id, set()).copy()

        for chat_id in chat_ids:
            logger.info(f"[AgentManager] 用户退出，销毁 Agent: user_id={user_id}, chat_id={chat_id}")
            self.destroy(chat_id)

    def get(self, chat_id: str) -> Optional[Agent]:
        """
        获取 Agent 实例

        Args:
            chat_id: 对话窗口ID

        Returns:
            Optional[Agent]: Agent 实例，如果不存在则返回 None
        """
        with self._agents_lock:
            entry = self._agents.get(chat_id)
            if entry:
                entry.last_active_time = time.time()
                return entry.agent
            return None

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

    def save_user_indices(self, user_id: str) -> None:
        """
        保存用户所有 Agent 的索引（不销毁）

        Args:
            user_id: 用户ID
        """
        with self._agents_lock:
            chat_ids = self._user_chats.get(user_id, set()).copy()

        for chat_id in chat_ids:
            with self._agents_lock:
                entry = self._agents.get(chat_id)
                if entry:
                    logger.info(f"[AgentManager] 保存用户向量库: user_id={user_id}, chat_id={chat_id}")
                    entry.agent.rag.user_retrieval.save_index()

    def clear_all(self) -> None:
        """
        清理所有 Agent 实例
        在服务关闭时调用
        """
        self._running = False
        with self._agents_lock:
            for chat_id, entry in self._agents.items():
                logger.info(f"[AgentManager] 保存并清理 Agent: chat_id={chat_id}")
                entry.agent.rag.user_retrieval.save_index()
            self._agents.clear()
            self._user_chats.clear()
            logger.info("[AgentManager] 已清理所有 Agent 实例")

    def get_active_count(self) -> int:
        """
        获取活跃 Agent 数量

        Returns:
            int: 活跃 Agent 数量
        """
        with self._agents_lock:
            return len(self._agents)

    def get_user_active_count(self, user_id: str) -> int:
        """
        获取用户的活跃 Agent 数量

        Args:
            user_id: 用户ID

        Returns:
            int: 用户的活跃 Agent 数量
        """
        with self._agents_lock:
            return len(self._user_chats.get(user_id, set()))


agent_manager = AgentManager()

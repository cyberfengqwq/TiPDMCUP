# core/agent/agent_manager.py

import logging
import threading
import time
from dataclasses import dataclass

from core.agent.pipeline import Agent
from core.services.vllm_service import LLM

logger = logging.getLogger(__name__)

MODEL_PATH = "/home/qwq/models/Qwen2.5-7B-Instruct"


@dataclass
class AgentEntry:
    agent: Agent
    user_id: str
    company_id: str
    chat_id: str
    last_active_time: float


class AgentManager:
    _instance: "AgentManager | None" = None
    _lock = threading.Lock()

    DEFAULT_TIMEOUT = 30 * 60
    CLEANUP_INTERVAL = 5 * 60

    def __new__(cls) -> "AgentManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._agents: dict[str, AgentEntry] = {}
        self._user_chats: dict[str, set[str]] = {}
        self._agents_lock = threading.Lock()
        self._cleanup_thread: threading.Thread | None = None
        self._running: bool = False
        self._initialized: bool = True

        # LLM单例，所有Agent共享
        self._llm: LLM = LLM(
            _modelpath=MODEL_PATH,
            _temperature=0.7,
            _top_p=0.8,
            _max_tokens=512,
            _gpu_memory_utilization=0.63,
        )
        self._llm.load_model()
        logger.info("[AgentManager] LLM加载完成")

        self._start_cleanup_thread()

    def _start_cleanup_thread(self) -> None:
        if self._cleanup_thread is None or not self._cleanup_thread.is_alive():
            self._running = True
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_loop, daemon=True
            )
            self._cleanup_thread.start()

    def _cleanup_loop(self) -> None:
        while self._running:
            time.sleep(self.CLEANUP_INTERVAL)
            self._cleanup_expired_agents()

    def _cleanup_expired_agents(self) -> None:
        current_time = time.time()
        expired = []
        with self._agents_lock:
            for chat_id, entry in self._agents.items():
                if current_time - entry.last_active_time > self.DEFAULT_TIMEOUT:
                    expired.append(chat_id)
        for chat_id in expired:
            self.destroy(chat_id)

    def get_or_create(self, user_id: str, company_id: str, chat_id: str) -> Agent:
        with self._agents_lock:
            if chat_id not in self._agents:
                agent = Agent(
                    user_id=user_id,
                    company_id=company_id,
                    chat_id=chat_id,
                    llm=self._llm,  # 注入共享LLM
                )
                self._agents[chat_id] = AgentEntry(
                    agent=agent,
                    user_id=user_id,
                    company_id=company_id,
                    chat_id=chat_id,
                    last_active_time=time.time(),
                )
                if user_id not in self._user_chats:
                    self._user_chats[user_id] = set()
                self._user_chats[user_id].add(chat_id)
                logger.info(f"[AgentManager] 创建Agent: chat_id={chat_id}")
            else:
                self._agents[chat_id].last_active_time = time.time()

            return self._agents[chat_id].agent

    def destroy(self, chat_id: str) -> None:
        with self._agents_lock:
            entry = self._agents.pop(chat_id, None)
            if entry:
                entry.agent.rag.user_retrieval.save_index()
                if entry.user_id in self._user_chats:
                    self._user_chats[entry.user_id].discard(chat_id)
                    if not self._user_chats[entry.user_id]:
                        del self._user_chats[entry.user_id]
                logger.info(f"[AgentManager] 销毁Agent: chat_id={chat_id}")

    def destroy_user_agents(self, user_id: str) -> None:
        with self._agents_lock:
            chat_ids = self._user_chats.get(user_id, set()).copy()
        for chat_id in chat_ids:
            self.destroy(chat_id)

    def get(self, chat_id: str) -> Agent | None:
        with self._agents_lock:
            entry = self._agents.get(chat_id)
            if entry:
                entry.last_active_time = time.time()
                return entry.agent
            return None

    def has(self, chat_id: str) -> bool:
        with self._agents_lock:
            return chat_id in self._agents

    def save_user_indices(self, user_id: str) -> None:
        with self._agents_lock:
            chat_ids = self._user_chats.get(user_id, set()).copy()
        for chat_id in chat_ids:
            with self._agents_lock:
                entry = self._agents.get(chat_id)
                if entry:
                    entry.agent.rag.user_retrieval.save_index()

    def clear_all(self) -> None:
        self._running = False
        with self._agents_lock:
            for entry in self._agents.values():
                entry.agent.rag.user_retrieval.save_index()
            self._agents.clear()
            self._user_chats.clear()

    def get_active_count(self) -> int:
        with self._agents_lock:
            return len(self._agents)

    def get_user_active_count(self, user_id: str) -> int:
        with self._agents_lock:
            return len(self._user_chats.get(user_id, set()))


agent_manager = AgentManager()

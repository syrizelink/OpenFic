"""Agent 运行时消息持久化层公共 API。"""

from app.agent_runtime.persistence import compaction_repo, repo
from app.agent_runtime.persistence.errors import (
    PersistenceError,
    PersistenceLoadError,
    PersistenceWriteError,
)
from app.agent_runtime.persistence.loader import load_history
from app.agent_runtime.persistence.persister import MessagePersister
from app.agent_runtime.persistence.types import PersistedMessage
from app.agent_runtime.persistence.compaction_types import PersistedCompaction

__all__ = [
    "MessagePersister",
    "load_history",
    "PersistedMessage",
    "PersistedCompaction",
    "PersistenceError",
    "PersistenceWriteError",
    "PersistenceLoadError",
    "compaction_repo",
    "repo",
]

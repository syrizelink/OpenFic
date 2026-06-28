class PersistenceError(Exception):
    """持久化层基类异常。"""


class PersistenceWriteError(PersistenceError):
    """写库失败：MessagePersister.handle / finalize / mark_user_sent / repo 写入。"""


class PersistenceLoadError(PersistenceError):
    """读库失败：load_history / repo 查询。"""

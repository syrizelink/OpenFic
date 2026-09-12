class PersistenceError(Exception):
    """Exception dasar untuk lapisan persistensi."""


class PersistenceWriteError(PersistenceError):
    """Penulisan ke basis data gagal: MessagePersister.handle / finalize /
    mark_user_sent / penulisan repo."""


class PersistenceLoadError(PersistenceError):
    """Pembacaan basis data gagal: load_history / kueri repo."""

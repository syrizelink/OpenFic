from unittest.mock import AsyncMock, patch

import pytest

from app.core.editor_content_limits import EditorContentLimitError
from app.storage.services.world_info_entry_service import (
    WorldInfoImportEntry,
    import_entries,
)


@pytest.mark.asyncio
async def test_overwrite_import_validates_all_entries_before_deleting_existing_entries() -> None:
    session = AsyncMock()
    entries = [
        WorldInfoImportEntry(
            uid=1,
            name="超限条目",
            content="\n".join("内容" for _ in range(2001)),
            is_enabled=True,
            order=1,
        )
    ]

    with (
        patch(
            "app.storage.services.world_info_entry_service.get_world_info",
            AsyncMock(),
        ),
        patch(
            "app.storage.services.world_info_entry_service.world_info_entry_repo.delete_by_world_info",
            AsyncMock(),
        ) as delete_entries,
    ):
        with pytest.raises(EditorContentLimitError, match="内容超出限制"):
            await import_entries(session, "world-1", entries, mode="overwrite")

    delete_entries.assert_not_awaited()


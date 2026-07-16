# -*- coding: utf-8 -*-
"""
Settings API 测试。
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import EncryptionService
from app.models.repos import model_provider_repo, model_repo
from app.audit.queue import audit_queue
from app.storage.models.llm_audit_log import LLMAuditLog
from app.storage.models.retrieval_index import RetrievalIndex
from app.storage.models.retrieval_chapter_index_state import RetrievalChapterIndexState
from app.storage.repos import setting_repo


EXPECTED_AGENT_TOOL_PERMISSIONS = [
    {"tool_name": "ask_user", "mode": "allow"},
    {"tool_name": "create_character", "mode": "ask"},
    {"tool_name": "create_plan", "mode": "ask"},
    {"tool_name": "create_volume", "mode": "ask"},
    {"tool_name": "create_world_entry", "mode": "ask"},
    {"tool_name": "delete_chapter", "mode": "ask"},
    {"tool_name": "delete_character", "mode": "ask"},
    {"tool_name": "delete_volume", "mode": "ask"},
    {"tool_name": "delete_world_entry", "mode": "ask"},
    {"tool_name": "edit_chapter", "mode": "ask"},
    {"tool_name": "edit_character", "mode": "ask"},
    {"tool_name": "edit_volume", "mode": "ask"},
    {"tool_name": "edit_world_entry", "mode": "ask"},
    {"tool_name": "get_plan", "mode": "allow"},
    {"tool_name": "list_chapters", "mode": "allow"},
    {"tool_name": "list_characters", "mode": "allow"},
    {"tool_name": "list_plan", "mode": "allow"},
    {"tool_name": "list_volumes", "mode": "allow"},
    {"tool_name": "list_world_entries", "mode": "allow"},
    {"tool_name": "move_chapter_to_volume", "mode": "ask"},
    {"tool_name": "read_chapter", "mode": "allow"},
    {"tool_name": "read_chapter_summaries", "mode": "allow"},
    {"tool_name": "read_character", "mode": "allow"},
    {"tool_name": "read_range_summaries", "mode": "allow"},
    {"tool_name": "read_world_entry", "mode": "allow"},
    {"tool_name": "search_chapters", "mode": "allow"},
    {"tool_name": "update_index", "mode": "allow"},
    {"tool_name": "update_plan", "mode": "ask"},
    {"tool_name": "write_chapter", "mode": "ask"},
]


def _expected_agent_tool_permissions(**mode_overrides: str) -> list[dict[str, str]]:
    return [
        {
            "tool_name": item["tool_name"],
            "mode": mode_overrides.get(item["tool_name"], item["mode"]),
        }
        for item in EXPECTED_AGENT_TOOL_PERMISSIONS
    ]


@pytest.mark.asyncio
async def test_get_settings_default(client: AsyncClient) -> None:
    """测试获取默认设置。"""
    response = await client.get("/api/v1/settings")
    assert response.status_code == 200
    data = response.json()
    # 验证默认值
    assert data["language"] == "zh-CN"
    assert data["theme"] == "light"
    assert data["font_family"] == "SourceHanSerifCN-VF"
    assert data["code_font_family"] == "JetBrainsMapleMono"
    assert data["default_model"] == ""
    assert data["light_model"] == ""
    assert data["default_embedding_model"] == ""
    assert data["index_mode"] == "off"
    assert data["index_enabled_projects"] == []
    assert data["index_chunk_size"] == 800
    assert data["index_chunk_overlap"] == 100
    assert data["index_auto_strategy"] == "off"
    assert data["index_rerank_enabled"] is False
    assert data["default_rerank_model"] == ""
    assert data["agent_bypass_tool_approval"] is False
    assert data["agent_tool_permissions"] == EXPECTED_AGENT_TOOL_PERMISSIONS
    assert data["audit_persist_details"] is False


@pytest.mark.asyncio
async def test_update_settings_language(client: AsyncClient) -> None:
    """测试更新语言设置。"""
    response = await client.put(
        "/api/v1/settings",
        json={"language": "en"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "en"
    # 其他设置保持默认值
    assert data["theme"] == "light"
    assert data["font_family"] == "SourceHanSerifCN-VF"


@pytest.mark.asyncio
async def test_update_settings_theme(client: AsyncClient) -> None:
    """测试更新主题设置。"""
    response = await client.put(
        "/api/v1/settings",
        json={"theme": "dark"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["theme"] == "dark"


@pytest.mark.asyncio
async def test_update_settings_font(client: AsyncClient) -> None:
    """测试更新字体设置。"""
    response = await client.put(
        "/api/v1/settings",
        json={"font_family": "SourceHanSansCN-VF"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["font_family"] == "SourceHanSansCN-VF"


@pytest.mark.asyncio
async def test_update_settings_multiple(client: AsyncClient) -> None:
    """测试同时更新多个设置。"""
    response = await client.put(
        "/api/v1/settings",
        json={
            "language": "en",
            "theme": "dark",
            "font_family": "SourceHanSansCN-VF",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "en"
    assert data["theme"] == "dark"
    assert data["font_family"] == "SourceHanSansCN-VF"


@pytest.mark.asyncio
async def test_update_settings_persistence(client: AsyncClient) -> None:
    """测试设置持久化。"""
    # 更新设置
    await client.put(
        "/api/v1/settings",
        json={"language": "en", "theme": "dark"},
    )

    # 再次获取，验证持久化
    response = await client.get("/api/v1/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "en"
    assert data["theme"] == "dark"


@pytest.mark.asyncio
async def test_update_settings_partial(client: AsyncClient) -> None:
    """测试部分更新设置（只更新部分字段）。"""
    # 先设置初始值
    await client.put(
        "/api/v1/settings",
        json={"language": "en", "theme": "dark", "font_family": "SourceHanSansCN-VF"},
    )

    # 只更新语言
    response = await client.put(
        "/api/v1/settings",
        json={"language": "zh-CN"},
    )
    assert response.status_code == 200
    data = response.json()
    # 语言被更新
    assert data["language"] == "zh-CN"
    # 其他设置保持不变
    assert data["theme"] == "dark"
    assert data["font_family"] == "SourceHanSansCN-VF"


@pytest.mark.asyncio
async def test_update_settings_default_model(client: AsyncClient) -> None:
    """测试更新默认模型设置。"""
    response = await client.put(
        "/api/v1/settings",
        json={"default_model": "model-123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["default_model"] == "model-123"
    assert data["light_model"] == ""


@pytest.mark.asyncio
async def test_update_settings_light_model(client: AsyncClient) -> None:
    """测试更新轻量模型设置。"""
    response = await client.put(
        "/api/v1/settings",
        json={"light_model": "model-456"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["light_model"] == "model-456"


@pytest.mark.asyncio
async def test_update_settings_model_persistence(client: AsyncClient) -> None:
    """测试模型设置持久化。"""
    await client.put(
        "/api/v1/settings",
        json={"default_model": "model-123", "light_model": "model-456"},
    )

    response = await client.get("/api/v1/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["default_model"] == "model-123"
    assert data["light_model"] == "model-456"


@pytest.mark.asyncio
async def test_patch_settings_default_embedding_model(client: AsyncClient) -> None:
    response = await client.patch(
        "/api/v1/settings",
        json={"default_embedding_model": "embedding-model-1"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["default_embedding_model"] == "embedding-model-1"

    follow_up = await client.get("/api/v1/settings")
    assert follow_up.status_code == 200
    assert follow_up.json()["default_embedding_model"] == "embedding-model-1"


@pytest.mark.asyncio
async def test_update_rerank_settings_persistence(client: AsyncClient) -> None:
    """rerank 开关与模型选择应可持久化。"""
    response = await client.put(
        "/api/v1/settings",
        json={"index_rerank_enabled": True, "default_rerank_model": "rerank-1"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["index_rerank_enabled"] is True
    assert data["default_rerank_model"] == "rerank-1"

    follow_up = await client.get("/api/v1/settings")
    assert follow_up.json()["index_rerank_enabled"] is True
    assert follow_up.json()["default_rerank_model"] == "rerank-1"


async def _create_embedding_model(session: AsyncSession, model_id: str):
    from app.settings import settings

    encryption_service = EncryptionService(settings.encryption_key)
    provider = await model_provider_repo.create(
        session=session,
        name=f"Provider {model_id}",
        url="https://api.test.com",
        api_key_encrypted=encryption_service.encrypt("test-key"),
        provider_type="openai",
    )
    return await model_repo.create(
        session=session,
        name=f"Embedding {model_id}",
        provider_id=provider.id,
        model_id=model_id,
        task_type="embedding",
        dimensions=3,
    )


@pytest.mark.asyncio
async def test_changing_default_embedding_model_marks_retrieval_indexes_for_rebuild(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    old_model = await _create_embedding_model(session, "embed-old")
    new_model = await _create_embedding_model(session, "embed-new")
    retrieval_index = RetrievalIndex(
        index_key="chapters:project-1",
        table_name="chapters_project_1",
        status="ready",
        embedding_model_ref_id=old_model.id,
        embedding_model_id_snapshot=old_model.model_id,
        embedding_dimensions_snapshot=3,
    )
    chapter_state = RetrievalChapterIndexState(
        project_id="project-1",
        chapter_id="chapter-1",
        index_key="chapters:project-1",
        status="ready",
        source_hash="old-hash",
        embedding_model_ref_id=old_model.id,
        chunk_count=2,
    )
    session.add(retrieval_index)
    session.add(chapter_state)
    await setting_repo.upsert(session, "default_embedding_model", old_model.id)
    await session.commit()

    response = await client.patch(
        "/api/v1/settings",
        json={"default_embedding_model": new_model.id},
    )

    assert response.status_code == 200
    await session.refresh(retrieval_index)
    await session.refresh(chapter_state)
    assert response.json()["default_embedding_model"] == new_model.id
    assert retrieval_index.status == "needs_rebuild"
    assert chapter_state.status == "needs_rebuild"

    rows = (
        await session.execute(select(RetrievalChapterIndexState))
    ).scalars().all()
    assert [row.status for row in rows] == ["needs_rebuild"]


@pytest.mark.asyncio
async def test_update_settings_agent_bypass_tool_approval(client: AsyncClient) -> None:
    """测试更新工具审批放行设置。"""
    response = await client.put(
        "/api/v1/settings",
        json={"agent_bypass_tool_approval": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["agent_bypass_tool_approval"] is True

    follow_up = await client.get("/api/v1/settings")
    assert follow_up.status_code == 200
    assert follow_up.json()["agent_bypass_tool_approval"] is True


@pytest.mark.asyncio
async def test_update_settings_audit_persist_details(client: AsyncClient) -> None:
    """审计详情记录开关应可持久化。"""
    response = await client.put(
        "/api/v1/settings",
        json={"audit_persist_details": False},
    )

    assert response.status_code == 200
    assert response.json()["audit_persist_details"] is False

    follow_up = await client.get("/api/v1/settings")
    assert follow_up.status_code == 200
    assert follow_up.json()["audit_persist_details"] is False

    await client.put(
        "/api/v1/settings",
        json={"audit_persist_details": True},
    )


@pytest.mark.asyncio
async def test_audit_persistence_memory_state_does_not_change_when_settings_write_fails(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """设置写入失败时，内存中的审计开关必须保持原值。"""
    audit_queue.set_persist_details(True)

    async def fail_bulk_upsert(*_args, **_kwargs):
        raise RuntimeError("settings write failed")

    monkeypatch.setattr("app.api.routers.settings.setting_repo.bulk_upsert", fail_bulk_upsert)

    with pytest.raises(RuntimeError, match="settings write failed"):
        await client.put(
            "/api/v1/settings",
            json={"audit_persist_details": False},
        )

    assert audit_queue._persist_details is True


@pytest.mark.asyncio
async def test_audit_details_storage_and_clear_preserve_metrics(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """清空详情不应删除调用统计，并应返回 UTF-8 字节占用。"""
    audit_log = LLMAuditLog(
        id="audit-detail-1",
        project_id="project-1",
        operation="writer",
        model_id="model-1",
        status="success",
        request_messages='[{"content":"输入"}]',
        tool_references='[{"name":"tool"}]',
        response_content="输出",
        response_tool_calls='[{"name":"tool"}]',
        tool_call_results='[{"result":"完成"}]',
        extra_data='{"source":"test"}',
        tokens_total=42,
        latency_ms=120,
        tool_calls_count=1,
    )
    session.add(audit_log)
    await session.flush()

    storage_response = await client.get("/api/v1/settings/audit-details/storage")

    assert storage_response.status_code == 200
    storage = storage_response.json()
    assert storage["detail_records_count"] == 1
    assert storage["detail_bytes"] == sum(
        len(value.encode("utf-8"))
        for value in (
            audit_log.request_messages,
            audit_log.tool_references,
            audit_log.response_content,
            audit_log.response_tool_calls,
            audit_log.tool_call_results,
            audit_log.extra_data,
        )
        if value is not None
    )

    clear_response = await client.delete("/api/v1/settings/audit-details")

    assert clear_response.status_code == 200
    assert clear_response.json() == {
        "cleared_records_count": 1,
        "cleared_detail_bytes": storage["detail_bytes"],
    }
    await session.refresh(audit_log)
    assert audit_log.request_messages is None
    assert audit_log.tool_references is None
    assert audit_log.response_content is None
    assert audit_log.response_tool_calls is None
    assert audit_log.tool_call_results is None
    assert audit_log.extra_data is None
    assert audit_log.tokens_total == 42
    assert audit_log.latency_ms == 120
    assert audit_log.tool_calls_count == 1


@pytest.mark.asyncio
async def test_update_settings_agent_tool_permissions(client: AsyncClient) -> None:
    """测试更新 Agent 工具权限设置。"""
    response = await client.put(
        "/api/v1/settings",
        json={
            "agent_tool_permissions": [
                {"tool_name": "write_chapter", "mode": "allow"},
                {"tool_name": "edit_chapter", "mode": "deny"},
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["agent_tool_permissions"] == _expected_agent_tool_permissions(
        write_chapter="allow",
        edit_chapter="deny",
    )


@pytest.mark.asyncio
async def test_get_settings_does_not_lazy_persist_agent_tool_permissions(
    client: AsyncClient, session
) -> None:
    """首次读取设置只返回默认值，不应懒写入数据库。"""
    response = await client.get("/api/v1/settings")

    assert response.status_code == 200
    setting = await setting_repo.get_by_key(session, "agent_tool_permissions")
    assert setting is None
    bypass_setting = await setting_repo.get_by_key(session, "agent_bypass_tool_approval")
    assert bypass_setting is None

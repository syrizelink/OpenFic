# -*- coding: utf-8 -*-
"""
Dashboard LLM API 测试。
"""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models.llm_audit_log import LLMAuditLog


@pytest.mark.asyncio
async def test_llm_dashboard_records_include_output_details(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """测试调用记录返回模型输出和工具调用详情，不内联输入提示词。"""
    project_response = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说"},
    )
    project_id = project_response.json()["id"]

    audit_log = LLMAuditLog(
        created_at=datetime(2026, 5, 9, 7, 30, tzinfo=UTC),
        project_id=project_id,
        operation="writer",
        model_id="test-model",
        model_provider="openai-compatible",
        model_name="Test Model",
        request_messages='[{"role":"system","content":"系统提示"},{"role":"user","content":"用户提示"}]',
        response_content="模型输出正文",
        response_tool_calls='[{"name":"edit_chapter","args":{"chapter_ref":{"type":"order","value":1}}}]',
        tokens_input=120,
        tokens_output=34,
        tokens_total=154,
        token_cache=20,
        latency_ms=900,
        first_token_ms=120,
        status="success",
        tool_calls_count=1,
    )
    session.add(audit_log)
    await session.commit()

    response = await client.get("/api/v1/dashboard/llm-api/records")

    assert response.status_code == 200
    record = response.json()["records"]["items"][0]
    assert record["project_title"] == "测试小说"
    assert record["token_cache"] == 20
    assert "request_messages" not in record
    assert record["response_content"] == "模型输出正文"
    assert record["response_tool_calls"] == audit_log.response_tool_calls


@pytest.mark.asyncio
async def test_llm_dashboard_record_prompt_returns_request_messages(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """测试输入提示词通过单条记录详情接口返回。"""
    project_response = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说"},
    )
    project_id = project_response.json()["id"]
    audit_log = LLMAuditLog(
        project_id=project_id,
        operation="writer",
        model_id="test-model",
        request_messages='[{"role":"system","content":"系统提示"}]',
        tokens_input=12,
        tokens_total=12,
        status="success",
    )
    session.add(audit_log)
    await session.commit()

    response = await client.get(f"/api/v1/dashboard/llm-api/records/{audit_log.id}/prompt")

    assert response.status_code == 200
    assert response.json() == {
        "id": audit_log.id,
        "request_messages": audit_log.request_messages,
    }


@pytest.mark.asyncio
async def test_llm_dashboard_filters_summary_operations(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    project_response = await client.post("/api/v1/projects", data={"title": "测试小说"})
    project_id = project_response.json()["id"]
    session.add_all(
        [
            LLMAuditLog(
                project_id=project_id,
                operation="writer",
                model_id="test-model",
                status="success",
            ),
            LLMAuditLog(
                project_id=project_id,
                operation="chapter_summary",
                model_id="test-model",
                status="success",
            ),
        ]
    )
    await session.commit()

    response = await client.get(
        "/api/v1/dashboard/llm-api/records",
        params={"operation": "chapter_summary"},
    )

    assert response.status_code == 200
    assert response.json()["options"]["operations"] == ["chapter_summary", "writer"]
    assert [item["operation"] for item in response.json()["records"]["items"]] == [
        "chapter_summary"
    ]


@pytest.mark.asyncio
async def test_llm_dashboard_filters_records_by_category(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    project_response = await client.post("/api/v1/projects", data={"title": "测试小说"})
    project_id = project_response.json()["id"]
    session.add_all(
        [
            LLMAuditLog(
                project_id=project_id,
                category="agent",
                operation="writer",
                model_id="test-model",
                status="success",
            ),
            LLMAuditLog(
                project_id=project_id,
                category="memory",
                operation="chapter_summary",
                model_id="test-model",
                status="success",
            ),
        ]
    )
    await session.commit()

    response = await client.get(
        "/api/v1/dashboard/llm-api/records",
        params={"category": "memory"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["options"]["categories"] == ["agent", "memory"]
    assert [item["category"] for item in payload["records"]["items"]] == ["memory"]


@pytest.mark.asyncio
async def test_llm_dashboard_searches_category_and_operation(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    project_response = await client.post("/api/v1/projects", data={"title": "测试小说"})
    project_id = project_response.json()["id"]
    session.add_all(
        [
            LLMAuditLog(
                project_id=project_id,
                category="agent",
                operation="writer",
                model_id="test-model",
                status="success",
            ),
            LLMAuditLog(
                project_id=project_id,
                category="memory",
                operation="chapter_summary",
                model_id="test-model",
                status="success",
            ),
        ]
    )
    await session.commit()

    response = await client.get(
        "/api/v1/dashboard/llm-api/records",
        params={"search": "chapter_summary"},
    )

    assert response.status_code == 200
    assert [item["operation"] for item in response.json()["records"]["items"]] == [
        "chapter_summary"
    ]


@pytest.mark.asyncio
async def test_llm_dashboard_stats_include_model_trends_and_project_breakdown(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """测试统计接口返回按模型趋势和按项目分布。"""
    project_a_response = await client.post("/api/v1/projects", data={"title": "项目甲"})
    project_b_response = await client.post("/api/v1/projects", data={"title": "项目乙"})
    project_a_id = project_a_response.json()["id"]
    project_b_id = project_b_response.json()["id"]
    session.add_all(
        [
            LLMAuditLog(
                created_at=datetime(2026, 5, 8, 7, 30, tzinfo=UTC),
                project_id=project_a_id,
                operation="writer",
                model_id="model-a",
                model_name="模型 A",
                tokens_total=100,
                latency_ms=800,
                status="success",
            ),
            LLMAuditLog(
                created_at=datetime(2026, 5, 9, 7, 30, tzinfo=UTC),
                project_id=project_a_id,
                operation="writer",
                model_id="model-a",
                model_name="模型 A",
                tokens_total=60,
                latency_ms=1000,
                status="success",
            ),
            LLMAuditLog(
                created_at=datetime(2026, 5, 9, 8, 30, tzinfo=UTC),
                project_id=project_b_id,
                operation="reviewer",
                model_id="model-b",
                model_name="模型 B",
                tokens_total=40,
                latency_ms=1200,
                status="success",
            ),
        ]
    )
    await session.commit()

    response = await client.get("/api/v1/dashboard/llm-api/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["model_time_series"] == [
        {
            "date": "2026-05-08",
            "key": "model-a",
            "label": "模型 A",
            "calls": 1,
            "tokens_total": 100,
            "avg_latency_ms": 800.0,
        },
        {
            "date": "2026-05-09",
            "key": "model-a",
            "label": "模型 A",
            "calls": 1,
            "tokens_total": 60,
            "avg_latency_ms": 1000.0,
        },
        {
            "date": "2026-05-09",
            "key": "model-b",
            "label": "模型 B",
            "calls": 1,
            "tokens_total": 40,
            "avg_latency_ms": 1200.0,
        },
    ]
    assert data["by_project"] == [
        {
            "key": project_a_id,
            "label": "项目甲",
            "calls": 2,
            "tokens_total": 160,
        },
        {
            "key": project_b_id,
            "label": "项目乙",
            "calls": 1,
            "tokens_total": 40,
        },
    ]

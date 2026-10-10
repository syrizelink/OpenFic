# -*- coding: utf-8 -*-
"""
Dashboard LLM API 测试。
"""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models.llm_audit_log import LLMAuditLog


def _track_sql_statements(session: AsyncSession) -> tuple[list[str], object]:
    statements: list[str] = []
    bind = session.sync_session.get_bind()

    def before_cursor_execute(
        _conn, _cursor, statement, _parameters, _context, _executemany
    ):
        statements.append(statement)

    event.listen(bind, "before_cursor_execute", before_cursor_execute)
    return statements, before_cursor_execute


def _stop_tracking_sql(session: AsyncSession, listener: object) -> None:
    event.remove(session.sync_session.get_bind(), "before_cursor_execute", listener)


@pytest.mark.asyncio
async def test_llm_dashboard_records_load_output_details_on_demand(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """列表只返回元数据，输入和输出详情按需加载。"""
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
        tool_references='[{"name":"edit_chapter","description":"编辑章节","parameters":{"content":{"type":"string"}}}]',
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
    assert record["created_at"] == "2026-05-09T07:30:00Z"
    assert record["token_cache"] == 20
    assert "request_messages" not in record
    assert record["has_request_messages"] is True
    assert record["has_tool_references"] and record["has_output_details"]
    assert (
        not {
            "tool_references",
            "response_content",
            "response_tool_calls",
            "error_message",
        }
        & record.keys()
    )
    details = await client.get(
        f"/api/v1/dashboard/llm-api/records/{audit_log.id}/details"
    )
    assert details.status_code == 200
    assert details.json() == {
        "id": audit_log.id,
        "response_content": "模型输出正文",
        "response_tool_calls": audit_log.response_tool_calls,
        "tool_references": audit_log.tool_references,
        "error_message": None,
    }


@pytest.mark.asyncio
async def test_llm_dashboard_records_indicate_when_input_details_are_unavailable(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """调用记录列表应标识输入详情是否可查看。"""
    project_response = await client.post(
        "/api/v1/projects",
        data={"title": "测试小说"},
    )
    project_id = project_response.json()["id"]
    session.add_all(
        [
            LLMAuditLog(
                project_id=project_id,
                operation="writer",
                model_id="with-input",
                request_messages='[{"role":"user","content":"提示"}]',
                status="success",
            ),
            LLMAuditLog(
                project_id=project_id,
                operation="writer",
                model_id="without-input",
                request_messages="",
                status="success",
            ),
        ]
    )
    await session.commit()

    response = await client.get("/api/v1/dashboard/llm-api/records")

    assert response.status_code == 200
    records_by_model = {
        record["model_id"]: record for record in response.json()["records"]["items"]
    }
    assert records_by_model["with-input"]["has_request_messages"] is True
    assert records_by_model["without-input"]["has_request_messages"] is False


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

    response = await client.get(
        f"/api/v1/dashboard/llm-api/records/{audit_log.id}/prompt"
    )

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


@pytest.mark.asyncio
async def test_llm_dashboard_stats_merge_model_name_changes(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """同一模型 ID 的历史显示名变化不应拆分统计结果。"""
    project_response = await client.post("/api/v1/projects", data={"title": "测试小说"})
    project_id = project_response.json()["id"]
    session.add_all(
        [
            LLMAuditLog(
                created_at=datetime(2026, 5, 9, 7, 30, tzinfo=UTC),
                project_id=project_id,
                operation="writer",
                model_id="model-a",
                model_name=None,
                tokens_total=100,
                status="success",
            ),
            LLMAuditLog(
                created_at=datetime(2026, 5, 9, 8, 30, tzinfo=UTC),
                project_id=project_id,
                operation="writer",
                model_id="model-a",
                model_name="Model A",
                tokens_total=60,
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
            "date": "2026-05-09",
            "key": "model-a",
            "label": "Model A",
            "calls": 2,
            "tokens_total": 160,
            "avg_latency_ms": 0.0,
        }
    ]
    assert data["by_model"] == [
        {
            "key": "model-a",
            "label": "Model A",
            "calls": 2,
            "tokens_total": 160,
        }
    ]
    assert data["options"]["model_options"] == [
        {"value": "model-a", "label": "Model A"}
    ]


@pytest.mark.asyncio
async def test_llm_dashboard_stats_uses_bounded_query_count(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    project_response = await client.post("/api/v1/projects", data={"title": "测试小说"})
    project_id = project_response.json()["id"]
    session.add(
        LLMAuditLog(
            project_id=project_id,
            operation="writer",
            model_id="test-model",
            status="success",
        )
    )
    await session.commit()
    statements, listener = _track_sql_statements(session)

    try:
        response = await client.get("/api/v1/dashboard/llm-api/stats")
    finally:
        _stop_tracking_sql(session, listener)

    assert response.status_code == 200
    assert len(statements) <= 2


@pytest.mark.asyncio
async def test_llm_dashboard_records_uses_one_page_and_one_options_query(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    project_response = await client.post("/api/v1/projects", data={"title": "测试小说"})
    project_id = project_response.json()["id"]
    session.add(
        LLMAuditLog(
            project_id=project_id,
            operation="writer",
            model_id="test-model",
            status="success",
        )
    )
    await session.commit()
    statements, listener = _track_sql_statements(session)

    try:
        response = await client.get("/api/v1/dashboard/llm-api/records")
    finally:
        _stop_tracking_sql(session, listener)

    assert response.status_code == 200
    assert len(statements) <= 2


@pytest.mark.asyncio
async def test_llm_dashboard_large_details_do_not_inflate_list(
    client: AsyncClient, session: AsyncSession
) -> None:
    project = (await client.post("/api/v1/projects", data={"title": "长上下文"})).json()
    large = "大段正文" * 100_000
    record = LLMAuditLog(
        project_id=project["id"],
        operation="writer",
        model_id="large",
        status="error",
        request_messages=large,
        tool_references=large,
        response_content=large,
        response_tool_calls=large,
        error_message=large,
    )
    session.add(record)
    await session.commit()
    response = await client.get("/api/v1/dashboard/llm-api/records")
    assert response.status_code == 200
    assert len(response.content) < 5000
    item = response.json()["records"]["items"][0]
    assert (
        item["has_request_messages"]
        and item["has_tool_references"]
        and item["has_output_details"]
    )
    details = await client.get(f"/api/v1/dashboard/llm-api/records/{record.id}/details")
    assert details.json()["error_message"] == large


@pytest.mark.asyncio
async def test_llm_dashboard_details_missing_and_empty_flags(
    client: AsyncClient, session: AsyncSession
) -> None:
    project = (await client.post("/api/v1/projects", data={"title": "空详情"})).json()
    session.add_all(
        [
            LLMAuditLog(
                project_id=project["id"],
                operation="writer",
                model_id="empty",
                status="success",
                tool_references="[]",
                response_tool_calls="null",
            ),
            LLMAuditLog(
                project_id=project["id"],
                operation="writer",
                model_id="error",
                status="error",
                error_status_code=429,
            ),
        ]
    )
    await session.commit()
    response = await client.get("/api/v1/dashboard/llm-api/records")
    items = {item["model_id"]: item for item in response.json()["records"]["items"]}
    assert (
        not items["empty"]["has_tool_references"]
        and not items["empty"]["has_output_details"]
    )
    assert items["error"]["has_output_details"]
    assert (
        await client.get("/api/v1/dashboard/llm-api/records/missing/details")
    ).status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "sort_by",
    [
        "created_at",
        "tokens_input",
        "tokens_output",
        "tokens_total",
        "latency_ms",
        "first_token_ms",
        "tool_calls_count",
    ],
)
@pytest.mark.parametrize("sort_order", ["asc", "desc"])
async def test_llm_dashboard_cte_ordering_pagination_and_total(
    client: AsyncClient, session: AsyncSession, sort_by: str, sort_order: str
) -> None:
    project = (await client.post("/api/v1/projects", data={"title": "分页排序"})).json()
    records = [
        LLMAuditLog(
            id=f"sort-{i:02}",
            project_id=project["id"],
            operation="writer",
            model_id="matched" if i < 12 else "other",
            status="success",
            created_at=datetime(2026, 5, 1 + i % 3),
            tokens_input=i % 3,
            tokens_output=i % 3,
            tokens_total=i % 3,
            latency_ms=None if i % 3 == 0 else i % 3,
            first_token_ms=None if i % 3 == 0 else i % 3,
            tool_calls_count=i % 3,
        )
        for i in range(15)
    ]
    session.add_all(records)
    await session.commit()
    expected = sorted(records[:12], key=lambda row: row.id, reverse=True)
    expected.sort(
        key=lambda row: (getattr(row, sort_by) is not None, getattr(row, sort_by)),
        reverse=sort_order == "desc",
    )
    ids = []
    for page in range(1, 5):
        response = await client.get(
            "/api/v1/dashboard/llm-api/records",
            params={
                "model_id": "matched",
                "page": page,
                "page_size": 5,
                "sort_by": sort_by,
                "sort_order": sort_order,
            },
        )
        assert response.status_code == 200
        data = response.json()["records"]
        assert data["total"] == 12
        ids.extend(item["id"] for item in data["items"])
    assert ids == [row.id for row in expected]


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{}, {"page": 2}, {"model_id": "missing"}])
async def test_llm_dashboard_cte_empty_pages_need_no_fallback(
    client: AsyncClient, session: AsyncSession, params: dict
) -> None:
    project = (await client.post("/api/v1/projects", data={"title": "空页"})).json()
    session.add(
        LLMAuditLog(
            project_id=project["id"],
            operation="writer",
            model_id="model",
            status="success",
        )
    )
    await session.commit()
    statements, listener = _track_sql_statements(session)
    try:
        response = await client.get("/api/v1/dashboard/llm-api/records", params=params)
    finally:
        _stop_tracking_sql(session, listener)
    data = response.json()["records"]
    assert data["total"] == (0 if "model_id" in params else 1)
    assert len(data["items"]) == (0 if params else 1)
    assert len(statements) == 2
    assert "OVER (" not in statements[0].upper()
    assert "dashboard_record_page AS MATERIALIZED" in statements[0]


@pytest.mark.asyncio
async def test_llm_dashboard_cte_empty_database(client: AsyncClient) -> None:
    response = await client.get("/api/v1/dashboard/llm-api/records", params={"page": 5})
    assert response.json()["records"] == {
        "items": [],
        "total": 0,
        "page": 5,
        "page_size": 20,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("date_filter", [False, True])
async def test_llm_dashboard_covering_query_plans(
    session: AsyncSession, date_filter: bool
) -> None:
    from app.storage.repos import dashboard_repo

    queries = []
    bind = session.sync_session.get_bind()

    def track(_conn, _cursor, statement, parameters, _context, _executemany):
        queries.append((statement, parameters))

    filters = dashboard_repo.DashboardFilters(
        start_at=datetime(2026, 5, 1) if date_filter else None,
        end_at=datetime(2026, 5, 31) if date_filter else None,
    )
    event.listen(bind, "before_cursor_execute", track)
    try:
        await dashboard_repo.get_stats(session, filters)
        await dashboard_repo.get_filter_options(session)
        records, total = await dashboard_repo.list_records(
            session, filters, 20, 0, "created_at", "desc"
        )
    finally:
        event.remove(bind, "before_cursor_execute", track)
    assert records == [] and total == 0
    assert len(queries) == 3
    connection = await session.connection()
    plans = []
    for sql, params in queries:
        result = await connection.exec_driver_sql("EXPLAIN QUERY PLAN " + sql, params)
        plans.append([row[3] for row in result])
    assert "COVERING INDEX ix_agent_audit_logs_dashboard_metrics" in "\n".join(plans[0])
    assert "COVERING INDEX ix_agent_audit_logs_model_id_model_name" in "\n".join(
        plans[1]
    )
    start = plans[2].index("MATERIALIZE dashboard_record_page")
    assert "COVERING INDEX ix_agent_audit_logs_dashboard_metrics" in plans[2][start + 1]

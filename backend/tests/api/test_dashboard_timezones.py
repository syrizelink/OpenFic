"""Dashboard boundaries must be timezone-aware before binding database parameters."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage.models.llm_audit_log import LLMAuditLog


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["records", "stats"])
@pytest.mark.parametrize("parameter", ["start_at", "end_at"])
async def test_dashboard_rejects_naive_boundaries(
    client: AsyncClient, endpoint: str, parameter: str
) -> None:
    response = await client.get(
        f"/api/v1/dashboard/llm-api/{endpoint}",
        params={parameter: "2026-10-25T00:00:00"},
    )
    assert response.status_code == 422
    assert any(
        error["loc"] == ["query", parameter]
        and error["type"] == "timezone_aware"
        for error in response.json()["detail"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["records", "stats"])
@pytest.mark.parametrize(
    ("start_at", "end_at"),
    [
        ("2026-10-25T00:00:00+08:00", "2026-10-25T23:59:59+08:00"),
        ("2026-10-24T16:00:00Z", "2026-10-25T15:59:59Z"),
    ],
)
async def test_dashboard_uses_utc_boundaries(
    client: AsyncClient,
    session: AsyncSession,
    endpoint: str,
    start_at: str,
    end_at: str,
) -> None:
    project = await client.post("/api/v1/projects", data={"title": "Timezone test"})
    for hour in (15, 16, 23):
        session.add(
            LLMAuditLog(
                project_id=project.json()["id"],
                created_at=datetime(2026, 10, 24, hour, tzinfo=UTC),
                operation="writer",
                model_id="timezone-model",
                status="success",
            )
        )
    await session.commit()
    response = await client.get(
        f"/api/v1/dashboard/llm-api/{endpoint}",
        params={"start_at": start_at, "end_at": end_at},
    )
    assert response.status_code == 200
    payload = response.json()
    if endpoint == "records":
        assert payload["records"]["total"] == 2
    else:
        assert payload["summary"]["calls_total"] == 2

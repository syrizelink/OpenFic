# -*- coding: utf-8 -*-
"""Tests for Chapter Context API."""

import pytest
from httpx import AsyncClient

from app.api.routers.chapter_context import (
    build_summary_panel_response,
    build_summary_statuses_response,
)
from app.background.jobs.models import BackgroundJob, BackgroundJobItem
from app.memory.chapter.summary_service import (
    LONG_TERM_SUMMARY_INTERVAL,
    MIN_CHAPTER_SUMMARY_WORD_COUNT,
    encode_summary_list,
    normalize_summary_source_content,
)
from app.storage.repos import chapter_summary_repo
from app.storage.models.chapter_summary import ChapterSummary
from app.storage.repos.chapter_summary_repo import SUMMARY_STATUS_FAILED, SUMMARY_STATUS_READY, SUMMARY_TYPE_LONG_TERM


class _FakeResponse:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def json(self):
        return self._payload


async def _summary_statuses_response(session, project_id: str) -> _FakeResponse:
    statuses = await build_summary_statuses_response(session, project_id)
    return _FakeResponse([item.model_dump(mode="json") for item in statuses])


async def _summary_panel_response(session, project_id: str) -> _FakeResponse:
    panel = await build_summary_panel_response(session, project_id)
    return _FakeResponse(panel.model_dump(mode="json"))


def _source_content(chapter: dict) -> str:
    return normalize_summary_source_content(chapter["content"])


async def _default_volume_id(client: AsyncClient, project_id: str) -> str:
    response = await client.get(f"/api/v1/projects/{project_id}/volumes")
    assert response.status_code == 200
    volumes = response.json()
    assert len(volumes) == 1
    return volumes[0]["id"]


@pytest.fixture
async def test_project(client: AsyncClient) -> dict:
    response = await client.post(
        "/api/v1/projects",
        data={"title": "Context Test Project", "description": "Test project"},
    )
    assert response.status_code == 201
    project = response.json()
    project["default_volume_id"] = await _default_volume_id(client, project["id"])
    return project


@pytest.fixture
async def test_chapters(client: AsyncClient, test_project: dict) -> list[dict]:
    chapters = []
    for i in range(5):
        response = await client.post(
            f"/api/v1/projects/{test_project['id']}/chapters",
            json={
                "volume_id": test_project["default_volume_id"],
                "title": f"第{i + 1}章",
                "content": f"这是第{i + 1}章的内容。" * 50,
                "word_count": 800,
            },
        )
        assert response.status_code == 201
        chapters.append(response.json())
    return chapters


@pytest.mark.asyncio
class TestChapterSummaries:
    async def test_list_statuses_defaults_to_not_generated(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        response = await _summary_statuses_response(session, test_project["id"])
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
        assert {item["status"] for item in data} == {"not_generated"}
        assert {item["is_stale"] for item in data} == {False}

    async def test_enqueue_summary_creates_queued_row(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        chapter = test_chapters[0]
        response = await client.post(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/enqueue",
            json={"chapter_id": chapter["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["job_id"]

        status_response = await _summary_statuses_response(session, test_project["id"])
        statuses = {item["chapter_id"]: item["status"] for item in status_response.json()}
        assert statuses[chapter["id"]] == "queued"

    async def test_enqueue_summary_does_not_downgrade_ready_chapter_to_queued(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        chapter = test_chapters[0]
        session.add(
            ChapterSummary(
                project_id=test_project["id"],
                summary_type="chapter",
                status=SUMMARY_STATUS_READY,
                chapter_id=chapter["id"],
                chapter_order=chapter["order"],
                start_order=chapter["order"],
                end_order=chapter["order"],
                summary="已完成摘要",
                source_content_normalized=_source_content(chapter),
            )
        )
        await session.commit()

        response = await client.post(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/enqueue",
            json={"chapter_id": chapter["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

        status_response = await _summary_statuses_response(session, test_project["id"])
        item = next(item for item in status_response.json() if item["chapter_id"] == chapter["id"])
        assert item["status"] == "ready"

    async def test_enqueue_stale_ready_summary_keeps_db_ready_but_status_endpoint_queued(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        chapter = test_chapters[0]
        session.add(
            ChapterSummary(
                project_id=test_project["id"],
                summary_type="chapter",
                status=SUMMARY_STATUS_READY,
                chapter_id=chapter["id"],
                chapter_order=chapter["order"],
                start_order=chapter["order"],
                end_order=chapter["order"],
                summary="旧摘要",
                source_content_normalized="完全不同的旧内容",
            )
        )
        await session.commit()

        response = await client.post(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/enqueue",
            json={"chapter_id": chapter["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["job_id"] is None

        stored = await chapter_summary_repo.get_by_chapter_id(session, chapter["id"])
        assert stored is not None
        assert stored.status == SUMMARY_STATUS_READY

        status_response = await _summary_statuses_response(session, test_project["id"])
        item = next(item for item in status_response.json() if item["chapter_id"] == chapter["id"])
        assert item["status"] == "queued"

        panel_response = await _summary_panel_response(session, test_project["id"])
        active_jobs = panel_response.json()["maintenance"]["active_jobs"]
        assert any(job["chapter_id"] == chapter["id"] for job in active_jobs)

        list_response = await client.get(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/chapters"
        )
        list_item = next(item for item in list_response.json()["items"] if item["chapter_id"] == chapter["id"])
        assert list_item["status"] == "queued"

    async def test_summary_stale_is_dynamic_by_content_diff(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        chapter = test_chapters[0]
        session.add(
            ChapterSummary(
                project_id=test_project["id"],
                summary_type="chapter",
                status=SUMMARY_STATUS_READY,
                chapter_id=chapter["id"],
                chapter_order=chapter["order"],
                start_order=chapter["order"],
                end_order=chapter["order"],
                summary="旧摘要",
                source_content_normalized=_source_content(chapter),
            )
        )
        await session.commit()

        response = await client.patch(
            f"/api/v1/chapters/{chapter['id']}",
            json={
                "content": f"{chapter['content']}{'新增剧情' * 40}",
                "word_count": 1200,
            },
        )
        assert response.status_code == 200

        status_response = await _summary_statuses_response(session, test_project["id"])
        item = next(item for item in status_response.json() if item["chapter_id"] == chapter["id"])
        assert item["status"] == "ready"
        assert item["is_stale"] is True

        response = await client.patch(
            f"/api/v1/chapters/{chapter['id']}",
            json={"content": chapter["content"], "word_count": chapter["word_count"]},
        )
        assert response.status_code == 200
        status_response = await _summary_statuses_response(session, test_project["id"])
        item = next(item for item in status_response.json() if item["chapter_id"] == chapter["id"])
        assert item["status"] == "ready"
        assert item["is_stale"] is False

    async def test_summary_stale_ignores_whitespace_and_punctuation(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        chapter = test_chapters[0]
        session.add(
            ChapterSummary(
                project_id=test_project["id"],
                summary_type="chapter",
                status=SUMMARY_STATUS_READY,
                chapter_id=chapter["id"],
                chapter_order=chapter["order"],
                start_order=chapter["order"],
                end_order=chapter["order"],
                summary="旧摘要",
                source_content_normalized=_source_content(chapter),
            )
        )
        await session.commit()

        changed_content = "\n，。".join(chapter["content"])
        response = await client.patch(
            f"/api/v1/chapters/{chapter['id']}",
            json={"content": changed_content, "word_count": chapter["word_count"]},
        )
        assert response.status_code == 200

        status_response = await _summary_statuses_response(session, test_project["id"])
        item = next(item for item in status_response.json() if item["chapter_id"] == chapter["id"])
        assert item["status"] == "ready"
        assert item["is_stale"] is False

    async def test_enqueue_summary_rejects_short_chapter(
        self, client: AsyncClient, test_project: dict
    ):
        response = await client.post(
            f"/api/v1/projects/{test_project['id']}/chapters",
            json={
                "volume_id": test_project["default_volume_id"],
                "title": "短章节",
                "content": "内容",
                "word_count": 100,
            },
        )
        assert response.status_code == 201
        chapter = response.json()

        enqueue_response = await client.post(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/enqueue",
            json={"chapter_id": chapter["id"]},
        )
        assert enqueue_response.status_code == 400
        assert str(MIN_CHAPTER_SUMMARY_WORD_COUNT) in enqueue_response.json()["detail"]

    async def test_summary_panel_returns_structured_summary(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        chapter = test_chapters[0]
        row = ChapterSummary(
            project_id=test_project["id"],
            summary_type="chapter",
            status=SUMMARY_STATUS_READY,
            chapter_id=chapter["id"],
            chapter_order=chapter["order"],
            start_order=chapter["order"],
            end_order=chapter["order"],
            start_time="清晨",
            end_time="午后",
            characters_json=encode_summary_list(["林舟"]),
            locations_json=encode_summary_list(["旧城"]),
            summary="林舟进入旧城并发现线索。",
            source_content_normalized=_source_content(chapter),
        )
        session.add(row)
        await session.commit()

        response = await _summary_panel_response(session, test_project["id"])
        assert response.status_code == 200
        data = response.json()
        assert "chapter_summary" not in data
        assert "maintenance" in data

        list_response = await client.get(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/chapters",
        )
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert list_data["total"] == 1
        assert list_data["page"] == 1
        assert list_data["page_size"] == 20
        assert list_data["items"][0]["summary"] == "林舟进入旧城并发现线索。"
        assert list_data["items"][0]["characters"] == ["林舟"]
        assert list_data["items"][0]["locations"] == ["旧城"]

    async def test_list_chapter_summaries_supports_pagination(
        self, client: AsyncClient, session, test_project: dict
    ):
        chapters: list[dict] = []
        for index in range(25):
            response = await client.post(
                f"/api/v1/projects/{test_project['id']}/chapters",
                json={
                    "volume_id": test_project["default_volume_id"],
                    "title": f"第{index + 1}章",
                    "content": "内容",
                    "word_count": 800,
                },
            )
            assert response.status_code == 201
            chapters.append(response.json())
        await chapter_summary_repo.delete_all_chapter_summaries_by_project(
            session, test_project["id"]
        )

        for chapter in chapters:
            session.add(
                ChapterSummary(
                    project_id=test_project["id"],
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter["id"],
                    chapter_order=chapter["order"],
                    start_order=chapter["order"],
                    end_order=chapter["order"],
                    summary=f"摘要{chapter['order']}",
                    source_content_normalized="内容",
                )
            )
        await session.commit()

        response = await client.get(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/chapters",
            params={"page": 2, "page_size": 20},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 25
        assert data["page"] == 2
        assert data["page_size"] == 20
        assert len(data["items"]) == 5
        assert data["items"][0]["chapter_order"] == 21

    async def test_list_chapter_summaries_returns_only_existing_summary_rows(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        for chapter in test_chapters[:2]:
            session.add(
                ChapterSummary(
                    project_id=test_project["id"],
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter["id"],
                    chapter_order=chapter["order"],
                    start_order=chapter["order"],
                    end_order=chapter["order"],
                    summary=f"摘要{chapter['order']}",
                    source_content_normalized=_source_content(chapter),
                )
            )
        await session.commit()

        response = await client.get(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/chapters"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert [item["chapter_order"] for item in data["items"]] == [1, 2]
        assert {item["status"] for item in data["items"]} == {"ready"}

    async def test_list_chapter_summaries_filters_by_volume_and_includes_volume_fields(
        self, client: AsyncClient, session, test_project: dict
    ):
        first_volume_id = test_project["default_volume_id"]
        second_volume_response = await client.post(
            f"/api/v1/projects/{test_project['id']}/volumes",
            json={"title": "第二卷"},
        )
        assert second_volume_response.status_code == 201
        second_volume_id = second_volume_response.json()["id"]

        chapters: list[tuple[str, str, int]] = []
        for volume_id, volume_label in [
            (first_volume_id, "第一卷"),
            (second_volume_id, "第二卷"),
        ]:
            for index in range(2):
                response = await client.post(
                    f"/api/v1/projects/{test_project['id']}/chapters",
                    json={
                        "volume_id": volume_id,
                        "title": f"{volume_label}第{index + 1}章",
                        "content": "内容",
                        "word_count": 800,
                    },
                )
                assert response.status_code == 201
                chapters.append((volume_id, response.json()["id"], response.json()["order"]))

        for global_order, (volume_id, chapter_id, _) in enumerate(chapters):
            session.add(
                ChapterSummary(
                    project_id=test_project["id"],
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter_id,
                    volume_id=volume_id,
                    chapter_order=global_order,
                    start_order=global_order,
                    end_order=global_order,
                    summary=f"摘要{global_order}",
                    source_content_normalized="内容",
                )
            )
        await session.commit()

        response = await client.get(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/chapters"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 4
        assert [item["volume_id"] for item in data["items"]] == [
            first_volume_id,
            first_volume_id,
            second_volume_id,
            second_volume_id,
        ]
        assert data["items"][0]["volume_title"] == "第一卷"
        assert data["items"][0]["volume_order"] == 1
        assert data["items"][2]["volume_title"] == "第二卷"
        assert data["items"][2]["volume_order"] == 2

        filtered_response = await client.get(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/chapters",
            params={"volume_id": second_volume_id},
        )
        assert filtered_response.status_code == 200
        filtered_data = filtered_response.json()
        assert filtered_data["total"] == 2
        assert {item["volume_id"] for item in filtered_data["items"]} == {second_volume_id}
        assert {item["volume_title"] for item in filtered_data["items"]} == {"第二卷"}

    async def test_delete_chapter_summaries(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        for chapter in test_chapters[:2]:
            session.add(
                ChapterSummary(
                    project_id=test_project["id"],
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter["id"],
                    chapter_order=chapter["order"],
                    start_order=chapter["order"],
                    end_order=chapter["order"],
                    summary=f"摘要{chapter['order']}",
                    source_content_normalized=_source_content(chapter),
                )
            )
        await session.commit()

        response = await client.request(
            "DELETE",
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/chapters",
            json={"chapter_ids": [test_chapters[0]["id"]]},
        )
        assert response.status_code == 204

        list_response = await client.get(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/chapters",
        )
        assert list_response.status_code == 200
        items = list_response.json()["items"]
        assert len(items) == 1
        assert items[0]["chapter_id"] == test_chapters[1]["id"]
        assert items[0]["status"] == "ready"

    async def test_delete_all_chapter_summaries(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        for chapter in test_chapters:
            session.add(
                ChapterSummary(
                    project_id=test_project["id"],
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter["id"],
                    chapter_order=chapter["order"],
                    start_order=chapter["order"],
                    end_order=chapter["order"],
                    summary=f"摘要{chapter['order']}",
                    source_content_normalized=_source_content(chapter),
                )
            )
        await session.commit()

        response = await client.request(
            "DELETE",
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/chapters",
            json={"chapter_ids": []},
        )
        assert response.status_code == 204

        list_response = await client.get(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/chapters",
        )
        assert list_response.status_code == 200
        assert list_response.json()["items"] == []

    async def test_maintenance_blocks_large_project_without_summaries(
        self, client: AsyncClient, session, test_project: dict
    ):
        for index in range(21):
            response = await client.post(
                f"/api/v1/projects/{test_project['id']}/chapters",
                json={
                    "volume_id": test_project["default_volume_id"],
                    "title": f"第{index + 1}章",
                    "content": "内容",
                    "word_count": 600,
                },
            )
            assert response.status_code == 201

        panel_response = await _summary_panel_response(session, test_project["id"])
        assert panel_response.status_code == 200
        maintenance = panel_response.json()["maintenance"]
        assert maintenance["auto_generation_blocked"] is True
        assert len(maintenance["missing_or_failed_chapter_summaries"]) == 21

    async def test_maintenance_lists_skipped_short_chapters(
        self, client: AsyncClient, session, test_project: dict
    ):
        short_response = await client.post(
            f"/api/v1/projects/{test_project['id']}/chapters",
            json={
                "volume_id": test_project["default_volume_id"],
                "title": "短章节",
                "content": "内容",
                "word_count": 120,
            },
        )
        assert short_response.status_code == 201

        long_response = await client.post(
            f"/api/v1/projects/{test_project['id']}/chapters",
            json={
                "volume_id": test_project["default_volume_id"],
                "title": "长章节",
                "content": "内容",
                "word_count": 800,
            },
        )
        assert long_response.status_code == 201

        panel_response = await _summary_panel_response(session, test_project["id"])
        assert panel_response.status_code == 200
        maintenance = panel_response.json()["maintenance"]
        assert [item["chapter_title"] for item in maintenance["missing_or_failed_chapter_summaries"]] == [
            "长章节"
        ]
        assert maintenance["skipped_chapter_summaries"] == [
            {
                "chapter_id": short_response.json()["id"],
                "chapter_order": 1,
                "volume_id": test_project["default_volume_id"],
                "volume_title": "第一卷",
                "volume_order": 1,
                "chapter_title": "短章节",
                "word_count": 120,
            }
        ]

    async def test_maintenance_returns_active_summary_jobs(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        chapter = test_chapters[0]
        summary = ChapterSummary(
            project_id=test_project["id"],
            summary_type="chapter",
            status="running",
            chapter_id=chapter["id"],
            chapter_order=chapter["order"],
            start_order=chapter["order"],
            end_order=chapter["order"],
            job_id="item-summary-1",
        )
        job = BackgroundJob(
            id="job-summary-1",
            type="summary_batch",
            status="running",
            subject_type="project",
            subject_id=test_project["id"],
            payload_json=f'{{"project_id":"{test_project["id"]}"}}',
            context_json=f'{{"project_id":"{test_project["id"]}"}}',
            progress_json='{"current":3,"total":3,"message":"处理中","progress_percent":100,"total_item_count":1,"completed_item_count":0,"running_item_count":1,"queued_item_count":0}',
        )
        item = BackgroundJobItem(
            id="item-summary-1",
            job_id="job-summary-1",
            item_key=f"chapter:{chapter['id']}",
            type="chapter_summary",
            status="running",
            payload_json=f'{{"chapter_id":"{chapter["id"]}"}}',
            progress_json='{"current":3,"total":3,"message":"章节摘要已保存"}',
            order_index=0,
        )
        session.add(summary)
        session.add(job)
        session.add(item)
        await session.commit()

        panel_response = await _summary_panel_response(session, test_project["id"])
        assert panel_response.status_code == 200
        maintenance = panel_response.json()["maintenance"]
        batch_progress = maintenance["batch_progress"]
        assert batch_progress["job_id"] == "job-summary-1"
        assert batch_progress["status"] == "running"
        assert batch_progress["progress_current"] == 3
        assert batch_progress["progress_total"] == 3
        assert batch_progress["progress_percent"] == 100
        assert batch_progress["progress_message"] == "处理中"
        assert batch_progress["total_item_count"] == 1
        assert batch_progress["completed_item_count"] == 0
        assert batch_progress["running_item_count"] == 1
        assert batch_progress["queued_item_count"] == 0

        active_jobs = maintenance["active_jobs"]
        assert len(active_jobs) == 1
        assert active_jobs[0]["job_id"] == "item-summary-1"
        assert active_jobs[0]["job_type"] == "chapter_summary"
        assert active_jobs[0]["progress_current"] == 3
        assert active_jobs[0]["progress_total"] == 3

        chapter_items = maintenance["missing_or_failed_chapter_summaries"]
        assert chapter_items[0]["chapter_id"] == chapter["id"]
        assert chapter_items[0]["status"] == "running"
        assert chapter_items[0]["progress_message"] == "章节摘要已保存"

    async def test_maintenance_aggregates_total_progress_from_all_summary_items(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        chapter_one = test_chapters[0]
        chapter_two = test_chapters[1]
        session.add(
            ChapterSummary(
                project_id=test_project["id"],
                summary_type="chapter",
                status="queued",
                chapter_id=chapter_one["id"],
                chapter_order=chapter_one["order"],
                start_order=chapter_one["order"],
                end_order=chapter_one["order"],
                job_id="item-summary-queued",
            )
        )
        session.add(
            ChapterSummary(
                project_id=test_project["id"],
                summary_type="chapter",
                status="running",
                chapter_id=chapter_two["id"],
                chapter_order=chapter_two["order"],
                start_order=chapter_two["order"],
                end_order=chapter_two["order"],
                job_id="item-summary-running",
            )
        )
        session.add(
            BackgroundJob(
                id="job-summary-aggregate",
                type="summary_batch",
                status="running",
                subject_type="project",
                subject_id=test_project["id"],
                payload_json=f'{{"project_id":"{test_project["id"]}"}}',
                context_json=f'{{"project_id":"{test_project["id"]}"}}',
                progress_json='{"current":7,"total":9,"message":"正在生成章节摘要","progress_percent":78,"total_item_count":3,"completed_item_count":1,"running_item_count":1,"queued_item_count":1}',
            )
        )
        session.add(
            BackgroundJobItem(
                id="item-summary-queued",
                job_id="job-summary-aggregate",
                item_key=f"chapter:{chapter_one['id']}",
                type="chapter_summary",
                status="pending",
                payload_json=f'{{"chapter_id":"{chapter_one["id"]}"}}',
                progress_json='{"current":0,"total":3,"message":"已加入队列"}',
                order_index=0,
            )
        )
        session.add(
            BackgroundJobItem(
                id="item-summary-running",
                job_id="job-summary-aggregate",
                item_key=f"chapter:{chapter_two['id']}",
                type="chapter_summary",
                status="running",
                payload_json=f'{{"chapter_id":"{chapter_two["id"]}"}}',
                progress_json='{"current":3,"total":3,"message":"章节摘要已保存"}',
                order_index=1,
            )
        )
        await session.commit()

        response = await _summary_panel_response(session, test_project["id"])
        assert response.status_code == 200
        batch_progress = response.json()["maintenance"]["batch_progress"]
        assert batch_progress["total_item_count"] == 3
        assert batch_progress["completed_item_count"] == 1
        assert batch_progress["running_item_count"] == 1
        assert batch_progress["queued_item_count"] == 1
        assert batch_progress["progress_current"] == 7
        assert batch_progress["progress_total"] == 9
        assert batch_progress["progress_percent"] == 78

    async def test_maintenance_keeps_batch_progress_when_recent_batch_job_exists(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        chapter = test_chapters[0]
        session.add(
            ChapterSummary(
                project_id=test_project["id"],
                summary_type="chapter",
                status="running",
                chapter_id=chapter["id"],
                chapter_order=chapter["order"],
                start_order=chapter["order"],
                end_order=chapter["order"],
                job_id="item-summary-recent",
            )
        )
        session.add(
            BackgroundJob(
                id="job-summary-recent",
                type="summary_batch",
                status="succeeded",
                subject_type="project",
                subject_id=test_project["id"],
                payload_json=f'{{"project_id":"{test_project["id"]}"}}',
                context_json=f'{{"project_id":"{test_project["id"]}"}}',
                progress_json='{"current":3,"total":3,"message":"正在生成章节摘要","progress_percent":100,"total_item_count":1,"completed_item_count":0,"running_item_count":1,"queued_item_count":0}',
            )
        )
        session.add(
            BackgroundJobItem(
                id="item-summary-recent",
                job_id="job-summary-recent",
                item_key=f"chapter:{chapter['id']}",
                type="chapter_summary",
                status="running",
                payload_json=f'{{"chapter_id":"{chapter["id"]}"}}',
                progress_json='{"current":3,"total":3,"message":"章节摘要已保存"}',
                order_index=0,
            )
        )
        await session.commit()

        response = await _summary_panel_response(session, test_project["id"])
        assert response.status_code == 200
        batch_progress = response.json()["maintenance"]["batch_progress"]
        assert batch_progress is not None
        assert batch_progress["job_id"] == "job-summary-recent"
        assert batch_progress["progress_current"] == 3
        assert batch_progress["progress_total"] == 3
        assert batch_progress["progress_percent"] == 100

    async def test_maintenance_starts_batch_progress_at_zero_for_pending_items(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        chapter = test_chapters[0]
        session.add(
            BackgroundJob(
                id="job-summary-pending-zero",
                type="summary_batch",
                status="pending",
                subject_type="project",
                subject_id=test_project["id"],
                payload_json=f'{{"project_id":"{test_project["id"]}"}}',
                context_json=f'{{"project_id":"{test_project["id"]}"}}',
                progress_json="{}",
            )
        )
        session.add(
            BackgroundJobItem(
                id="item-summary-pending-zero",
                job_id="job-summary-pending-zero",
                item_key=f"chapter:{chapter['id']}",
                type="chapter_summary",
                status="pending",
                payload_json=f'{{"chapter_id":"{chapter["id"]}"}}',
                progress_json='{"current":0,"total":3,"message":"已加入队列"}',
                order_index=0,
            )
        )
        await session.commit()

        response = await _summary_panel_response(session, test_project["id"])
        assert response.status_code == 200
        batch_progress = response.json()["maintenance"]["batch_progress"]
        assert batch_progress["total_item_count"] == 1
        assert batch_progress["completed_item_count"] == 0
        assert batch_progress["running_item_count"] == 0
        assert batch_progress["queued_item_count"] == 1
        assert batch_progress["progress_current"] == 0
        assert batch_progress["progress_total"] == 3
        assert batch_progress["progress_percent"] == 0

    async def test_maintenance_returns_failed_summary_job_to_clear_queued_state(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        chapter = test_chapters[0]
        summary = ChapterSummary(
            project_id=test_project["id"],
            summary_type="chapter",
            status="failed",
            chapter_id=chapter["id"],
            chapter_order=chapter["order"],
            start_order=chapter["order"],
            end_order=chapter["order"],
            job_id="item-summary-failed",
            error_message="生成失败",
        )
        job = BackgroundJob(
            id="job-summary-failed",
            type="summary_batch",
            status="failed",
            subject_type="project",
            subject_id=test_project["id"],
            payload_json=f'{{"project_id":"{test_project["id"]}"}}',
            context_json=f'{{"project_id":"{test_project["id"]}"}}',
            progress_json='{"current":1,"total":3,"message":"正在生成章节摘要","progress_percent":33,"total_item_count":1,"completed_item_count":0,"running_item_count":0,"queued_item_count":1}',
            error_json='{"message":"生成失败"}',
        )
        item = BackgroundJobItem(
            id="item-summary-failed",
            job_id="job-summary-failed",
            item_key=f"chapter:{chapter['id']}",
            type="chapter_summary",
            status="failed",
            payload_json=f'{{"chapter_id":"{chapter["id"]}"}}',
            progress_json='{"current":1,"total":3,"message":"正在生成章节摘要"}',
            error_json='{"message":"生成失败"}',
            order_index=0,
        )
        session.add(summary)
        session.add(job)
        session.add(item)
        await session.commit()

        panel_response = await _summary_panel_response(session, test_project["id"])
        assert panel_response.status_code == 200
        maintenance = panel_response.json()["maintenance"]
        active_jobs = maintenance["active_jobs"]
        assert len(active_jobs) == 0

        chapter_items = maintenance["missing_or_failed_chapter_summaries"]
        assert chapter_items[0]["chapter_id"] == chapter["id"]
        assert chapter_items[0]["status"] == "failed"

    async def test_panel_uses_persisted_item_counts_instead_of_stage_totals(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        chapter = test_chapters[0]
        session.add(
            ChapterSummary(
                project_id=test_project["id"],
                summary_type="chapter",
                status="running",
                chapter_id=chapter["id"],
                chapter_order=chapter["order"],
                start_order=chapter["order"],
                end_order=chapter["order"],
                job_id="item-summary-panel-counts",
            )
        )
        session.add(
            BackgroundJob(
                id="job-summary-panel-counts",
                type="summary_batch",
                status="running",
                subject_type="project",
                subject_id=test_project["id"],
                payload_json=f'{{"project_id":"{test_project["id"]}"}}',
                context_json=f'{{"project_id":"{test_project["id"]}"}}',
                progress_json='{"current":194,"total":291,"message":"正在生成章节摘要","progress_percent":67,"total_item_count":97,"completed_item_count":23,"running_item_count":1,"queued_item_count":73}',
            )
        )
        session.add(
            BackgroundJobItem(
                id="item-summary-panel-counts",
                job_id="job-summary-panel-counts",
                item_key=f"chapter:{chapter['id']}",
                type="chapter_summary",
                status="running",
                payload_json=f'{{"chapter_id":"{chapter["id"]}"}}',
                progress_json='{"current":2,"total":3,"message":"正在生成章节摘要"}',
                order_index=0,
            )
        )
        await session.commit()

        response = await _summary_panel_response(session, test_project["id"])
        assert response.status_code == 200
        batch_progress = response.json()["maintenance"]["batch_progress"]
        assert batch_progress["total_item_count"] == 97
        assert batch_progress["completed_item_count"] == 23
        assert batch_progress["progress_current"] == 194
        assert batch_progress["progress_total"] == 291
        assert batch_progress["progress_percent"] == 67

    async def test_enqueue_long_term_summary_creates_background_job(
        self, client: AsyncClient, session, test_project: dict
    ):
        chapters = []
        for index in range(LONG_TERM_SUMMARY_INTERVAL):
            response = await client.post(
                f"/api/v1/projects/{test_project['id']}/chapters",
                json={
                    "volume_id": test_project["default_volume_id"],
                    "title": f"第{index + 1}章",
                    "content": "内容",
                    "word_count": 800,
                },
            )
            assert response.status_code == 201
            chapters.append(response.json())

        for chapter in chapters:
            session.add(
                ChapterSummary(
                    project_id=test_project["id"],
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter["id"],
                    chapter_order=chapter["order"],
                    start_order=chapter["order"],
                    end_order=chapter["order"],
                    summary=f"摘要{chapter['order']}",
                    source_content_normalized=_source_content(chapter),
                )
            )
        await session.commit()

        response = await client.post(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/enqueue",
            json={
                "summary_type": "long_term",
                "start_order": 1,
                "end_order": LONG_TERM_SUMMARY_INTERVAL,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["job_id"]
        assert data["item_count"] == 1

    async def test_enqueue_all_summaries_creates_single_batch_job(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        for chapter in test_chapters[:2]:
            session.add(
                ChapterSummary(
                    project_id=test_project["id"],
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter["id"],
                    chapter_order=chapter["order"],
                    start_order=chapter["order"],
                    end_order=chapter["order"],
                    summary=f"摘要{chapter['order']}",
                    source_content_normalized=_source_content(chapter),
                )
            )
        await session.commit()

        response = await client.post(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/enqueue",
            json={"summary_type": "all"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["job_id"]
        assert data["item_count"] >= 1

    async def test_maintenance_uses_fixed_long_term_windows(
        self, client: AsyncClient, session, test_project: dict
    ):
        chapters = []
        for index in range(11):
            response = await client.post(
                f"/api/v1/projects/{test_project['id']}/chapters",
                json={
                    "volume_id": test_project["default_volume_id"],
                    "title": f"第{index + 1}章",
                    "content": "内容",
                    "word_count": 800,
                },
            )
            assert response.status_code == 201
            chapters.append(response.json())

        for chapter in chapters[1:]:
            session.add(
                ChapterSummary(
                    project_id=test_project["id"],
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter["id"],
                    chapter_order=chapter["order"],
                    start_order=chapter["order"],
                    end_order=chapter["order"],
                    summary=f"摘要{chapter['order']}",
                    source_content_normalized=_source_content(chapter),
                )
            )
        await session.commit()

        panel_response = await _summary_panel_response(session, test_project["id"])
        assert panel_response.status_code == 200
        maintenance = panel_response.json()["maintenance"]
        assert maintenance["missing_or_failed_long_term_summaries"] == []

        session.add(
            ChapterSummary(
                project_id=test_project["id"],
                summary_type="chapter",
                status=SUMMARY_STATUS_READY,
                chapter_id=chapters[0]["id"],
                chapter_order=chapters[0]["order"],
                start_order=chapters[0]["order"],
                end_order=chapters[0]["order"],
                summary="摘要1",
                source_content_normalized=_source_content(chapters[0]),
            )
        )
        await session.commit()

        panel_response = await _summary_panel_response(session, test_project["id"])
        assert panel_response.status_code == 200
        missing_long_terms = panel_response.json()["maintenance"]["missing_or_failed_long_term_summaries"]
        assert missing_long_terms == [
            {
                "start_order": 1,
                "end_order": LONG_TERM_SUMMARY_INTERVAL,
                "status": "not_generated",
                "is_stale": False,
                "summary_id": None,
                "progress_message": None,
            }
        ]

    async def test_long_term_range_ignores_skipped_short_chapters(
        self, client: AsyncClient, session, test_project: dict
    ):
        chapters = []
        for index in range(LONG_TERM_SUMMARY_INTERVAL):
            word_count = 120 if index in {1, 4} else 900
            response = await client.post(
                f"/api/v1/projects/{test_project['id']}/chapters",
                json={
                    "volume_id": test_project["default_volume_id"],
                    "title": f"第{index + 1}章",
                    "content": f"内容{index + 1}",
                    "word_count": word_count,
                },
            )
            assert response.status_code == 201
            chapters.append(response.json())

        for chapter in chapters:
            if chapter["word_count"] < MIN_CHAPTER_SUMMARY_WORD_COUNT:
                continue
            session.add(
                ChapterSummary(
                    project_id=test_project["id"],
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter["id"],
                    chapter_order=chapter["order"],
                    start_order=chapter["order"],
                    end_order=chapter["order"],
                    summary=f"摘要{chapter['order']}",
                    source_content_normalized=_source_content(chapter),
                )
            )
        await session.commit()

        panel_response = await _summary_panel_response(session, test_project["id"])
        assert panel_response.status_code == 200
        assert panel_response.json()["maintenance"]["missing_or_failed_long_term_summaries"] == [
            {
                "start_order": 1,
                "end_order": LONG_TERM_SUMMARY_INTERVAL,
                "status": "not_generated",
                "is_stale": False,
                "summary_id": None,
                "progress_message": None,
            }
        ]

        enqueue_response = await client.post(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/enqueue",
            json={
                "summary_type": "long_term",
                "start_order": 1,
                "end_order": LONG_TERM_SUMMARY_INTERVAL,
            },
        )
        assert enqueue_response.status_code == 200
        assert enqueue_response.json()["status"] == "queued"

    async def test_maintenance_surfaces_running_long_term_range(
        self, client: AsyncClient, session, test_project: dict
    ):
        chapters = []
        for index in range(LONG_TERM_SUMMARY_INTERVAL):
            response = await client.post(
                f"/api/v1/projects/{test_project['id']}/chapters",
                json={
                    "volume_id": test_project["default_volume_id"],
                    "title": f"第{index + 1}章",
                    "content": "内容",
                    "word_count": 800,
                },
            )
            assert response.status_code == 201
            chapters.append(response.json())

        for chapter in chapters:
            session.add(
                ChapterSummary(
                    project_id=test_project["id"],
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter["id"],
                    chapter_order=chapter["order"],
                    start_order=chapter["order"],
                    end_order=chapter["order"],
                    summary=f"摘要{chapter['order']}",
                    source_content_normalized=_source_content(chapter),
                )
            )

        session.add(
            ChapterSummary(
                project_id=test_project["id"],
                summary_type=SUMMARY_TYPE_LONG_TERM,
                status="running",
                start_order=1,
                end_order=LONG_TERM_SUMMARY_INTERVAL,
                job_id="item-long-term-1",
            )
        )
        session.add(
            BackgroundJob(
                id="job-long-term-1",
                type="summary_batch",
                status="running",
                subject_type="project",
                subject_id=test_project["id"],
                payload_json=f'{{"project_id":"{test_project["id"]}"}}',
                context_json=f'{{"project_id":"{test_project["id"]}"}}',
                progress_json='{"current":4,"total":10,"message":"处理中","progress_percent":40,"total_item_count":1,"completed_item_count":0,"running_item_count":1,"queued_item_count":0}',
            )
        )
        session.add(
            BackgroundJobItem(
                id="item-long-term-1",
                job_id="job-long-term-1",
                item_key=f"long_term:1:{LONG_TERM_SUMMARY_INTERVAL}",
                type="long_term_summary",
                status="running",
                payload_json=(
                    f'{{"project_id":"{test_project["id"]}",'
                    f'"start_order":1,"end_order":{LONG_TERM_SUMMARY_INTERVAL}}}'
                ),
                progress_json='{"current":4,"total":10,"message":"正在聚合区间摘要"}',
                order_index=0,
            )
        )
        await session.commit()

        panel_response = await _summary_panel_response(session, test_project["id"])
        assert panel_response.status_code == 200
        items = panel_response.json()["maintenance"]["missing_or_failed_long_term_summaries"]
        assert items == [
            {
                "start_order": 1,
                "end_order": LONG_TERM_SUMMARY_INTERVAL,
                "status": "running",
                "is_stale": False,
                "summary_id": items[0]["summary_id"],
                "progress_message": "正在聚合区间摘要",
            }
        ]

    async def test_long_term_summary_list_includes_existing_summary_rows_only(
        self, client: AsyncClient, session, test_project: dict
    ):
        chapters = []
        for index in range(22):
            response = await client.post(
                f"/api/v1/projects/{test_project['id']}/chapters",
                json={
                    "volume_id": test_project["default_volume_id"],
                    "title": f"第{index + 1}章",
                    "content": "内容",
                    "word_count": 800,
                },
            )
            assert response.status_code == 201
            chapters.append(response.json())

        for chapter in chapters[:20]:
            session.add(
                ChapterSummary(
                    project_id=test_project["id"],
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter["id"],
                    chapter_order=chapter["order"],
                    start_order=chapter["order"],
                    end_order=chapter["order"],
                    summary=f"摘要{chapter['order']}",
                    source_content_normalized=_source_content(chapter),
                )
            )
        session.add(
            ChapterSummary(
                project_id=test_project["id"],
                summary_type=SUMMARY_TYPE_LONG_TERM,
                status=SUMMARY_STATUS_READY,
                start_order=1,
                end_order=10,
                start_time="第1天",
                end_time="第10天",
                summary="区间摘要1-10",
                token_count=12,
            )
        )
        await session.commit()

        response = await client.get(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/long-term"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"] == [
            {
                "start_order": 1,
                "end_order": 10,
                "status": "ready",
                "is_stale": True,
                "summary_id": data["items"][0]["summary_id"],
                "start_time": "第1天",
                "end_time": "第10天",
                "summary": "区间摘要1-10",
                "error_message": None,
                "updated_at": data["items"][0]["updated_at"],
            },
        ]

    async def test_long_term_summary_list_returns_only_existing_summary_rows(
        self, client: AsyncClient, session, test_project: dict
    ):
        chapters = []
        for index in range(22):
            response = await client.post(
                f"/api/v1/projects/{test_project['id']}/chapters",
                json={
                    "volume_id": test_project["default_volume_id"],
                    "title": f"第{index + 1}章",
                    "content": "内容",
                    "word_count": 800,
                },
            )
            assert response.status_code == 201
            chapters.append(response.json())

        for chapter in chapters[:20]:
            session.add(
                ChapterSummary(
                    project_id=test_project["id"],
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter["id"],
                    chapter_order=chapter["order"],
                    start_order=chapter["order"],
                    end_order=chapter["order"],
                    summary=f"摘要{chapter['order']}",
                    source_content_normalized=_source_content(chapter),
                )
            )
        session.add(
            ChapterSummary(
                project_id=test_project["id"],
                summary_type=SUMMARY_TYPE_LONG_TERM,
                status=SUMMARY_STATUS_READY,
                start_order=1,
                end_order=10,
                start_time="第1天",
                end_time="第10天",
                summary="区间摘要1-10",
                token_count=12,
            )
        )
        await session.commit()

        response = await client.get(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/long-term"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"] == [
            {
                "start_order": 1,
                "end_order": 10,
                "status": "ready",
                "is_stale": True,
                "summary_id": data["items"][0]["summary_id"],
                "start_time": "第1天",
                "end_time": "第10天",
                "summary": "区间摘要1-10",
                "error_message": None,
                "updated_at": data["items"][0]["updated_at"],
            }
        ]

    async def test_long_term_summary_list_surfaces_failed_range(
        self, client: AsyncClient, session, test_project: dict
    ):
        chapters = []
        for index in range(10):
            response = await client.post(
                f"/api/v1/projects/{test_project['id']}/chapters",
                json={
                    "volume_id": test_project["default_volume_id"],
                    "title": f"第{index + 1}章",
                    "content": "内容",
                    "word_count": 800,
                },
            )
            assert response.status_code == 201
            chapters.append(response.json())

        for chapter in chapters:
            session.add(
                ChapterSummary(
                    project_id=test_project["id"],
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter["id"],
                    chapter_order=chapter["order"],
                    start_order=chapter["order"],
                    end_order=chapter["order"],
                    summary=f"摘要{chapter['order']}",
                    source_content_normalized=_source_content(chapter),
                )
            )
        session.add(
            ChapterSummary(
                project_id=test_project["id"],
                summary_type=SUMMARY_TYPE_LONG_TERM,
                status=SUMMARY_STATUS_FAILED,
                start_order=1,
                end_order=10,
                error_message="聚合失败",
            )
        )
        await session.commit()

        response = await client.get(
            f"/api/v1/projects/{test_project['id']}/chapter-context/summaries/long-term"
        )
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["start_order"] == 1
        assert item["end_order"] == 10
        assert item["status"] == "failed"
        assert item["error_message"] == "聚合失败"

    async def test_creating_new_chapter_does_not_stale_existing_summaries(
        self, client: AsyncClient, session, test_project: dict, test_chapters: list[dict]
    ):
        for chapter in test_chapters:
            session.add(
                ChapterSummary(
                    project_id=test_project["id"],
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter["id"],
                    chapter_order=chapter["order"],
                    start_order=chapter["order"],
                    end_order=chapter["order"],
                    summary=f"摘要{chapter['order']}",
                    source_content_normalized=_source_content(chapter),
                )
            )
        await session.commit()

        response = await client.post(
            f"/api/v1/projects/{test_project['id']}/chapters",
            json={
                "volume_id": test_project["default_volume_id"],
                "title": "新章节",
                "content": "新内容",
                "word_count": 800,
            },
        )
        assert response.status_code == 201

        panel_response = await _summary_panel_response(session, test_project["id"])
        assert panel_response.status_code == 200
        missing = panel_response.json()["maintenance"]["missing_or_failed_chapter_summaries"]
        assert [item["chapter_order"] for item in missing] == [6]
        assert missing[0]["status"] == "not_generated"


@pytest.mark.asyncio
class TestContextBuilder:
    async def test_get_context(
        self, client: AsyncClient, test_project: dict, test_chapters: list[dict]
    ):
        response = await client.get(
            f"/api/v1/projects/{test_project['id']}/chapter-context/context",
            params={"chapter_id": test_chapters[4]["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "latest_field" in data
        assert "near_field" in data
        assert "mid_field" in data
        assert "far_field" in data

    async def test_context_uses_fixed_summary_ranges(
        self, client: AsyncClient, session, test_project: dict
    ):
        chapters = []
        for index in range(25):
            response = await client.post(
                f"/api/v1/projects/{test_project['id']}/chapters",
                json={
                    "volume_id": test_project["default_volume_id"],
                    "title": f"第{index + 1}章",
                    "content": f"正文{index + 1}",
                    "word_count": 800,
                },
            )
            assert response.status_code == 201
            chapters.append(response.json())

        for chapter in chapters:
            session.add(
                ChapterSummary(
                    project_id=test_project["id"],
                    summary_type="chapter",
                    status=SUMMARY_STATUS_READY,
                    chapter_id=chapter["id"],
                    chapter_order=chapter["order"],
                    start_order=chapter["order"],
                    end_order=chapter["order"],
                    summary=f"摘要{chapter['order']}",
                    token_count=1,
                    source_content_normalized=_source_content(chapter),
                )
            )
        session.add(
            ChapterSummary(
                project_id=test_project["id"],
                summary_type=SUMMARY_TYPE_LONG_TERM,
                status=SUMMARY_STATUS_READY,
                start_order=1,
                end_order=5,
                summary="远期摘要1-5",
                token_count=1,
            )
        )
        session.add(
            ChapterSummary(
                project_id=test_project["id"],
                summary_type=SUMMARY_TYPE_LONG_TERM,
                status=SUMMARY_STATUS_READY,
                start_order=6,
                end_order=10,
                summary="远期摘要6-10",
                token_count=1,
            )
        )
        await session.commit()

        response = await client.get(
            f"/api/v1/projects/{test_project['id']}/chapter-context/context",
            params={"chapter_id": chapters[24]["id"]},
        )
        assert response.status_code == 200
        data = response.json()

        assert data["latest_field"]["chapter_range"] == [25, 25]
        assert "第25章" in data["latest_field"]["content"]
        assert data["latest_field"]["content"].startswith("{\n  ")
        assert data["near_field"]["chapter_range"] == [16, 24]
        assert data["near_field"]["content"].startswith("[\n  ")
        assert "第15章" not in data["near_field"]["content"]
        assert "第16章" in data["near_field"]["content"]
        assert "第24章" in data["near_field"]["content"]
        assert data["mid_field"]["chapter_range"] == [6, 15]
        assert data["mid_field"]["content"].startswith("[\n  ")
        assert "摘要6" in data["mid_field"]["content"]
        assert "摘要15" in data["mid_field"]["content"]
        assert "摘要16" not in data["mid_field"]["content"]
        assert data["far_field"]["chapter_range"] == [1, 5]
        assert data["far_field"]["content"].startswith("[\n  ")
        assert "远期摘要1-5" in data["far_field"]["content"]
        assert "远期摘要6-10" not in data["far_field"]["content"]

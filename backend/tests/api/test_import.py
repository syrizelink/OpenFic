# -*- coding: utf-8 -*-
"""
Import API 测试。
"""

import io
import json
import zipfile

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_preview_txt_simple(client: AsyncClient) -> None:
    """测试预览简单 TXT 文件（无章节标题）。"""
    content = "这是一段简单的文本内容。\n没有标题，只有正文。"
    files = {"file": ("test.txt", content.encode("utf-8"), "text/plain")}

    response = await client.post("/api/v1/import/preview", files=files)
    assert response.status_code == 200
    data = response.json()

    assert data["chapter_count"] >= 1
    assert data["total_word_count"] > 0
    assert data["detected_encoding"] == "utf-8"
    assert len(data["volumes"]) == 1
    assert len(data["volumes"][0]["chapters"]) >= 1


@pytest.mark.asyncio
async def test_preview_txt_with_chapters(client: AsyncClient) -> None:
    """测试预览带章节标题的 TXT 文件。"""
    # 每章内容足够长以满足解析器的间隔要求
    ch1 = "我本想当个平常人，谁知道命运弄人。" * 30
    ch2 = "新的一天开始了，难题也跟着来了。" * 30
    ch3 = "经历了很多，终于走到了结局。" * 30
    content = f"""第一章 开始

{ch1}

第二章 发展

{ch2}

第三章 结局

{ch3}
"""
    files = {"file": ("novel.txt", content.encode("utf-8"), "text/plain")}

    response = await client.post("/api/v1/import/preview", files=files)
    assert response.status_code == 200
    data = response.json()

    assert data["chapter_count"] >= 2  # 至少解析出 2 个章节
    assert data["total_word_count"] > 0
    # 验证章节标题包含关键字
    titles = [
        chapter["title"] for volume in data["volumes"] for chapter in volume["chapters"]
    ]
    assert any("第一章" in t for t in titles)
    assert any("第二章" in t for t in titles)


@pytest.mark.asyncio
async def test_preview_txt_chapter_format_2(client: AsyncClient) -> None:
    """测试数字分隔符格式的章节标题。"""
    # 每章内容足够长以满足解析器的间隔要求
    ch1 = "故事的开始总是充满期待和悬念。" * 30
    ch2 = "这一天终于来了，主角醒来了。" * 30
    ch3 = "全部结束了，这就是结局。" * 30
    content = f"""1、序言

{ch1}

2、第一天

{ch2}

3、结束

{ch3}
"""
    files = {"file": ("novel.txt", content.encode("utf-8"), "text/plain")}

    response = await client.post("/api/v1/import/preview", files=files)
    assert response.status_code == 200
    data = response.json()

    assert data["chapter_count"] >= 2  # 数字分隔符格式


@pytest.mark.asyncio
async def test_preview_empty_file(client: AsyncClient) -> None:
    """测试空文件处理。"""
    files = {"file": ("empty.txt", b"", "text/plain")}

    response = await client.post("/api/v1/import/preview", files=files)
    assert response.status_code == 400
    assert "空" in response.json()["detail"]


@pytest.mark.asyncio
async def test_preview_invalid_file_type(client: AsyncClient) -> None:
    """测试无效文件类型。"""
    files = {"file": ("test.pdf", b"fake pdf content", "application/pdf")}

    response = await client.post("/api/v1/import/preview", files=files)
    assert response.status_code == 400
    assert "txt" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_confirm_import(client: AsyncClient) -> None:
    """测试确认导入流程。"""
    # 每个章节内容需要足够长以满足解析器的间隔要求
    chapter1_content = "这是序章的内容，描述故事的背景。" * 30  # 约 600 字符
    chapter2_content = "主角踏上了冒险的旅程，开始了漫长的征途。" * 30  # 约 600 字符
    content = f"""第一章 序章

{chapter1_content}

第二章 冒险开始

{chapter2_content}
"""
    files = {
        "file": ("novel.txt", content.encode("utf-8"), "text/plain"),
    }
    data = {
        "title": "测试小说",
        "description": "这是一本测试小说",
    }

    response = await client.post("/api/v1/import/confirm", files=files, data=data)
    assert response.status_code == 201
    result = response.json()

    assert result["title"] == "测试小说"
    assert result["chapter_count"] >= 1  # 至少有一个章节
    assert result["total_word_count"] > 0
    assert "project_id" in result

    # 验证项目已创建
    project_id = result["project_id"]
    project_response = await client.get(f"/api/v1/projects/{project_id}")
    assert project_response.status_code == 200
    project = project_response.json()
    assert project["title"] == "测试小说"

    # 验证章节已创建
    chapters_response = await client.get(f"/api/v1/projects/{project_id}/chapters")
    assert chapters_response.status_code == 200
    tree = chapters_response.json()
    assert tree["total_chapters"] >= 1
    assert len(tree["volumes"]) == 1
    volume = tree["volumes"][0]
    assert volume["title"] == "第一卷"
    assert volume["chapter_count"] == tree["total_chapters"]
    assert len(volume["chapters"]) >= 1
    assert all(chapter["volume_id"] == volume["id"] for chapter in volume["chapters"])


@pytest.mark.asyncio
async def test_import_txt_with_volume_titles(client: AsyncClient) -> None:
    """卷标题与下一目录标题之间没有正文时，应按卷导入章节。"""
    first_chapter = "第一卷的第一章正文。" * 60
    second_chapter = "第一卷的第二章正文。" * 60
    third_chapter = "第二卷的第一章正文。" * 60
    content = f"""第一卷 初入江湖
第一章 出山

{first_chapter}

第二章 相逢

{second_chapter}

第二卷 风云再起
第一章 入城

{third_chapter}
"""
    files = {"file": ("volumes.txt", content.encode("utf-8"), "text/plain")}

    preview_response = await client.post("/api/v1/import/preview", files=files)

    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert [volume["title"] for volume in preview["volumes"]] == [
        "第一卷 初入江湖",
        "第二卷 风云再起",
    ]
    assert [chapter["title"] for chapter in preview["volumes"][0]["chapters"]] == [
        "第一章 出山",
        "第二章 相逢",
    ]
    assert [chapter["title"] for chapter in preview["volumes"][1]["chapters"]] == [
        "第一章 入城",
    ]
    assert preview["chapter_count"] == 3

    import_response = await client.post(
        "/api/v1/import/confirm",
        files=files,
        data={"title": "分卷测试小说"},
    )

    assert import_response.status_code == 201
    project_id = import_response.json()["project_id"]
    tree_response = await client.get(f"/api/v1/projects/{project_id}/chapters")

    assert tree_response.status_code == 200
    volumes = tree_response.json()["volumes"]
    assert [volume["title"] for volume in volumes] == [
        "第一卷 初入江湖",
        "第二卷 风云再起",
    ]
    assert [volume["chapter_count"] for volume in volumes] == [2, 1]
    assert [chapter["order"] for chapter in volumes[0]["chapters"]] == [1, 2]
    assert [chapter["order"] for chapter in volumes[1]["chapters"]] == [1]


@pytest.mark.asyncio
async def test_preview_creates_explicit_volume_when_following_chapter_is_unrecognized(
    client: AsyncClient,
) -> None:
    """显式卷标题后的未识别章节也应归入新卷。"""
    first_chapter = "第一章正文。" * 200
    second_chapter = "未命名章节正文。" * 200
    content = f"""第一卷 第一卷
前言
作品简介

第一章 灵眸少年（一）

{first_chapter}

第二卷 未命名卷
未命名章节

{second_chapter}
"""
    files = {"file": ("explicit-volumes.txt", content.encode("utf-8"), "text/plain")}

    response = await client.post("/api/v1/import/preview", files=files)

    assert response.status_code == 200
    preview = response.json()
    assert [volume["title"] for volume in preview["volumes"]] == [
        "第一卷 第一卷",
        "第二卷 未命名卷",
    ]
    assert [chapter["title"] for chapter in preview["volumes"][0]["chapters"]] == [
        "前言",
        "第一章 灵眸少年（一）",
    ]
    assert [chapter["title"] for chapter in preview["volumes"][1]["chapters"]] == [
        "未命名章节",
    ]


@pytest.mark.asyncio
async def test_confirm_import_empty_title(client: AsyncClient) -> None:
    """测试导入时标题为空。"""
    content = "简单内容"
    files = {"file": ("novel.txt", content.encode("utf-8"), "text/plain")}
    data = {"title": ""}

    response = await client.post("/api/v1/import/confirm", files=files, data=data)
    # 422 是 Pydantic 验证错误，400 是业务验证错误，两者都可接受
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_confirm_import_rejects_over_limit_content_before_project_creation(
    client: AsyncClient,
) -> None:
    projects_before = (await client.get("/api/v1/projects")).json()["total"]
    files = {
        "file": (
            "over-limit.txt",
            ("内容" * 100001).encode("utf-8"),
            "text/plain",
        )
    }

    response = await client.post(
        "/api/v1/import/confirm",
        files=files,
        data={"title": "超限导入"},
    )

    assert response.status_code == 400
    assert "内容超出限制" in response.json()["detail"]
    projects_after = (await client.get("/api/v1/projects")).json()["total"]
    assert projects_after == projects_before


@pytest.mark.asyncio
async def test_confirm_import_stream_rejects_over_limit_chapter_before_project_creation(
    client: AsyncClient,
) -> None:
    projects_before = (await client.get("/api/v1/projects")).json()["total"]
    content = "\n".join(["内容" * 51, *("内容" for _ in range(2000))])

    response = await client.post(
        "/api/v1/import/confirm-stream",
        files={"file": ("over-limit.txt", content.encode("utf-8"), "text/plain")},
        data={"title": "超限流式导入"},
    )

    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    error_event = next(event for event in events if event["type"] == "error")
    assert error_event["type"] == "error"
    assert "内容超出限制" in error_event["message"]
    projects_after = (await client.get("/api/v1/projects")).json()["total"]
    assert projects_after == projects_before


@pytest.mark.asyncio
async def test_preview_gbk_encoding(client: AsyncClient) -> None:
    """测试 GBK 编码文件的检测和解析。"""
    content = "第一章 中文测试\n\n这是中文内容。"
    gbk_content = content.encode("gbk")
    files = {"file": ("gbk_novel.txt", gbk_content, "text/plain")}

    response = await client.post("/api/v1/import/preview", files=files)
    assert response.status_code == 200
    data = response.json()

    # GBK 编码应该被检测到并正确解析
    assert data["chapter_count"] >= 1
    # 包含 gb 系列编码或 utf-8（小文件可能识别不准）
    enc = data["detected_encoding"].lower()
    assert "gb" in enc or enc == "utf-8" or enc == "ascii"


@pytest.mark.asyncio
async def test_preview_gb18030_preserves_original_text(client: AsyncClient) -> None:
    """测试 GB18030 编码文件预览时不会出现乱码。"""
    content = "第一章 扩展字符测试\n\n这里有扩展字：𠮷。"
    gb18030_content = content.encode("gb18030")
    files = {"file": ("gb18030_novel.txt", gb18030_content, "text/plain")}

    response = await client.post("/api/v1/import/preview", files=files)
    assert response.status_code == 200
    data = response.json()

    assert data["detected_encoding"].lower() == "gb18030"
    assert data["volumes"][0]["chapters"][0]["title"] == "第一章 扩展字符测试"
    assert data["volumes"][0]["chapters"][0]["content_preview"] == "这里有扩展字：𠮷。"


def _build_zip(entries: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for filename, content in entries:
            archive.writestr(filename, content)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_preview_markdown_file(client: AsyncClient) -> None:
    content = "# Markdown 标题\n\n这是 Markdown 正文。"
    response = await client.post(
        "/api/v1/import/preview",
        files={"file": ("novel.md", content.encode("utf-8"), "text/markdown")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["chapter_count"] == 1
    chapter = data["volumes"][0]["chapters"][0]
    assert chapter["title"] == "# Markdown 标题"
    assert chapter["content_preview"] == "这是 Markdown 正文。"


@pytest.mark.asyncio
async def test_preview_zip_files_as_chapters_and_folders_as_volumes(
    client: AsyncClient,
) -> None:
    archive_content = _build_zip(
        [
            ("序章.txt", "根目录章节".encode("utf-8")),
            ("卷一/第一章.md", "第一卷章节".encode("utf-8")),
            ("卷一/第二章.txt", "第二章".encode("utf-8")),
            ("封面.png", b"not a text chapter"),
            ("卷二/终章.md", "第二卷章节".encode("utf-8")),
        ]
    )
    response = await client.post(
        "/api/v1/import/preview",
        files={"file": ("novel.zip", archive_content, "application/zip")},
    )

    assert response.status_code == 200
    data = response.json()
    assert [volume["title"] for volume in data["volumes"]] == [
        "第一卷",
        "卷一",
        "卷二",
    ]
    assert [
        chapter["title"]
        for volume in data["volumes"]
        for chapter in volume["chapters"]
    ] == ["序章", "第一章", "第二章", "终章"]
    assert data["chapter_count"] == 4


@pytest.mark.asyncio
async def test_preview_manual_split_uses_chunk_size(client: AsyncClient) -> None:
    content = "段落一\n\n段落二\n\n段落三"
    response = await client.post(
        "/api/v1/import/preview",
        files={"file": ("novel.txt", content.encode("utf-8"), "text/plain")},
        data={"split_mode": "manual", "chunk_size": "10"},
    )

    assert response.status_code == 200
    data = response.json()
    chapters = [chapter for volume in data["volumes"] for chapter in volume["chapters"]]
    assert [chapter["title"] for chapter in chapters] == ["第1章", "第2章"]
    assert [chapter["content_preview"] for chapter in chapters] == [
        "段落一\n\n段落二",
        "段落三",
    ]


@pytest.mark.asyncio
async def test_preview_manual_split_rejects_invalid_chunk_size(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/import/preview",
        files={"file": ("novel.txt", "正文".encode("utf-8"), "text/plain")},
        data={"split_mode": "manual", "chunk_size": "0"},
    )

    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_confirm_import_zip_preserves_archive_structure(client: AsyncClient) -> None:
    archive_content = _build_zip(
        [
            ("root.md", "根章节".encode("utf-8")),
            ("卷一/第一章.txt", "第一章正文".encode("utf-8")),
        ]
    )
    response = await client.post(
        "/api/v1/import/confirm",
        files={"file": ("novel.zip", archive_content, "application/zip")},
        data={"title": "ZIP 导入测试", "split_mode": "manual", "chunk_size": "10"},
    )

    assert response.status_code == 201
    project_id = response.json()["project_id"]
    tree_response = await client.get(f"/api/v1/projects/{project_id}/chapters")

    assert tree_response.status_code == 200
    volumes = tree_response.json()["volumes"]
    assert [volume["title"] for volume in volumes] == ["第一卷", "卷一"]
    assert [chapter["title"] for volume in volumes for chapter in volume["chapters"]] == [
        "root",
        "第一章",
    ]


@pytest.mark.asyncio
async def test_confirm_import_stream_uses_manual_split(client: AsyncClient) -> None:
    content = "段落一\n\n段落二\n\n段落三"
    response = await client.post(
        "/api/v1/import/confirm-stream",
        files={"file": ("novel.txt", content.encode("utf-8"), "text/plain")},
        data={"title": "流式手动分割", "split_mode": "manual", "chunk_size": "10"},
    )

    assert response.status_code == 200
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    complete_event = next(event for event in events if event["type"] == "complete")
    assert complete_event["chapter_count"] == 2


@pytest.mark.asyncio
async def test_preview_corrupt_zip_returns_a_readable_error(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/import/preview",
        files={"file": ("broken.zip", b"not a zip", "application/zip")},
    )

    assert response.status_code == 400
    assert "压缩包" in response.json()["detail"]


@pytest.mark.asyncio
async def test_preview_zip_without_text_files_returns_a_readable_error(
    client: AsyncClient,
) -> None:
    archive_content = _build_zip([("cover.png", b"not a text chapter")])
    response = await client.post(
        "/api/v1/import/preview",
        files={"file": ("images.zip", archive_content, "application/zip")},
    )

    assert response.status_code == 400
    assert "TXT" in response.json()["detail"]

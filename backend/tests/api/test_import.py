# -*- coding: utf-8 -*-
"""
Import API 测试。
"""

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
    assert len(data["chapters"]) >= 1


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
    titles = [ch["title"] for ch in data["chapters"]]
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
async def test_confirm_import_empty_title(client: AsyncClient) -> None:
    """测试导入时标题为空。"""
    content = "简单内容"
    files = {"file": ("novel.txt", content.encode("utf-8"), "text/plain")}
    data = {"title": ""}

    response = await client.post("/api/v1/import/confirm", files=files, data=data)
    # 422 是 Pydantic 验证错误，400 是业务验证错误，两者都可接受
    assert response.status_code in (400, 422)


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
    assert data["chapters"][0]["title"] == "第一章 扩展字符测试"
    assert data["chapters"][0]["content_preview"] == "这里有扩展字：𠮷。"

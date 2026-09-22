import pytest

from app.agent_runtime.attachments import (
    _format_attachment_processing_error,
    build_attachment_content_blocks,
    classify_agent_attachment,
    serialize_agent_attachment,
)


@pytest.mark.parametrize(
    ("file_name", "mime_type", "expected"),
    [
        ("notes.txt", "application/octet-stream", "text"),
        ("Dockerfile", "application/octet-stream", "text"),
        ("records.csv", "text/csv", "csv"),
        ("paper.pdf", "application/pdf", "pdf"),
        ("chapter.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
        ("sheet.xlsx", "application/octet-stream", "unstructured"),
        ("page.html", "text/html", "html"),
        ("unknown.bin", "application/octet-stream", None),
    ],
)
def test_classify_agent_attachment(file_name: str, mime_type: str, expected: str | None) -> None:
    assert classify_agent_attachment(file_name, mime_type) == expected


def test_serialize_agent_attachment_exposes_content_length_without_content() -> None:
    attachment = type(
        "Attachment",
        (),
        {
            "id": "file-1",
            "storage_name": "session/file-1.txt",
            "file_name": "notes.txt",
            "mime_type": "text/plain",
            "size_bytes": 12,
            "content": "hello world!",
            "content_length": 12,
            "line_count": 1,
            "width": None,
            "height": None,
        },
    )()

    assert serialize_agent_attachment(attachment) == {
        "id": "file-1",
        "storage_name": "session/file-1.txt",
        "file_name": "notes.txt",
        "mime_type": "text/plain",
        "size_bytes": 12,
        "content_length": 12,
        "line_count": 1,
        "width": None,
        "height": None,
        "url": "/agent-attachments/session/file-1.txt",
    }


@pytest.mark.parametrize(
    ("error", "expected_message"),
    [
        (FileNotFoundError("libreoffice not found"), "LibreOffice"),
        (ModuleNotFoundError("No module named 'networkx'"), "networkx"),
    ],
)
def test_format_attachment_processing_error_identifies_missing_dependencies(
    error: Exception,
    expected_message: str,
) -> None:
    message = _format_attachment_processing_error(error)

    assert expected_message in message
    assert "管理员" not in message


@pytest.mark.asyncio
async def test_build_attachment_content_blocks_exposes_attachment_error_to_agent() -> None:
    blocks = await build_attachment_content_blocks(
        [
            {
                "id": "failed-attachment",
                "file_name": "book.epub",
                "mime_type": "application/epub+zip",
                "error": "服务器未安装 Pandoc",
            }
        ]
    )

    assert blocks == [
        {
            "type": "text",
            "text": "[附件处理失败: book.epub] 服务器未安装 Pandoc",
        }
    ]

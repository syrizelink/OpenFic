import zipfile

import pytest

from app.core.zip_archive import decode_member_name, is_macos_metadata_path


def _legacy_member(raw_name: bytes) -> zipfile.ZipInfo:
    # zipfile 读取未设置 UTF-8 标志位的条目时，按 CP437 解码文件名
    return zipfile.ZipInfo(raw_name.decode("cp437"))


@pytest.mark.parametrize(
    ("raw_name", "expected"),
    [
        ("卷一/第一章.txt".encode("utf-8"), "卷一/第一章.txt"),
        ("卷一/第一章 开端.txt".encode("gbk"), "卷一/第一章 开端.txt"),
        ("café.txt".encode("cp437"), "café.txt"),
    ],
)
def test_decode_member_name_restores_names_without_utf8_flag(
    raw_name: bytes, expected: str
) -> None:
    assert decode_member_name(_legacy_member(raw_name)) == expected


def test_decode_member_name_keeps_utf8_flagged_name() -> None:
    info = zipfile.ZipInfo("卷一/第一章.txt")
    info.flag_bits |= 0x800

    assert decode_member_name(info) == "卷一/第一章.txt"


def test_decode_member_name_keeps_name_from_unicode_path_extra_field() -> None:
    # zipfile 采用 0x7075 扩展字段时只替换 filename，orig_filename 仍是原始文件名
    info = _legacy_member(b"??/???.txt")
    info.filename = "卷一/第一章.txt"

    assert decode_member_name(info) == "卷一/第一章.txt"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("__MACOSX/卷一/._第一章.txt", True),
        ("小说/__MACOSX/小说/._第一章.txt", True),
        ("卷一/._第一章.txt", True),
        ("卷一/第一章.txt", False),
        ("卷一/.第一章.txt", False),
    ],
)
def test_is_macos_metadata_path(path: str, expected: bool) -> None:
    assert is_macos_metadata_path(path) is expected

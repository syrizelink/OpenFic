# -*- coding: utf-8 -*-
"""ZIP 导入公共处理：还原条目文件名并识别系统压缩附带的元数据文件。"""

import zipfile

_UTF8_NAME_FLAG = 0x800
# 未声明 UTF-8 的文件名：macOS 自带压缩和 zip 命令写入的是未标记的 UTF-8，
# Windows 中文环境的压缩工具通常写入 GBK（GB18030 为其超集）。
_LEGACY_NAME_ENCODINGS = ("utf-8", "gb18030")
_MACOS_METADATA_DIR = "__MACOSX"
_APPLE_DOUBLE_PREFIX = "._"


def decode_member_name(info: zipfile.ZipInfo) -> str:
    """返回 ZIP 条目的真实文件名。

    条目未设置 UTF-8 标志位时，zipfile 一律按 CP437 解码文件名，中文文件名
    会变成乱码；这里取回原始字节重新解码，并沿用 zipfile 对文件名的规范化。
    """
    if info.flag_bits & _UTF8_NAME_FLAG:
        return info.filename
    if info.filename != zipfile.ZipInfo(info.orig_filename).filename:
        # zipfile 已采用 Unicode Path 扩展字段（0x7075）中的 UTF-8 文件名
        return info.filename

    raw_name = info.orig_filename.encode("cp437")
    for encoding in _LEGACY_NAME_ENCODINGS:
        try:
            return zipfile.ZipInfo(raw_name.decode(encoding)).filename
        except UnicodeDecodeError:
            continue
    return info.filename


def is_macos_metadata_path(path: str) -> bool:
    """判断条目是否为 macOS 压缩附带的 __MACOSX 目录或 AppleDouble（._*）文件。"""
    parts = path.split("/")
    return _MACOS_METADATA_DIR in parts or parts[-1].startswith(_APPLE_DOUBLE_PREFIX)

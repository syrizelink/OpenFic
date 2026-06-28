# -*- coding: utf-8 -*-
"""
加密密钥解析回归测试。

历史问题：打包后后端在导入期向 CWD 相对路径 .env 写入加密密钥，
当 CWD 不可写（如 Program Files）时启动即崩溃（“后端服务已退出”）。
此测试确保密钥始终解析到可写的数据目录，且不依赖 CWD。
"""

from pathlib import Path

from cryptography.fernet import Fernet

import app.settings as settings_module
from app.settings import _ensure_encryption_key


def test_env_file_path_resolves_under_data_dir() -> None:
    """ENV_FILE_PATH 必须为绝对路径且位于数据目录下，不依赖 CWD。"""
    assert settings_module.ENV_FILE_PATH.is_absolute()
    assert settings_module.ENV_FILE_PATH.parent == settings_module.BACKEND_DATA_DIR


def test_ensure_encryption_key_writes_to_data_dir_not_cwd(
    monkeypatch, tmp_path: Path
) -> None:
    """全新安装：密钥应写入数据目录，而非 CWD 相对路径。"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(settings_module, "ENV_FILE_PATH", data_dir / ".env")
    monkeypatch.setattr(
        settings_module, "_LEGACY_ENV_FILE_PATH", tmp_path / "no-legacy.env"
    )
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    key = _ensure_encryption_key()

    assert key
    assert (data_dir / ".env").exists(), "密钥应写入数据目录"
    assert not (tmp_path / ".env").exists(), "不应向 CWD 写入 .env"


def test_ensure_encryption_key_reads_legacy_without_overwriting(
    monkeypatch, tmp_path: Path
) -> None:
    """历史位置存在密钥时应直接读取，不写入新位置（保护现有加密数据）。"""
    known_key = Fernet.generate_key().decode()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    legacy = tmp_path / "legacy.env"
    legacy.write_text(f'ENCRYPTION_KEY="{known_key}"\n', encoding="utf-8")
    monkeypatch.setattr(settings_module, "ENV_FILE_PATH", data_dir / ".env")
    monkeypatch.setattr(settings_module, "_LEGACY_ENV_FILE_PATH", legacy)
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

    key = _ensure_encryption_key()

    assert key == known_key
    assert not (data_dir / ".env").exists(), "读取到历史密钥时不应写入新位置"

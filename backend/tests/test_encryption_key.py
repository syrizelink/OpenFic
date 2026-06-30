from pathlib import Path

from cryptography.fernet import Fernet

import app.settings as settings_module
from app.settings import _ensure_encryption_key


def test_env_file_path_resolves_under_data_dir() -> None:
    assert settings_module.ENV_FILE_PATH.is_absolute()
    assert settings_module.ENV_FILE_PATH.parent == settings_module.BACKEND_DATA_DIR


def test_encryption_key_file_path_resolves_under_data_dir() -> None:
    assert settings_module.ENCRYPTION_KEY_FILE_PATH.is_absolute()
    assert settings_module.ENCRYPTION_KEY_FILE_PATH.parent == settings_module.BACKEND_DATA_DIR


def test_ensure_encryption_key_reads_key_file_and_ignores_env(
    monkeypatch, tmp_path: Path
) -> None:
    known_key = Fernet.generate_key().decode()
    key_file = tmp_path / "data" / ".key"
    key_file.parent.mkdir(parents=True)
    key_file.write_text(known_key, encoding="utf-8")
    monkeypatch.setattr(settings_module, "ENCRYPTION_KEY_FILE_PATH", key_file)
    monkeypatch.setenv("ENCRYPTION_KEY", Fernet.generate_key().decode())

    key = _ensure_encryption_key()

    assert key == known_key


def test_ensure_encryption_key_writes_to_key_file_not_cwd(
    monkeypatch, tmp_path: Path
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    key_file = data_dir / ".key"
    monkeypatch.setattr(settings_module, "ENCRYPTION_KEY_FILE_PATH", key_file)
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    key = _ensure_encryption_key()

    assert key
    assert key_file.exists(), "key should be written under the data directory"
    assert key_file.read_text(encoding="utf-8").strip() == key
    assert not (tmp_path / ".key").exists(), "key should not be written to cwd"

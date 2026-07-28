from hashlib import sha256
from pathlib import Path

import tiktoken
import tiktoken.load
import tiktoken.registry
import pytest

from app.core.utils.tiktoken import get_encoding
from app.storage.services import character_service, world_info_entry_service


EXPECTED_ENCODING_HASHES = {
    "cl100k_base": "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7",
    "o200k_base": "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d",
}


class StubEncoding:
    def encode(self, _: str) -> list[int]:
        return list(range(7))


@pytest.mark.parametrize(
    "encoding_name, expected_hash", EXPECTED_ENCODING_HASHES.items()
)
def test_bundles_required_encoding_resource(
    encoding_name: str, expected_hash: str
) -> None:
    resource_path = (
        Path(__file__).parents[2]
        / "app"
        / "core"
        / "resources"
        / "tiktoken"
        / f"{encoding_name}.tiktoken"
    )

    assert resource_path.is_file()
    assert sha256(resource_path.read_bytes()).hexdigest() == expected_hash


@pytest.mark.parametrize("encoding_name", ["cl100k_base", "o200k_base"])
def test_get_encoding_seeds_bundled_resource_for_tiktoken_registry(
    monkeypatch: pytest.MonkeyPatch,
    encoding_name: str,
) -> None:
    monkeypatch.setattr(tiktoken.registry, "ENCODINGS", {})
    native_get_encoding = tiktoken.get_encoding
    requested_encodings: list[str] = []

    def track_native_get_encoding(name: str) -> tiktoken.Encoding:
        requested_encodings.append(name)
        return native_get_encoding(name)

    def fail_if_network_requested(_: str) -> bytes:
        raise AssertionError("bundled encodings must not request network resources")

    monkeypatch.setattr(tiktoken, "get_encoding", track_native_get_encoding)
    monkeypatch.setattr(tiktoken.load, "read_file", fail_if_network_requested)

    encoding = get_encoding(encoding_name)

    assert requested_encodings == [encoding_name]
    assert encoding.name == encoding_name
    assert encoding.encode("OpenFic 离线 Token 计数")


def test_character_token_count_uses_shared_offline_encoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        character_service,
        "get_encoding",
        lambda _: StubEncoding(),
        raising=False,
    )

    assert character_service.calculate_token_count("OpenFic") == 7


def test_world_info_token_count_uses_shared_offline_encoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        world_info_entry_service,
        "get_encoding",
        lambda _: StubEncoding(),
        raising=False,
    )

    assert world_info_entry_service._calculate_token_count("OpenFic") == 7

from app.agent_runtime.agents.tool_categories import (
    LOCAL_ONLY_TOOL_NAMES,
    get_tool_names_for_categories,
)


def test_chapter_read_includes_search_tools_in_cloud_only(monkeypatch) -> None:
    """Pencarian bab tersedia pada mode cloud-only lewat adapter SQLite FTS5."""
    monkeypatch.setattr("app.settings.settings.cloud_only", True)

    names = get_tool_names_for_categories(["chapter_read"])

    assert "list_chapters" in names
    assert "read_chapter" in names
    assert "search_chapters" in names
    assert "update_index" in names


def test_chapter_read_includes_search_tools_in_local_mode(monkeypatch) -> None:
    """Mode biasa memakai LanceDB dan tetap menyediakan tool yang sama."""
    monkeypatch.setattr("app.settings.settings.cloud_only", False)

    names = get_tool_names_for_categories(["chapter_read"])

    assert "search_chapters" in names
    assert "update_index" in names


def test_local_only_tool_names_is_empty() -> None:
    """Tidak ada tool yang khusus lokal setelah adapter FTS5 tersedia."""
    assert LOCAL_ONLY_TOOL_NAMES == frozenset()


def test_tool_names_are_deduplicated_and_ordered() -> None:
    names = get_tool_names_for_categories(["chapter_read", "chapter_read"])

    assert len(names) == len(set(names))
    assert names[0] == "list_volumes"


def test_local_only_names_are_filtered_when_present(monkeypatch) -> None:
    """Penyaringan tetap bekerja bila kelak ada tool khusus lokal."""
    monkeypatch.setattr(
        "app.agent_runtime.agents.tool_categories.LOCAL_ONLY_TOOL_NAMES",
        frozenset({"search_chapters"}),
    )

    names = get_tool_names_for_categories(["chapter_read"])

    assert "search_chapters" not in names
    assert "read_chapter" in names

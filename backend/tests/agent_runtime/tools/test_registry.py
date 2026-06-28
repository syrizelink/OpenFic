from collections.abc import Iterator

import pytest
from pydantic import BaseModel

from app.agent_runtime.tools.base import AgentTool, HookContext, HookResult
from app.agent_runtime.tools.registry import ToolRegistry


class FakeInput(BaseModel):
    x: int


class FakeTool(AgentTool):
    name: str = "fake_tool"
    description: str = "fake"
    access_level: str = "readonly"
    args_schema: type[BaseModel] = FakeInput

    async def _execute(self, x: int) -> str:
        return str(x * 2)


@pytest.fixture(autouse=True)
def _restore_registry() -> Iterator[None]:
    original = dict(ToolRegistry._tools)
    try:
        yield
    finally:
        ToolRegistry._tools = original


def _make_state() -> dict:
    return {
        "session_id": "s1",
        "project_id": "p1",
        "model_config": {},
        "active_agent": None,
        "is_completed": False,
        "error": None,
        "retry_count": 0,
        "message_checkpoints": [],
        "user_request": "",
    }


def test_register_and_list():
    ToolRegistry._tools = {}
    ToolRegistry.register(FakeTool)
    assert "fake_tool" in ToolRegistry.list_names()


def test_get_tools_returns_instances():
    ToolRegistry._tools = {}
    ToolRegistry.register(FakeTool)
    tools = ToolRegistry.get_tools(names=["fake_tool"], state=_make_state())
    assert len(tools) == 1
    assert tools[0].project_id == "p1"


def test_get_tools_all():
    ToolRegistry._tools = {}
    ToolRegistry.register(FakeTool)
    tools = ToolRegistry.get_tools(state=_make_state())
    assert len(tools) == 1


def test_get_tools_with_hooks():
    ToolRegistry._tools = {}
    ToolRegistry.register(FakeTool)

    async def my_hook(ctx: HookContext) -> HookResult:
        return HookResult()

    tools = ToolRegistry.get_tools(
        names=["fake_tool"],
        state=_make_state(),
        pre_hooks=[my_hook],
    )
    assert len(tools[0]._pre_hooks) == 1


def test_get_tools_applies_build_hooks_before_returning_instances():
    ToolRegistry._tools = {}
    ToolRegistry.register(FakeTool)

    def build_hook(tool: AgentTool) -> None:
        tool.description = "built"

    tools = ToolRegistry.get_tools(
        names=["fake_tool"],
        state=_make_state(),
        build_hooks=[build_hook],
    )

    assert tools[0].description == "built"


def test_get_tools_unknown_name_raises():
    ToolRegistry._tools = {}
    with pytest.raises(KeyError):
        ToolRegistry.get_tools(names=["nonexistent"], state=_make_state())


def _collect_schema_property_nodes(
    schema: object,
    *,
    path: str,
) -> list[tuple[str, dict]]:
    if not isinstance(schema, dict):
        return []

    nodes: list[tuple[str, dict]] = []
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for key, value in properties.items():
            if isinstance(value, dict):
                nodes.append((f"{path}.{key}", value))
                nodes.extend(
                    _collect_schema_property_nodes(
                        value,
                        path=f"{path}.{key}",
                    )
                )

    defs = schema.get("$defs")
    if isinstance(defs, dict):
        for key, value in defs.items():
            nodes.extend(
                _collect_schema_property_nodes(
                    value,
                    path=f"{path}.$defs.{key}",
                )
            )

    items = schema.get("items")
    if isinstance(items, dict):
        nodes.extend(_collect_schema_property_nodes(items, path=f"{path}[]"))

    additional_properties = schema.get("additionalProperties")
    if isinstance(additional_properties, dict):
        nodes.extend(
            _collect_schema_property_nodes(
                additional_properties,
                path=f"{path}{{}}",
            )
        )

    for key in ("anyOf", "allOf", "oneOf"):
        variants = schema.get(key)
        if isinstance(variants, list):
            for index, value in enumerate(variants):
                nodes.extend(
                    _collect_schema_property_nodes(
                        value,
                        path=f"{path}.{key}[{index}]",
                    )
                )

    return nodes


def test_registered_tool_args_schema_fields_have_descriptions():
    missing_descriptions: list[str] = []

    for tool in ToolRegistry.get_tools(state=_make_state()):
        schema = tool.args_schema.model_json_schema()
        for path, property_schema in _collect_schema_property_nodes(
            schema,
            path=tool.name,
        ):
            description = property_schema.get("description")
            if isinstance(description, str) and description.strip():
                continue
            missing_descriptions.append(path)

    assert missing_descriptions == []

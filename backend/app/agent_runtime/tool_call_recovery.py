from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha1
from typing import Any, cast

from json_repair import loads as repair_json_loads

from app.agent_runtime.tools.errors import ToolFailure

MALFORMED_TOOL_CALL_MARKER = "__malformed_tool_call__"
MALFORMED_TOOL_CALL_RAW_ARGS = "__raw_args__"
MALFORMED_TOOL_CALL_ERROR = "__parse_error__"
MALFORMED_TOOL_CALL_MESSAGE = "工具参数 JSON 无法解析，未执行工具调用"


def _resolve_schema_ref(
    schema: Mapping[str, Any],
    root_schema: Mapping[str, Any],
) -> Mapping[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return schema

    current: Any = root_schema
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, Mapping) or part not in current:
            return schema
        current = current[part]
    return current if isinstance(current, Mapping) else schema


def _schema_variants(
    schema: Mapping[str, Any],
    root_schema: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    resolved = _resolve_schema_ref(schema, root_schema)
    for union_key in ("anyOf", "oneOf"):
        branches = resolved.get(union_key)
        if isinstance(branches, list):
            variants: list[Mapping[str, Any]] = []
            for branch in branches:
                if isinstance(branch, Mapping):
                    variants.extend(_schema_variants(branch, root_schema))
            return variants
    return [resolved]


def _parse_json_container(value: str) -> Any:
    try:
        parsed = repair_json_loads(value)
    except Exception:
        return value
    return parsed if isinstance(parsed, (Mapping, list)) else value


def _normalize_schema_value(
    value: Any,
    schema: Mapping[str, Any] | None,
    root_schema: Mapping[str, Any],
) -> Any:
    if not isinstance(schema, Mapping):
        return value

    variants = _schema_variants(schema, root_schema)
    accepts_object = any(item.get("type") == "object" for item in variants)
    accepts_array = any(item.get("type") == "array" for item in variants)
    if isinstance(value, str) and (accepts_object or accepts_array):
        value = _parse_json_container(value)

    object_variants = [item for item in variants if item.get("type") == "object"]
    if isinstance(value, Mapping) and object_variants:
        properties: dict[str, Mapping[str, Any]] = {}
        additional_schema: Mapping[str, Any] | None = None
        for variant in object_variants:
            raw_properties = variant.get("properties")
            if isinstance(raw_properties, Mapping):
                properties.update(
                    {
                        str(key): child
                        for key, child in raw_properties.items()
                        if isinstance(child, Mapping)
                    }
                )
            raw_additional = variant.get("additionalProperties")
            if isinstance(raw_additional, Mapping):
                additional_schema = raw_additional

        normalized: dict[str, Any] = {}
        for key, item in value.items():
            child_schema = properties.get(str(key), additional_schema)
            normalized[key] = _normalize_schema_value(
                item,
                child_schema,
                root_schema,
            )
        return normalized

    if isinstance(value, list):
        item_schemas = [
            item_schema
            for variant in variants
            if variant.get("type") == "array"
            for item_schema in [variant.get("items")]
            if isinstance(item_schema, Mapping)
        ]
        if item_schemas:
            item_schema: Mapping[str, Any]
            if len(item_schemas) == 1:
                item_schema = item_schemas[0]
            else:
                item_schema = {"anyOf": item_schemas}
            return [
                _normalize_schema_value(item, item_schema, root_schema)
                for item in value
            ]

    return value


def normalize_tool_input_for_schema(
    tool_input: Any,
    args_schema: Any,
) -> Any:
    """Parse JSON-encoded nested containers only where the schema expects them.

    Some model providers encode an object or array-valued tool argument as a
    JSON string. Normalize those values before Pydantic validates the tool
    input, while leaving ordinary string fields such as note content intact.
    """
    if not isinstance(tool_input, Mapping):
        return tool_input

    schema_builder = getattr(args_schema, "model_json_schema", None)
    if not callable(schema_builder):
        schema_builder = getattr(args_schema, "schema", None)
    if not callable(schema_builder):
        return dict(tool_input)

    try:
        schema = schema_builder()
    except Exception:
        return dict(tool_input)
    if not isinstance(schema, Mapping):
        return dict(tool_input)

    normalized = _normalize_schema_value(dict(tool_input), schema, schema)
    return normalized if isinstance(normalized, dict) else dict(tool_input)


def parse_tool_args(args_raw: Any) -> dict[str, Any] | None:
    if args_raw is None:
        return {}
    if isinstance(args_raw, Mapping):
        return dict(args_raw)
    if not isinstance(args_raw, str):
        return None
    if not args_raw.strip():
        return {}

    try:
        parsed = repair_json_loads(args_raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def synthesize_tool_call_id(
    *,
    index: int,
    id_seed: str | None = None,
    name: str | None = None,
) -> str:
    seed = f"{id_seed or 'default'}:{index}:{name or ''}"
    return f"call_{sha1(seed.encode('utf-8')).hexdigest()[:16]}"


def _malformed_args_payload(raw_args: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        MALFORMED_TOOL_CALL_MARKER: True,
        MALFORMED_TOOL_CALL_ERROR: MALFORMED_TOOL_CALL_MESSAGE,
    }
    if isinstance(raw_args, str):
        payload[MALFORMED_TOOL_CALL_RAW_ARGS] = raw_args
    return payload


def _recover_one_tool_call(
    raw_tool_call: Mapping[str, Any],
    *,
    index: int,
    id_seed: str | None = None,
    args_value: Any | None = None,
) -> dict[str, Any] | None:
    name = raw_tool_call.get("name")
    if not isinstance(name, str) or not name:
        return None

    tool_call_id = raw_tool_call.get("id")
    if not isinstance(tool_call_id, str) or not tool_call_id:
        tool_call_id = synthesize_tool_call_id(
            index=index,
            id_seed=id_seed,
            name=name,
        )

    raw_args = raw_tool_call.get("args") if args_value is None else args_value
    args = parse_tool_args(raw_args)
    if args is None:
        args = _malformed_args_payload(raw_args)

    return {"id": tool_call_id, "name": name, "args": args}


def recover_tool_calls(
    raw_tool_calls: Any,
    *,
    id_seed: str | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(raw_tool_calls, list):
        return []

    recovered: list[dict[str, Any]] = []
    for index, raw_tool_call in enumerate(raw_tool_calls):
        if not isinstance(raw_tool_call, Mapping):
            continue
        recovered_tool_call = _recover_one_tool_call(
            cast(Mapping[str, Any], raw_tool_call),
            index=index,
            id_seed=id_seed,
        )
        if recovered_tool_call is not None:
            recovered.append(recovered_tool_call)
    return recovered


def recover_message_tool_calls(
    message: object | None,
    *,
    id_seed: str | None = None,
) -> list[dict[str, Any]]:
    tool_calls = recover_tool_calls(
        getattr(message, "tool_calls", None),
        id_seed=id_seed,
    )
    invalid_tool_calls = recover_tool_calls(
        getattr(message, "invalid_tool_calls", None),
        id_seed=id_seed,
    )

    if not invalid_tool_calls:
        return tool_calls
    if not tool_calls:
        return invalid_tool_calls

    seen: set[tuple[str, str]] = {
        (str(tool_call.get("id") or ""), str(tool_call.get("name") or ""))
        for tool_call in tool_calls
    }
    merged = list(tool_calls)
    for tool_call in invalid_tool_calls:
        key = (str(tool_call.get("id") or ""), str(tool_call.get("name") or ""))
        if key in seen:
            continue
        seen.add(key)
        merged.append(tool_call)
    return merged


def reconcile_tool_call_chunks(
    chunks: Mapping[int, Mapping[str, Any]],
    *,
    id_seed: str | None = None,
) -> list[dict[str, Any]]:
    recovered: list[dict[str, Any]] = []
    for index in sorted(chunks):
        chunk = chunks[index]
        if not isinstance(chunk, Mapping):
            continue
        recovered_tool_call = _recover_one_tool_call(
            chunk,
            index=index,
            id_seed=id_seed,
            args_value=chunk.get("args_text"),
        )
        if recovered_tool_call is not None:
            recovered.append(recovered_tool_call)
    return recovered


def is_malformed_tool_call(tool_call: Mapping[str, Any]) -> bool:
    args = tool_call.get("args")
    return isinstance(args, Mapping) and bool(args.get(MALFORMED_TOOL_CALL_MARKER))


def tool_call_input(tool_call: Mapping[str, Any]) -> Any:
    args = tool_call.get("args")
    if not isinstance(args, Mapping):
        return None
    if bool(args.get(MALFORMED_TOOL_CALL_MARKER)):
        raw_args = args.get(MALFORMED_TOOL_CALL_RAW_ARGS)
        return raw_args if isinstance(raw_args, str) else None
    return dict(args)


def build_malformed_tool_call_error(tool_call: Mapping[str, Any]) -> dict[str, Any]:
    return ToolFailure(
        code="malformed_tool_call",
        message=MALFORMED_TOOL_CALL_MESSAGE,
        trace={"source": "tool_call_recovery"},
    ).to_result()

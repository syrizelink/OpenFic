import json
import math
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context.compaction.config import (
    AUTO_TRIGGER_RATIO,
    MIN_COMPACTABLE_TOKENS,
    TAIL_TOKEN_BUDGET,
    TAIL_WINDOW_RATIO,
)
from app.agent_runtime.context.pruning import PRUNE_MINIMUM_TOKENS, PRUNE_PROTECTED_TOKENS
from app.models.clients.model_params import (
    DEFAULT_REASONING_EFFORT,
    ReasoningEffort,
    normalize_reasoning_effort,
)
from app.storage.repos import setting_repo

SESSION_MODEL_REFERENCE = "__session_model__"
DEFAULT_MODEL_REFERENCE = "__system_default_model__"
LIGHT_MODEL_REFERENCE = "__system_light_model__"


@dataclass(frozen=True)
class ContextSettings:
    auto_compact_context: bool = True
    compaction_model: str = SESSION_MODEL_REFERENCE
    compaction_model_reasoning_effort: ReasoningEffort = DEFAULT_REASONING_EFFORT
    compaction_trigger_ratio: float = AUTO_TRIGGER_RATIO
    compaction_tail_token_budget: int = TAIL_TOKEN_BUDGET
    compaction_tail_window_ratio: float = TAIL_WINDOW_RATIO
    compaction_min_compactable_tokens: int = MIN_COMPACTABLE_TOKENS
    auto_prune_tool_outputs: bool = False
    prune_protected_tokens: int = PRUNE_PROTECTED_TOKENS
    prune_minimum_tokens: int = PRUNE_MINIMUM_TOKENS


def parse_context_settings(raw: Mapping[str, str]) -> ContextSettings:
    defaults = ContextSettings()

    def boolean(key: str) -> bool:
        try:
            value = json.loads(raw[key])
            return value if isinstance(value, bool) else getattr(defaults, key)
        except (KeyError, ValueError):
            return getattr(defaults, key)

    def number(key: str, default: int | float, *, maximum: float | None = None) -> int | float:
        try:
            value = type(default)(raw[key])
        except (KeyError, ValueError, OverflowError):
            return default
        if not math.isfinite(value) or value <= 0 or (maximum is not None and value > maximum):
            return default
        return value

    model = raw.get("compaction_model", SESSION_MODEL_REFERENCE)
    if not model.strip():
        model = SESSION_MODEL_REFERENCE
    return ContextSettings(
        auto_compact_context=boolean("auto_compact_context"),
        compaction_model=model,
        compaction_model_reasoning_effort=normalize_reasoning_effort(
            raw.get("compaction_model_reasoning_effort")
        ),
        compaction_trigger_ratio=number("compaction_trigger_ratio", AUTO_TRIGGER_RATIO, maximum=1),
        compaction_tail_token_budget=int(number("compaction_tail_token_budget", TAIL_TOKEN_BUDGET)),
        compaction_tail_window_ratio=number("compaction_tail_window_ratio", TAIL_WINDOW_RATIO, maximum=1),
        compaction_min_compactable_tokens=int(number("compaction_min_compactable_tokens", MIN_COMPACTABLE_TOKENS)),
        auto_prune_tool_outputs=boolean("auto_prune_tool_outputs"),
        prune_protected_tokens=int(number("prune_protected_tokens", PRUNE_PROTECTED_TOKENS)),
        prune_minimum_tokens=int(number("prune_minimum_tokens", PRUNE_MINIMUM_TOKENS)),
    )


async def load_context_settings(session: AsyncSession) -> ContextSettings:
    rows = await setting_repo.get_all(session)
    return parse_context_settings({row.key: row.value for row in rows})

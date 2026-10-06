"""Global configuration for structured chapter summaries."""

import json
from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.clients.model_params import (
    DEFAULT_REASONING_EFFORT,
    ReasoningEffort,
    normalize_reasoning_effort,
)



SUMMARY_MODEL_POLICY = "summary_model"
SUMMARY_DEFAULT_MODEL_REFERENCE = "__system_default_model__"
SUMMARY_LIGHT_MODEL_REFERENCE = "__system_light_model__"

SETTING_KEY_SUMMARY_MODEL = "summary_model"
SETTING_KEY_SUMMARY_MODEL_REASONING_EFFORT = "summary_model_reasoning_effort"
SETTING_KEY_SUMMARY_AUTO_GENERATE_CHAPTER = "summary_auto_generate_chapter"
SETTING_KEY_SUMMARY_AUTO_GENERATE_LONG_TERM = "summary_auto_generate_long_term"
SETTING_KEY_SUMMARY_MIN_CHAPTER_WORD_COUNT = "summary_min_chapter_word_count"
SETTING_KEY_SUMMARY_BATCH_SIZE = "summary_batch_size"
SETTING_KEY_SUMMARY_LONG_TERM_INTERVAL = "summary_long_term_interval"
SETTING_KEY_SUMMARY_CHAPTER_TARGET_LENGTH = "summary_chapter_target_length"
SETTING_KEY_SUMMARY_LONG_TERM_TARGET_LENGTH = "summary_long_term_target_length"

DEFAULT_SUMMARY_MODEL = SUMMARY_LIGHT_MODEL_REFERENCE
DEFAULT_SUMMARY_AUTO_GENERATE_CHAPTER = True
DEFAULT_SUMMARY_AUTO_GENERATE_LONG_TERM = True
DEFAULT_SUMMARY_MIN_CHAPTER_WORD_COUNT = 500
DEFAULT_SUMMARY_BATCH_SIZE = 10
DEFAULT_SUMMARY_LONG_TERM_INTERVAL = 10
DEFAULT_SUMMARY_CHAPTER_TARGET_LENGTH = 200
DEFAULT_SUMMARY_LONG_TERM_TARGET_LENGTH = 500


@dataclass(frozen=True)
class SummarySettings:
    """Resolved global summary settings."""

    model_id: str = DEFAULT_SUMMARY_MODEL
    model_reasoning_effort: ReasoningEffort = DEFAULT_REASONING_EFFORT
    auto_generate_chapter: bool = DEFAULT_SUMMARY_AUTO_GENERATE_CHAPTER
    auto_generate_long_term: bool = DEFAULT_SUMMARY_AUTO_GENERATE_LONG_TERM
    min_chapter_word_count: int = DEFAULT_SUMMARY_MIN_CHAPTER_WORD_COUNT
    batch_size: int = DEFAULT_SUMMARY_BATCH_SIZE
    long_term_interval: int = DEFAULT_SUMMARY_LONG_TERM_INTERVAL
    chapter_target_length: int = DEFAULT_SUMMARY_CHAPTER_TARGET_LENGTH
    long_term_target_length: int = DEFAULT_SUMMARY_LONG_TERM_TARGET_LENGTH


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return default
    return parsed if isinstance(parsed, bool) else default


def _parse_positive_int(value: str | None, default: int, *, minimum: int = 1) -> int:
    try:
        parsed = int(value) if value is not None and value != "" else default
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= minimum else default


def parse_summary_settings(raw_settings: Mapping[str, str]) -> SummarySettings:
    """Resolve stored setting values, falling back to safe defaults."""
    model_id = raw_settings.get(SETTING_KEY_SUMMARY_MODEL, DEFAULT_SUMMARY_MODEL).strip()
    if not model_id:
        model_id = DEFAULT_SUMMARY_MODEL
    return SummarySettings(
        model_id=model_id,
        model_reasoning_effort=normalize_reasoning_effort(
            raw_settings.get(SETTING_KEY_SUMMARY_MODEL_REASONING_EFFORT)
        ),
        auto_generate_chapter=_parse_bool(
            raw_settings.get(SETTING_KEY_SUMMARY_AUTO_GENERATE_CHAPTER),
            DEFAULT_SUMMARY_AUTO_GENERATE_CHAPTER,
        ),
        auto_generate_long_term=_parse_bool(
            raw_settings.get(SETTING_KEY_SUMMARY_AUTO_GENERATE_LONG_TERM),
            DEFAULT_SUMMARY_AUTO_GENERATE_LONG_TERM,
        ),
        min_chapter_word_count=_parse_positive_int(
            raw_settings.get(SETTING_KEY_SUMMARY_MIN_CHAPTER_WORD_COUNT),
            DEFAULT_SUMMARY_MIN_CHAPTER_WORD_COUNT,
            minimum=0,
        ),
        batch_size=_parse_positive_int(
            raw_settings.get(SETTING_KEY_SUMMARY_BATCH_SIZE),
            DEFAULT_SUMMARY_BATCH_SIZE,
        ),
        long_term_interval=_parse_positive_int(
            raw_settings.get(SETTING_KEY_SUMMARY_LONG_TERM_INTERVAL),
            DEFAULT_SUMMARY_LONG_TERM_INTERVAL,
        ),
        chapter_target_length=_parse_positive_int(
            raw_settings.get(SETTING_KEY_SUMMARY_CHAPTER_TARGET_LENGTH),
            DEFAULT_SUMMARY_CHAPTER_TARGET_LENGTH,
        ),
        long_term_target_length=_parse_positive_int(
            raw_settings.get(SETTING_KEY_SUMMARY_LONG_TERM_TARGET_LENGTH),
            DEFAULT_SUMMARY_LONG_TERM_TARGET_LENGTH,
        ),
    )


async def load_summary_settings(session: AsyncSession) -> SummarySettings:
    """Load the current global summary settings."""
    from app.storage.repos import setting_repo

    settings = await setting_repo.get_all(session)
    return parse_summary_settings({setting.key: setting.value for setting in settings})


async def resolve_summary_model_id(
    session: AsyncSession,
    model_id: str | None = None,
) -> str | None:
    """Resolve the configured summary model reference before queueing a task."""
    if model_id:
        return model_id

    from app.storage.repos import setting_repo

    summary_settings = await load_summary_settings(session)
    if summary_settings.model_id == SUMMARY_DEFAULT_MODEL_REFERENCE:
        setting = await setting_repo.get_by_key(session, "default_model")
        return setting.value.strip() if setting and setting.value else None
    if summary_settings.model_id == SUMMARY_LIGHT_MODEL_REFERENCE:
        light_model = await setting_repo.get_by_key(session, "light_model")
        if light_model and light_model.value:
            return light_model.value.strip()
        default_model = await setting_repo.get_by_key(session, "default_model")
        return default_model.value.strip() if default_model and default_model.value else None
    return summary_settings.model_id or None

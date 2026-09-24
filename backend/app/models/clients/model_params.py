from typing import Final, Literal, TypeVar, cast


ReasoningEffort = Literal["auto", "low", "medium", "high", "xhigh", "max"]
ReasoningEffortInput = Literal["auto", "off", "low", "medium", "high", "xhigh", "max"]

DEFAULT_TEMPERATURE: Final = 1.0
DEFAULT_TOP_P: Final = 1.0
DEFAULT_TOP_K: Final = 0
DEFAULT_FREQUENCY_PENALTY: Final = 0.0
DEFAULT_PRESENCE_PENALTY: Final = 0.0
DEFAULT_REPETITION_PENALTY: Final = 1.0
DEFAULT_MIN_P: Final = 0.0
DEFAULT_TOP_A: Final = 0.0
DEFAULT_CONTEXT_LENGTH: Final = 128_000
MAX_CONTEXT_LENGTH: Final = 2_000_000
DEFAULT_REASONING_EFFORT: Final[ReasoningEffort] = "medium"

REASONING_EFFORT_VALUES: Final[frozenset[str]] = frozenset(
    {"auto", "low", "medium", "high", "xhigh", "max"}
)

T = TypeVar("T")


def is_non_default(value: object, default: object) -> bool:
    return value != default


def with_default(value: T | None, default: T) -> T:
    return default if value is None else value


def normalize_reasoning_effort(
    value: object,
    default: ReasoningEffort = DEFAULT_REASONING_EFFORT,
) -> ReasoningEffort:
    if value == "off":
        return "auto"
    if isinstance(value, str) and value in REASONING_EFFORT_VALUES:
        return cast(ReasoningEffort, value)
    return default

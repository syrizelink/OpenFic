from dataclasses import dataclass
from typing import Literal

from langchain_core.tools import BaseTool

DEFAULT_AGENT_MAX_ITERATIONS = 1000
DEFAULT_AGENT_RECURSION_LIMIT = 1000


@dataclass
class TerminationCondition:
    mode: Literal["tool_success", "no_tool_call"]
    tool_name: str | None = None


@dataclass
class ReactAgentConfig:
    name: str
    tools: list[BaseTool]
    termination: TerminationCondition
    max_iterations: int = DEFAULT_AGENT_MAX_ITERATIONS

import pytest
from langchain_core.tools import tool


@pytest.fixture
def dummy_tool():
    @tool
    def add_numbers(a: int, b: int) -> int:
        """Add two numbers together."""
        return a + b
    return add_numbers


@pytest.fixture
def submit_tool():
    @tool
    def submit_result(result: str) -> str:
        """Submit the final result to end the agent loop."""
        return f"Submitted: {result}"
    return submit_result

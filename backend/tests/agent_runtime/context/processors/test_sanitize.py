from app.agent_runtime.context.processors.sanitize import sanitize_surrogates
from app.agent_runtime.context.types import ContextMessage


def test_strips_surrogate_codepoints() -> None:
    bad = "hello\ud800world\udfff!"
    parts = [ContextMessage(role="user", content=bad)]
    out = sanitize_surrogates(parts)
    assert out[0].content == "helloworld!"


def test_keeps_normal_text_unchanged() -> None:
    parts = [ContextMessage(role="user", content="正常中文 + emoji 🚀")]
    out = sanitize_surrogates(parts)
    assert out[0].content == "正常中文 + emoji 🚀"


def test_handles_empty_content() -> None:
    parts = [ContextMessage(role="assistant", content="")]
    out = sanitize_surrogates(parts)
    assert out[0].content == ""


def test_does_not_mutate_inputs() -> None:
    original = ContextMessage(role="user", content="x\ud800y")
    out = sanitize_surrogates([original])
    assert original.content == "x\ud800y"
    assert out[0].content == "xy"

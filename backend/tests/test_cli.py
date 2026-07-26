from unittest.mock import Mock

import app.cli as cli


def test_configure_asyncio_event_loop_policy_uses_selector_on_windows(monkeypatch) -> None:
    class FakeSelectorPolicy:
        pass

    set_event_loop_policy = Mock()
    monkeypatch.setattr(cli.sys, "platform", "win32")
    monkeypatch.setattr(
        cli.asyncio,
        "WindowsSelectorEventLoopPolicy",
        FakeSelectorPolicy,
        raising=False,
    )
    monkeypatch.setattr(cli.asyncio, "set_event_loop_policy", set_event_loop_policy)

    cli._configure_asyncio_event_loop_policy()

    set_event_loop_policy.assert_called_once()
    assert isinstance(set_event_loop_policy.call_args.args[0], FakeSelectorPolicy)

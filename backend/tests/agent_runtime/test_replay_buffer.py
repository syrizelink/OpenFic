from app.agent_runtime.streaming.replay_buffer import AgentEventReplayBuffer


def test_replay_buffer_keeps_only_latest_active_retry_event() -> None:
    buffer = AgentEventReplayBuffer()

    buffer.record_unlocked(
        "agent:retry",
        {
            "session_id": "session-1",
            "node": "writer",
            "attempt": 2,
            "error_message": "temporary failure",
        },
    )
    buffer.record_unlocked(
        "agent:token",
        {
            "session_id": "session-1",
            "run_id": "run-1",
            "content": "partial output",
        },
    )
    buffer.record_unlocked(
        "agent:retry",
        {
            "session_id": "session-1",
            "node": "writer",
            "attempt": 3,
            "error_message": "still failing",
        },
    )

    replayed = buffer.replay_events_unlocked("session-1")

    assert [(event.name, event.data.get("attempt")) for event in replayed] == [
        ("agent:token", None),
        ("agent:retry", 3),
    ]


def test_replay_buffer_can_clear_active_retry_event_without_touching_stream_events() -> None:
    buffer = AgentEventReplayBuffer()

    buffer.record_unlocked(
        "agent:token",
        {
            "session_id": "session-1",
            "run_id": "run-1",
            "content": "partial output",
        },
    )
    buffer.record_unlocked(
        "agent:retry",
        {
            "session_id": "session-1",
            "node": "writer",
            "attempt": 2,
            "error_message": "temporary failure",
        },
    )

    buffer.clear_event_unlocked("session-1", "agent:retry")

    replayed = buffer.replay_events_unlocked("session-1")

    assert [(event.name, event.data.get("content")) for event in replayed] == [
        ("agent:token", "partial output"),
    ]


def test_replay_buffer_uses_parent_session_id_for_subagent_status_and_deduplicates_child_run() -> None:
    buffer = AgentEventReplayBuffer()

    buffer.record_unlocked(
        "agent:subagent_status",
        {
            "parent_session_id": "parent-1",
            "child_run_id": "child-1",
            "child_thread_id": "thread-1",
            "agent_key": "writer",
            "status": "running",
            "queued_messages": 1,
            "is_active": True,
        },
    )
    buffer.record_unlocked(
        "agent:subagent_status",
        {
            "parent_session_id": "parent-1",
            "child_run_id": "child-1",
            "child_thread_id": "thread-1",
            "agent_key": "writer",
            "status": "completed",
            "queued_messages": 0,
            "is_active": True,
        },
    )
    buffer.record_unlocked(
        "agent:subagent_status",
        {
            "parent_session_id": "parent-1",
            "child_run_id": "child-2",
            "child_thread_id": "thread-2",
            "agent_key": "reviewer",
            "status": "waiting_user",
            "queued_messages": 0,
            "is_active": True,
        },
    )

    replayed = buffer.replay_events_unlocked("parent-1")

    assert [(event.data["child_run_id"], event.data["status"]) for event in replayed] == [
        ("child-1", "completed"),
        ("child-2", "waiting_user"),
    ]


def test_replay_buffer_records_compaction_events() -> None:
    buffer = AgentEventReplayBuffer()

    buffer.record_unlocked(
        "agent:compaction_start",
        {
            "session_id": "session-1",
            "task_id": "task-1",
            "trigger": "manual",
            "start_seq": 0,
            "end_seq": 2,
            "source_input_tokens": 500,
        },
    )
    buffer.record_unlocked(
        "agent:compaction_success",
        {
            "session_id": "session-2",
            "task_id": "task-1",
            "compaction_id": "cmp-1",
            "trigger": "manual",
            "start_seq": 0,
            "end_seq": 2,
            "source_input_tokens": 500,
            "summary_tokens": 42,
        },
    )
    buffer.record_unlocked(
        "agent:compaction_error",
        {
            "session_id": "session-3",
            "task_id": "task-1",
            "trigger": "manual",
            "code": "llm_error",
            "message": "压缩失败，当前请求已中止",
        },
    )

    replayed_start = buffer.replay_events_unlocked("session-1")
    replayed_success = buffer.replay_events_unlocked("session-2")
    replayed_error = buffer.replay_events_unlocked("session-3")

    assert [event.name for event in replayed_start] == ["agent:compaction_start"]
    assert [(event.name, event.data.get("summary")) for event in replayed_success] == [
        ("agent:compaction_success", None),
    ]
    assert [event.name for event in replayed_error] == ["agent:compaction_error"]


def test_replay_buffer_compaction_terminal_events_clear_active_start() -> None:
    buffer = AgentEventReplayBuffer()

    buffer.record_unlocked(
        "agent:compaction_start",
        {
            "session_id": "session-1",
            "task_id": "task-1",
            "trigger": "manual",
            "start_seq": 0,
            "end_seq": 2,
            "source_input_tokens": 500,
        },
    )
    buffer.record_unlocked(
        "agent:token",
        {
            "session_id": "session-1",
            "run_id": "run-1",
            "content": "partial output",
        },
    )
    buffer.record_unlocked(
        "agent:compaction_success",
        {
            "session_id": "session-1",
            "task_id": "task-1",
            "compaction_id": "cmp-1",
            "trigger": "manual",
            "start_seq": 0,
            "end_seq": 2,
            "source_input_tokens": 500,
            "summary_tokens": 42,
        },
    )
    buffer.record_unlocked(
        "agent:compaction_start",
        {
            "session_id": "session-2",
            "task_id": "task-2",
            "trigger": "manual",
            "start_seq": 3,
            "end_seq": 5,
            "source_input_tokens": 700,
        },
    )
    buffer.record_unlocked(
        "agent:compaction_error",
        {
            "session_id": "session-2",
            "task_id": "task-2",
            "trigger": "manual",
            "code": "llm_error",
            "message": "压缩失败，当前请求已中止",
        },
    )

    replayed_success = buffer.replay_events_unlocked("session-1")
    replayed_error = buffer.replay_events_unlocked("session-2")

    assert [(event.name, event.data.get("summary")) for event in replayed_success] == [
        ("agent:token", None),
        ("agent:compaction_success", None),
    ]
    assert [event.name for event in replayed_error] == [
        "agent:compaction_error",
    ]

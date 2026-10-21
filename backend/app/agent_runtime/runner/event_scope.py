SUBAGENT_CHILD_EVENT_TAG = "subagent_child"
COMPACTION_EVENT_TAG = "context_compaction"


def is_compaction_event(event: dict) -> bool:
    tags = event.get("tags")
    return isinstance(tags, list) and COMPACTION_EVENT_TAG in tags


def is_subagent_child_event(event: dict) -> bool:
    tags = event.get("tags")
    return isinstance(tags, list) and SUBAGENT_CHILD_EVENT_TAG in tags

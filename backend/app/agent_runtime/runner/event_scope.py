SUBAGENT_CHILD_EVENT_TAG = "subagent_child"


def is_subagent_child_event(event: dict) -> bool:
    tags = event.get("tags")
    return isinstance(tags, list) and SUBAGENT_CHILD_EVENT_TAG in tags

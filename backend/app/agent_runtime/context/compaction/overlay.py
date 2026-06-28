from app.agent_runtime.context.types import ContextMessage
from app.agent_runtime.persistence.compaction_types import PersistedCompaction


def _seq(message: ContextMessage) -> int | None:
    seq = (message.metadata or {}).get("seq")
    if type(seq) is int:
        return seq
    return None


def _summary_message(compaction: PersistedCompaction) -> ContextMessage:
    return ContextMessage(
        role="user",
        content=f"<compaction-summary>\n{compaction.summary}\n</compaction-summary>",
        metadata={"part": "history", "compaction_id": compaction.id},
    )


def apply_compaction_overlay(
    history_messages: list[ContextMessage],
    compactions: list[PersistedCompaction],
) -> list[ContextMessage]:
    sorted_compactions = sorted(compactions, key=lambda item: item.start_seq)
    output: list[ContextMessage] = []
    compaction_index = 0
    inserted_compaction_ids: set[str] = set()

    for message in history_messages:
        seq = _seq(message)
        if seq is None:
            output.append(message)
            continue

        while (
            compaction_index < len(sorted_compactions)
            and sorted_compactions[compaction_index].end_seq < seq
        ):
            skipped = sorted_compactions[compaction_index]
            if skipped.id not in inserted_compaction_ids:
                output.append(_summary_message(skipped))
                inserted_compaction_ids.add(skipped.id)
            compaction_index += 1

        if compaction_index >= len(sorted_compactions):
            output.append(message)
            continue

        current = sorted_compactions[compaction_index]
        if current.start_seq <= seq <= current.end_seq:
            if current.id not in inserted_compaction_ids:
                output.append(_summary_message(current))
                inserted_compaction_ids.add(current.id)
            continue

        output.append(message)

    while compaction_index < len(sorted_compactions):
        remaining = sorted_compactions[compaction_index]
        if remaining.id not in inserted_compaction_ids:
            output.append(_summary_message(remaining))
            inserted_compaction_ids.add(remaining.id)
        compaction_index += 1

    return output

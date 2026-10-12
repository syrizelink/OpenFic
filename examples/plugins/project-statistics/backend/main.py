"""Installable plugin: all aggregation lives here, outside OpenFic's core."""


async def projects(context, params):
    return await context.data.list_projects()


async def statistics(context, params):
    project_id = params.get("projectId")
    if not isinstance(project_id, str) or not project_id:
        raise ValueError("Choose a project first")
    entities = await context.data.project_entities(project_id)
    chapters = entities["chapters"]
    total_words = sum(chapter["word_count"] for chapter in chapters)
    target = context.settings["targetWords"]
    volumes = []
    if context.settings["showVolumes"]:
        for volume in entities["volumes"]:
            members = [chapter for chapter in chapters if chapter["volume_id"] == volume["id"]]
            volumes.append({"title": volume["title"], "chapters": len(members), "words": sum(chapter["word_count"] for chapter in members)})
    return {
        "project": entities["project"],
        "words": total_words,
        "chapters": len(chapters),
        "volumes": len(entities["volumes"]),
        "characters": len(entities["characters"]),
        "worldEntries": len(entities["world_entries"]),
        "enabledWorldEntries": sum(entry["is_enabled"] for entry in entities["world_entries"]),
        "notes": len(entities["notes"]),
        "averageChapterWords": round(total_words / len(chapters)) if chapters else 0,
        "targetWords": target,
        "progress": min(round(total_words / target * 100, 1), 100),
        "volumeDistribution": volumes,
    }


def register(host):
    host.register_command("projects.list", projects)
    host.register_command("statistics.get", statistics)

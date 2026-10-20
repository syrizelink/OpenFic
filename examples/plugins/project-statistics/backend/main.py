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
            members = [
                chapter for chapter in chapters if chapter["volume_id"] == volume["id"]
            ]
            volumes.append(
                {
                    "title": volume["title"],
                    "chapters": len(members),
                    "words": sum(chapter["word_count"] for chapter in members),
                }
            )
    return {
        "project": entities["project"],
        "words": total_words,
        "chapters": len(chapters),
        "volumes": len(entities["volumes"]),
        "characters": len(entities["characters"]),
        "worldEntries": len(entities["world_entries"]),
        "enabledWorldEntries": sum(
            entry["is_enabled"] for entry in entities["world_entries"]
        ),
        "notes": len(entities["notes"]),
        "averageChapterWords": round(total_words / len(chapters)) if chapters else 0,
        "targetWords": target,
        "progress": min(round(total_words / target * 100, 1), 100),
        "volumeDistribution": volumes,
    }


def ui_node(kind, children=None, **props):
    node = {"type": kind, "props": props, "children": children}
    if kind in {"Input", "TextArea"} and props.get("label"):
        return {
            "type": "Flex",
            "props": {"direction": "column", "gap": "2", "minWidth": "0"},
            "children": [
                {
                    "type": "Text",
                    "props": {"size": "2", "weight": "medium"},
                    "children": props["label"],
                },
                node,
            ],
        }
    return node


UI_CSS = """
:scope { --example-accent: var(--accent-9); }
.example-page { width: 100%; max-width: 1100px; margin: 0 auto; min-width: 0; }
.example-panel { padding: 20px; min-width: 0; }
.example-title { color: var(--accent-11); }
.example-actions { flex-wrap: wrap; }
.example-output { display: block; white-space: pre-wrap; overflow-wrap: anywhere; max-height: 24rem; overflow: auto; }
.example-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.example-metric strong { display: block; font-size: 26px; margin-top: 8px; }
.example-table { overflow-x: auto; }
.example-conflict { border: 1px solid var(--orange-7); padding: 12px; border-radius: 8px; }
.example-compact { padding: 8px; }
@media (max-width: 640px) {
  .example-panel { padding: 12px; }
  .example-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .example-actions > button { flex: 1 1 auto; }
}
"""


def ui_button(title, action, **props):
    return ui_node("Button", title, onPress=action, **props)


def ui_row(*children):
    return ui_node(
        "Flex", list(children), gap="3", align="center", className="example-actions"
    )


def ui_panel(*children):
    return ui_node(
        "Card",
        ui_node("Flex", list(children), direction="column", gap="4"),
        className="example-panel",
    )


def ui_status(state):
    return ui_node(
        "Text",
        state.get("status", ""),
        id="status",
        role="status",
        size="2",
        color="gray",
    )


def ui_document(*children, compact=False):
    return {
        "css": UI_CSS,
        "tree": ui_node(
            "Flex",
            list(children),
            direction="column",
            gap="4",
            **{
                "className": "example-page" + (" example-compact" if compact else ""),
            },
        ),
    }


async def ui_state(ctx, params, global_default=False):
    context = params.get("context", {})
    key = (
        "ui:"
        + params.get("viewId", "main")
        + ":"
        + str(context.get("projectId") or "global")
    )
    state = await ctx.storage.get(key, {})
    if "project" not in state:
        projects = await ctx.data.list_projects()
        state["project"] = context.get("projectId") or (
            "" if global_default or not projects else projects[0]["id"]
        )
    return key, state


async def ui_render(ctx, params):
    _, state = await ui_state(ctx, params)
    english = not params.get("context", {}).get("language", "zh").startswith("zh")

    def t(zh, en):
        return en if english else zh

    controls = ui_row(
        ui_node(
            "ProjectSelector",
            label=t("选择项目", "Select project"),
            value=state["project"],
            onChange="project",
        ),
        ui_button(t("刷新", "Refresh"), "refresh", variant="soft"),
    )
    children = [
        ui_node(
            "Heading", t("项目统计", "Project statistics"), className="example-title"
        ),
        controls,
    ]
    if not state["project"]:
        return ui_document(
            *children,
            ui_node(
                "Text",
                t("暂无项目，请先创建项目。", "Create a project to see statistics."),
            ),
        )
    data = await statistics(ctx, {"projectId": state["project"]})
    metrics = [
        (t("总字数", "Words"), "words"),
        (t("章节", "Chapters"), "chapters"),
        (t("卷", "Volumes"), "volumes"),
        (t("角色", "Characters"), "characters"),
        (t("世界书条目", "World entries"), "worldEntries"),
        (t("笔记", "Notes"), "notes"),
        (t("平均章节字数", "Average chapter words"), "averageChapterWords"),
        (t("启用世界书条目", "Enabled world entries"), "enabledWorldEntries"),
    ]
    children += [
        ui_node("Heading", data["project"]["title"], size="4"),
        ui_node(
            "Grid",
            [
                ui_node(
                    "Card",
                    [
                        ui_node("Text", title, size="2", color="gray"),
                        ui_node("Strong", f"{data[field]:,}"),
                    ],
                    className="example-metric",
                    **{"data-testid": "metric-" + field},
                )
                for title, field in metrics
            ],
            id="metrics",
            className="example-metrics",
        ),
    ]
    children.append(
        ui_panel(
            ui_node("Heading", t("写作目标", "Writing goal"), size="3"),
            ui_node(
                "Progress",
                value=data["progress"],
                label=t("写作目标进度", "Writing goal progress"),
            ),
            ui_node(
                "Text",
                f"{data['words']:,} / {data['targetWords']:,} · {data['progress']:g}%",
                id="goal",
            ),
        )
    )
    if data["volumeDistribution"]:
        rows = [
            ui_node(
                "Table.Row",
                [
                    ui_node("Table.Cell", str(value))
                    for value in [
                        volume["title"],
                        volume["chapters"],
                        f"{volume['words']:,}",
                        f"{volume['words'] / data['words'] * 100 if data['words'] else 0:.1f}%",
                    ]
                ],
            )
            for volume in data["volumeDistribution"]
        ]
        children.append(
            ui_panel(
                ui_node("Heading", t("各卷统计", "Volume distribution"), size="3"),
                ui_node(
                    "Box",
                    ui_node(
                        "Table.Root",
                        [
                            ui_node(
                                "Table.Header",
                                ui_node(
                                    "Table.Row",
                                    [
                                        ui_node("Table.ColumnHeaderCell", title)
                                        for title in [
                                            t("卷", "Volume"),
                                            t("章节", "Chapters"),
                                            t("字数", "Words"),
                                            t("占比", "Share"),
                                        ]
                                    ],
                                ),
                            ),
                            ui_node("Table.Body", rows, id="volume-body"),
                        ],
                    ),
                    className="example-table",
                ),
            )
        )
    children.append(
        ui_node(
            "Text",
            t("项目最后更新：", "Project updated: ") + data["project"]["updated_at"],
            size="1",
            color="gray",
        )
    )
    return ui_document(*children)


async def ui_action(ctx, params):
    key, state = await ui_state(ctx, params)
    if params["id"] == "project":
        state["project"] = params["value"]
    elif params["id"] != "refresh":
        raise ValueError("Unknown UI action")
    await ctx.storage.set(key, state)


def register(host):
    host.register_command("ui.render", ui_render)
    host.register_command("ui.action", ui_action)
    host.register_command("projects.list", projects)
    host.register_command("statistics.get", statistics)

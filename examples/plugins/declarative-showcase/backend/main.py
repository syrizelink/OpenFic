"""Native project components, compound Radix controls and scoped CSS, without JS."""

import json


def c(kind, children=None, **props):
    return {"type": kind, "props": props, "children": children}


async def render(context, params):
    state = await context.storage.get("state", {})
    return {
        "css": """
            :scope { --showcase-color: rgb(109, 40, 217); }
            .showcase-title { color: var(--showcase-color); @media (min-width: 600px) { letter-spacing: 1px; } }
            .showcase-dialog { border: 3px solid rgb(13, 148, 136); }
            .showcase-menu { border: 3px solid rgb(13, 148, 136); }
            .showcase-animated { animation: showcase-pulse 2s infinite; }
            @keyframes showcase-pulse { from { opacity: .8; } to { opacity: 1; } }
        """,
        "tree": c(
            "Flex",
            [
                c(
                    "Heading",
                    "Native UI showcase",
                    size={"initial": "4", "md": "6"},
                    className="showcase-title",
                ),
                c(
                    "Code",
                    "Code attributes and CSS",
                    className="showcase-code",
                    color="violet",
                    variant="outline",
                    style={"font-size": "14px"},
                ),
                c(
                    "Grid",
                    [
                        c(
                            "ModelSelector",
                            label="Model",
                            placeholder="Select a model",
                            value=state.get("model", ""),
                            onChange="model",
                            editable=False,
                        ),
                        c(
                            "ProjectSelector",
                            label="Project",
                            placeholder="Select a project",
                            value=state.get("project", ""),
                            onChange="project",
                        ),
                    ],
                    columns={"initial": "1", "sm": "2"},
                    gap="3",
                    **{"data-testid": "responsive-grid"},
                ),
                c(
                    "Flex",
                    [
                        c("Spinner", size=18, label="Project spinner"),
                        c("Radix.Spinner", size="2", label="Radix spinner"),
                        c(
                            "CircularProgress",
                            value=70,
                            size=24,
                            ariaLabel="Project progress",
                        ),
                        c("Badge", "Scoped animation", className="showcase-animated"),
                    ],
                    gap="3",
                    align="center",
                ),
                c(
                    "UnitTextField",
                    value=state.get("unit", ""),
                    unit="words",
                    label="Word target",
                    onChange="unit",
                ),
                c(
                    "StepperNumberInput",
                    value=state.get("stepper", 3),
                    onCommit="stepper",
                    min=0,
                    max=10,
                ),
                c(
                    "SearchableSelect",
                    label="Search choices",
                    role="group",
                    **{"data-testid": "search-control", "aria-label": "Search control"},
                    value=state.get("search", ""),
                    options=[
                        {"value": "alpha", "label": "Alpha"},
                        {"value": "beta", "label": "Beta"},
                    ],
                    onChange="search",
                ),
                c(
                    "Slider",
                    value=state.get("range", [20]),
                    min=0,
                    max=100,
                    step=5,
                    onValueCommit="range",
                    label="Range",
                ),
                c(
                    "CheckboxGroup.Root",
                    [
                        c("CheckboxGroup.Item", "First choice", value="first"),
                        c("CheckboxGroup.Item", "Second choice", value="second"),
                    ],
                    value=state.get("choices", []),
                    onValueChange="choices",
                ),
                c(
                    "TextArea",
                    value=state.get("description", ""),
                    placeholder="Description",
                    label="Description",
                    rows=3,
                    resize="vertical",
                    variant="soft",
                    onChange="description",
                ),
                c(
                    "TextField.Root",
                    [c("TextField.Slot", "Prefix", side="left")],
                    placeholder="Compound field",
                    label="Compound field",
                ),
                c(
                    "Radix.Select.Root",
                    [
                        c(
                            "Radix.Select.Trigger",
                            placeholder="Choose native option",
                            label="Native select",
                        ),
                        c(
                            "Radix.Select.Content",
                            [
                                c("Radix.Select.Item", "Native first", value="one"),
                                c("Radix.Select.Item", "Native second", value="two"),
                            ],
                            position="popper",
                            sideOffset=8,
                        ),
                    ],
                    value=state.get("native_select", ""),
                    onValueChange="native_select",
                ),
                c(
                    "RadioGroup.Root",
                    [
                        c("RadioGroup.Item", "Radio first", value="one"),
                        c("RadioGroup.Item", "Radio second", value="two"),
                    ],
                    value=state.get("radio", "one"),
                    onValueChange="radio",
                    orientation="horizontal",
                ),
                c(
                    "Tabs.Root",
                    [
                        c(
                            "Tabs.List",
                            [
                                c("Tabs.Trigger", "Overview", value="overview"),
                                c("Tabs.Trigger", "Details", value="details"),
                            ],
                        ),
                        c("Tabs.Content", "Overview panel", value="overview"),
                        c("Tabs.Content", "Details panel", value="details"),
                    ],
                    defaultValue="overview",
                ),
                c(
                    "Dialog.Root",
                    [
                        c(
                            "Dialog.Trigger",
                            c(
                                "Button",
                                "Open dialog",
                                variant="outline",
                                color="violet",
                                highContrast=True,
                            ),
                            asChild=True,
                        ),
                        c(
                            "Dialog.Content",
                            [
                                c("Dialog.Title", "Plugin dialog"),
                                c("Dialog.Description", "Scoped portal content"),
                                c(
                                    "Input",
                                    label="Dialog input",
                                    placeholder="Dialog input",
                                ),
                                c(
                                    "Dialog.Close",
                                    c("Button", "Close dialog"),
                                    asChild=True,
                                ),
                            ],
                            className="showcase-dialog",
                            size="2",
                        ),
                    ],
                ),
                c(
                    "DropdownMenu.Root",
                    [
                        c("DropdownMenu.Trigger", c("Button", "Open menu")),
                        c(
                            "DropdownMenu.Content",
                            [c("DropdownMenu.Item", "Menu action", onSelect="menu")],
                            className="showcase-menu",
                        ),
                    ],
                ),
                c(
                    "Popover.Root",
                    [
                        c("Popover.Trigger", c("Button", "Open popover")),
                        c(
                            "Popover.Content",
                            [
                                c("Text", "Popover content"),
                                c("Popover.Close", c("Button", "Close popover")),
                            ],
                        ),
                    ],
                ),
                c(
                    "Radix.Tooltip",
                    c("Button", "Radix tooltip trigger"),
                    content="Radix tooltip content",
                    delayDuration=0,
                ),
                c(
                    "Tooltip",
                    c("Button", "Project tooltip trigger"),
                    content="Project tooltip content",
                ),
                c(
                    "Table.Root",
                    c(
                        "Table.Body",
                        c(
                            "Table.Row",
                            [
                                c("Table.RowHeaderCell", "State"),
                                c(
                                    "Table.Cell",
                                    json.dumps(state, ensure_ascii=False),
                                    **{"data-testid": "state"},
                                ),
                            ],
                        ),
                    ),
                    variant="surface",
                ),
            ],
            direction="column",
            gap="4",
            style={"padding": 12, "border-radius": 8},
        ),
    }


async def status(context, params):
    return {
        "css": ".showcase-title {color: rgb(14, 116, 144); animation: showcase-pulse 2s infinite;} @keyframes showcase-pulse {from {opacity:.9} to {opacity:1}}",
        "tree": c(
            "Badge",
            "Native UI ready",
            className="showcase-title",
            **{"data-testid": "showcase-status"},
        ),
    }


async def action(context, params):
    state = await context.storage.get("state", {})
    state[params["id"]] = params["value"]
    await context.storage.set("state", state)


def register(host):
    host.register_command("ui.render", render)
    host.register_command("ui.action", action)
    host.register_command("ui.status", status)

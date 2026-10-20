// Maintainer tool: derive the serializable protocol from the installed Radix version.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

import * as Radix from "@radix-ui/themes";

const root = fileURLToPath(new URL("../../", import.meta.url));
const radixDir = path.dirname(fileURLToPath(import.meta.resolve("@radix-ui/themes")));
const definitions = await import(pathToFileURL(path.join(radixDir, "props/index.js")).href);
const string = { type: "string" };
const boolean = { type: "boolean" };
const number = { type: "number" };
const event = { type: "event" };
const json = { type: "json" };
const enumOf = (...values) => ({ type: "enum", values });
function clean(defs) {
  return Object.fromEntries(
    Object.entries(defs).map(([name, value]) => [
      name,
      {
        type: value.type === "enum" ? "enum" : value.type === "boolean" ? "boolean" : "string",
        ...(value.values ? { values: value.values } : {}),
        ...(value.responsive ? { responsive: true } : {}),
      },
    ]),
  );
}
const dom = {
  id: string,
  className: string,
  title: string,
  role: string,
  tabIndex: number,
  dir: enumOf("ltr", "rtl"),
  lang: string,
  hidden: boolean,
  style: { type: "style" },
  text: string,
  source: string,
  label: string,
  key: string,
  children: { type: "node" },
  onPress: event,
  onClick: event,
  onFocus: event,
  onBlur: event,
  hotkey: string,
  autoFocus: boolean,
};
const legacy = {
  bold: boolean,
  italic: boolean,
  dimColor: boolean,
  inverse: boolean,
  plain: boolean,
  flexDirection: enumOf("row", "column"),
  justifyContent: string,
  alignItems: string,
  marginTop: number,
  paddingX: number,
  paddingY: number,
  padding: number,
  borderStyle: string,
  borderColor: string,
  gap: { type: "spacing" },
  wrap: string,
};
const layout = clean({ ...definitions.layoutPropDefs, ...definitions.marginPropDefs });
const shared = { ...dom, ...layout, ...legacy, asChild: boolean };
// Legacy color aliases remain valid for existing native plugins.
const colorAliases = ["magenta", "white", "black"];
const roots = [
  "AccessibleIcon",
  "AlertDialog",
  "AspectRatio",
  "Avatar",
  "Badge",
  "Blockquote",
  "Box",
  "Button",
  "Callout",
  "Card",
  "Checkbox",
  "CheckboxCards",
  "CheckboxGroup",
  "Code",
  "Container",
  "ContextMenu",
  "DataList",
  "Dialog",
  "DropdownMenu",
  "Em",
  "Flex",
  "Grid",
  "Heading",
  "HoverCard",
  "IconButton",
  "Inset",
  "Kbd",
  "Link",
  "Popover",
  "Progress",
  "Quote",
  "Radio",
  "RadioCards",
  "RadioGroup",
  "ScrollArea",
  "Section",
  "SegmentedControl",
  "Select",
  "Separator",
  "Skeleton",
  "Slider",
  "Spinner",
  "Strong",
  "Switch",
  "TabNav",
  "Table",
  "Tabs",
  "Text",
  "TextArea",
  "TextField",
  "Theme",
  "Tooltip",
  "VisuallyHidden",
];
const radix = {};
for (const family of roots) {
  const value = Radix[family];
  const parts =
    typeof value === "object" && value && !("$$typeof" in value)
      ? Object.keys(value).filter((name) => /^[A-Z]/.test(name))
      : [""];
  for (const part of parts) {
    const name = family + (part ? "." + part : "");
    const stem = family[0].toLowerCase() + family.slice(1) + part;
    const defs =
      definitions[stem + "PropDefs"] ??
      definitions[family[0].toLowerCase() + family.slice(1) + "PropDefs"] ??
      {};
    const props = { ...shared, ...clean(defs) };
    if (["Button", "IconButton"].includes(family))
      Object.assign(props, {
        type: enumOf("button", "submit", "reset"),
        disabled: boolean,
        name: string,
        value: string,
      });
    if (["TextField", "TextArea"].includes(family) && part !== "Slot")
      Object.assign(props, {
        value: string,
        defaultValue: string,
        placeholder: string,
        disabled: boolean,
        readOnly: boolean,
        required: boolean,
        name: string,
        type: enumOf(
          "text",
          "number",
          "email",
          "password",
          "search",
          "tel",
          "url",
          "date",
          "datetime-local",
          "time",
          "month",
          "week",
          "color",
          "range",
        ),
        inputMode: enumOf("none", "text", "tel", "url", "email", "numeric", "decimal", "search"),
        pattern: string,
        spellCheck: boolean,
        autoCapitalize: string,
        enterKeyHint: enumOf("enter", "done", "go", "next", "previous", "search", "send"),
        min: number,
        max: number,
        step: number,
        minLength: number,
        maxLength: number,
        rows: number,
        autoComplete: string,
        onInput: event,
        onChange: event,
        onSubmit: event,
      });
    if (
      [
        "Select",
        "Tabs",
        "SegmentedControl",
        "RadioGroup",
        "RadioCards",
        "DropdownMenu",
        "ContextMenu",
      ].includes(family)
    )
      Object.assign(props, {
        value: string,
        defaultValue: string,
        disabled: boolean,
        onValueChange: event,
        onSelect: event,
      });
    if (["CheckboxGroup", "CheckboxCards"].includes(family))
      Object.assign(props, {
        value: { type: "strings" },
        defaultValue: { type: "strings" },
        onValueChange: event,
        disabled: boolean,
      });
    if (["Checkbox", "Switch", "Radio"].includes(family) || part === "CheckboxItem")
      Object.assign(props, {
        checked:
          family === "Switch" || family === "Radio"
            ? boolean
            : enumOf(true, false, "indeterminate"),
        defaultChecked: boolean,
        disabled: boolean,
        onCheckedChange: event,
        onChange: event,
      });
    if (["Checkbox", "Switch", "Radio"].includes(family))
      Object.assign(props, { name: string, value: string, required: boolean });
    if (["Slider", "RadioGroup", "CheckboxGroup", "SegmentedControl"].includes(family))
      Object.assign(props, {
        orientation: enumOf("horizontal", "vertical"),
        name: string,
        loop: boolean,
      });
    if (family === "Select") {
      if (part === "Root")
        Object.assign(props, {
          open: boolean,
          defaultOpen: boolean,
          onOpenChange: event,
          autoComplete: string,
        });
      if (part === "Trigger") Object.assign(props, { placeholder: string });
      if (part === "Content")
        Object.assign(props, {
          position: enumOf("item-aligned", "popper"),
          side: enumOf("top", "right", "bottom", "left"),
          align: enumOf("start", "center", "end"),
          sideOffset: number,
          alignOffset: number,
          avoidCollisions: boolean,
          collisionPadding: number,
        });
    }
    if (family === "Slider")
      Object.assign(props, {
        value: { type: "numbers" },
        defaultValue: { type: "numbers" },
        min: number,
        max: number,
        step: number,
        minStepsBetweenThumbs: number,
        disabled: boolean,
        inverted: boolean,
        onValueChange: event,
        onValueCommit: event,
      });
    if (family === "Progress") Object.assign(props, { value: number, max: number });
    if (family === "Avatar") Object.assign(props, { src: string, alt: string, fallback: string });
    if (family === "AspectRatio") Object.assign(props, { ratio: number });
    if (["Link", "TabNav"].includes(family))
      Object.assign(props, {
        href: string,
        target: enumOf("_blank", "_self"),
        download: string,
        active: boolean,
      });
    if (
      [
        "Dialog",
        "AlertDialog",
        "Popover",
        "DropdownMenu",
        "ContextMenu",
        "HoverCard",
        "Tooltip",
      ].includes(family)
    ) {
      Object.assign(props, {
        open: boolean,
        defaultOpen: boolean,
        modal: boolean,
        onOpenChange: event,
      });
      if (
        (part.endsWith("Content") && !["Dialog", "AlertDialog"].includes(family)) ||
        family === "Tooltip"
      )
        Object.assign(props, {
          side: enumOf("top", "right", "bottom", "left"),
          align: enumOf("start", "center", "end"),
          sideOffset: number,
          alignOffset: number,
          collisionPadding: number,
          avoidCollisions: boolean,
          sticky: enumOf("partial", "always"),
          hideWhenDetached: boolean,
        });
    }
    if (family === "Tooltip") Object.assign(props, { content: string, delayDuration: number });
    if (family === "HoverCard") Object.assign(props, { openDelay: number, closeDelay: number });
    if (family === "Tabs")
      Object.assign(props, {
        orientation: enumOf("horizontal", "vertical"),
        activationMode: enumOf("automatic", "manual"),
        loop: boolean,
      });
    if (family === "ScrollArea")
      Object.assign(props, {
        scrollbars: enumOf("vertical", "horizontal", "both"),
        type: enumOf("auto", "always", "scroll", "hover"),
        scrollHideDelay: number,
      });
    if (part === "Root" && ["Checkbox", "Radio", "Select", "RadioGroup", "Switch"].includes(family))
      Object.assign(props, { name: string, required: boolean });
    if (part === "Item" || part === "Trigger" || part === "Content")
      Object.assign(props, { value: string, disabled: boolean });
    if (part === "Item") Object.assign(props, { shortcut: string, textValue: string });
    if (family === "Theme")
      Object.assign(props, {
        appearance: enumOf("light", "dark", "inherit"),
        accentColor: clean(definitions.colorPropDef).color,
        grayColor: string,
        scaling: enumOf("90%", "95%", "100%", "105%", "110%"),
      });
    if (props.color?.type === "enum")
      props.color = { ...props.color, values: [...props.color.values, ...colorAliases] };
    radix[name] = { props };
  }
}
const options = { type: "options" };
const project = {
  Spinner: { props: { ...dom, size: enumOf(12, 18, 24, 32) } },
  CircularProgress: {
    props: {
      ...dom,
      value: number,
      max: number,
      size: number,
      strokeWidth: number,
      ariaLabel: string,
    },
  },
  UnitTextField: {
    props: {
      ...radix["TextField.Root"].props,
      unit: string,
      unitSide: enumOf("left", "right"),
      leftUnit: string,
      rightUnit: string,
    },
  },
  StepperNumberInput: {
    props: {
      ...dom,
      value: json,
      min: number,
      max: number,
      step: number,
      unit: string,
      width: number,
      disabled: boolean,
      increaseAriaLabel: string,
      decreaseAriaLabel: string,
      onChange: event,
      onCommit: event,
    },
  },
  LabeledSelect: {
    props: {
      ...dom,
      value: string,
      options,
      placeholder: string,
      disabled: boolean,
      size: enumOf("1", "2", "3"),
      variant: enumOf("default", "icon"),
      layout: enumOf("vertical", "horizontal"),
      gap: enumOf("1", "2", "3", "4", "5"),
      labelSize: enumOf("1", "2", "3"),
      labelWeight: enumOf("regular", "medium", "bold"),
      labelColor: string,
      triggerClassName: string,
      contentClassName: string,
      triggerLabelVisible: boolean,
      hideTriggerChevron: boolean,
      onChange: event,
      onSelect: event,
      onValueChange: event,
    },
  },
  SearchableSelect: { props: {} },
  ModelIdSelect: {
    capabilities: ["models.read"],
    props: {
      ...dom,
      value: string,
      placeholder: string,
      disabled: boolean,
      taskType: enumOf("llm", "embedding", "rerank"),
      editable: boolean,
      allowCustomValue: boolean,
      compact: boolean,
      compactTrigger: boolean,
      hideTriggerChevron: boolean,
      emptyOptionLabel: string,
      triggerClassName: string,
      contentClassName: string,
      onChange: event,
      onSelect: event,
      onValueChange: event,
    },
  },
  ProjectSelectField: {
    capabilities: ["projects.read"],
    props: {
      ...dom,
      value: string,
      disabled: boolean,
      showNoneOption: boolean,
      placeholder: string,
      onChange: event,
      onSelect: event,
    },
  },
  ProjectGridSelector: {
    capabilities: ["projects.read"],
    props: {
      ...dom,
      value: string,
      disabled: boolean,
      showNoneOption: boolean,
      onChange: event,
      onSelect: event,
    },
  },
  InfoTooltip: { props: { ...dom, content: string } },
};
project.SearchableSelect.props = {
  ...project.LabeledSelect.props,
  searchPlaceholder: string,
  emptyMessage: string,
  contentHeight: number,
};
const aliases = {
  Input: "Radix.TextField.Root",
  Markdown: "Radix.Code",
  Select: "Project.LabeledSelect",
  Tooltip: "Project.InfoTooltip",
  ModelSelector: "Project.ModelIdSelect",
  ProjectSelector: "Project.ProjectSelectField",
};
// Store inherited properties once; the host and backend resolve the same catalogue.
for (const [source, entries] of [
  ["radix", radix],
  ["project", project],
]) {
  const inherited = source === "radix" ? shared : dom;
  for (const definition of Object.values(entries))
    for (const key of Object.keys(definition.props))
      if (JSON.stringify(definition.props[key]) === JSON.stringify(inherited[key]))
        delete definition.props[key];
}
const catalogue = {
  version: 2,
  common: dom,
  radixCommon: { ...layout, ...legacy, asChild: boolean },
  radix,
  project,
  aliases,
};
const target = path.join(root, "backend/app/plugins/ui-catalog.json");
const serialized = JSON.stringify(catalogue, null, 2) + "\n";
if (process.argv.includes("--check")) {
  if (fs.readFileSync(target, "utf8") !== serialized)
    throw new Error("UI catalogue is stale; regenerate it");
} else fs.writeFileSync(target, serialized);
console.log(
  "Radix nodes: " +
    Object.keys(radix).length +
    "; project components: " +
    Object.keys(project).length,
);

// Publish the same catalogue as dependency-free SDK types. No React runtime is required.
const names = [
  ...new Set([
    ...Object.keys(radix),
    ...Object.keys(project),
    ...Object.keys(aliases),
    ...Object.keys(radix).map((name) => "Radix." + name),
    ...Object.keys(project).map((name) => "Project." + name),
  ]),
].sort();
function typeOf(spec) {
  let value = {
    string: "string",
    event: "string",
    boolean: "boolean",
    number: "number",
    json: "Json",
    style: "UIStyle",
    node: "UINode",
    strings: "string[]",
    numbers: "number[]",
    options: "UISelectOption[]",
    spacing: "string | number",
  }[spec.type];
  if (spec.type === "enum") value = spec.values.map((v) => JSON.stringify(v)).join(" | ");
  return spec.responsive ? "UIResponsive<" + value + ">" : value;
}
const allProps = {};
for (const def of [{ props: shared }, ...Object.values(radix), ...Object.values(project)])
  for (const [name, spec] of Object.entries(def.props)) {
    (allProps[name] ??= new Set()).add(typeOf(spec));
  }
const generated = `/** Generated by frontend/scripts/generate-plugin-ui-catalog.mjs. Project components win unqualified names. */
export type UIComponent =
  ${names.map((n) => JSON.stringify(n)).join(" |\n  ")};
export interface UIPropertyDefinition { type: string; values?: (string | number | boolean)[]; responsive?: boolean; }
export interface UIComponentDefinition { props: Record<string, UIPropertyDefinition>; capabilities?: string[]; }
export interface UICatalogue {
  version: number; common: Record<string, UIPropertyDefinition>; radixCommon: Record<string, UIPropertyDefinition>;
  radix: Record<string, UIComponentDefinition>; project: Record<string, UIComponentDefinition>; aliases: Record<string, string>;
}
export interface SDKCatalogue {
  version: string; capabilities: string[]; slots: UIAction[]; events: string[]; ui: UICatalogue;
  openapi: Json; operations: { path: string; methods: string[]; capability: string; summary: string }[];
}
export type UIResponsive<T> = T | Partial<Record<"initial" | "xs" | "sm" | "md" | "lg" | "xl", T>>;
/** camelCase, kebab-case and custom properties. Numeric lengths follow React CSS conventions. */
export type UIStyle = { [property: string]: string | number | null };
export interface UISelectOption { value: string; label?: string; description?: string; disabled?: boolean; labelColor?: string; fontFamily?: string; separatorAfter?: boolean; }
/** Per-component validity and capabilities are available from sdk.api.catalogue().ui.
 * Events are opaque backend action IDs; functions, refs and arbitrary DOM props are unavailable. */
export interface UIProps {
${Object.entries(allProps)
  .sort(([a], [b]) => a.localeCompare(b))
  .map(([k, ts]) => "  " + JSON.stringify(k) + "?: " + [...ts].join(" | ") + ";")
  .join("\n")}
  [attribute: \`data-\${string}\`]: string | number | boolean | null | undefined;
  [attribute: \`aria-\${string}\`]: string | number | boolean | null | undefined;
}
export type UINode = null | boolean | number | string | UINode[] | { type: UIComponent; props?: UIProps; children?: UINode };
/** CSS is limited to this view and its portals; @import/font-face/global registrations are ignored. */
export type UIDocument = ({ tree: UINode } | {
  trees: { component: "View" | "AbovePrompt" | "Pane" | "Spinner"; requestId?: string; tree: UINode }[];
  panes?: { id: string; title?: string; focus?: boolean; closeOnEscape?: boolean }[];
  commands?: { name: string }[];
}) & { css?: string };
export interface UIRenderRequest { viewId: string; slot: UIAction; columns: number; context: Partial<Context>; }
export interface UIEventRequest extends UIRenderRequest {
  id: string; event: "press" | "input" | "submit" | "select" | "change" | "command" | "close";
  value: Json;
}
/** Action response only; effects run sequentially via the capability-checked host bridge.
 * At most 16 effects/batch and 4 batches; next receives results as its event value. */
export interface UIActionResult {
  effects: { method: "editor.read" | "editor.insert" | "editor.replaceSelection" | "editor.setContent" |
    "editor.setSelection" | "editor.focus" | "editor.save" | "editor.undo" | "editor.redo" |
    "ui.navigate" | "ui.openExternal" | "ui.toast" | "ui.confirm" | "ui.copy" | "ui.download" |
    "ui.invalidate" | "ui.context" | "ui.tools" | "assistant.fill"; params?: Record<string, Json>; discardResult?: boolean }[];
  next?: string;
}
`;
for (const relative of ["packages/plugin-sdk/index.d.ts", "backend/app/plugins/sdk.d.ts"]) {
  const file = path.join(root, relative);
  const original = fs.readFileSync(file, "utf8");
  const start = original.indexOf(
    "/** Generated by frontend/scripts/generate-plugin-ui-catalog.mjs.",
  );
  const offset = start >= 0 ? start : original.indexOf("export type UIComponent");
  const next = (
    original.slice(0, offset) +
    generated +
    original.slice(original.indexOf("export interface Context"))
  ).replace("catalogue(): Promise<Json>", "catalogue(): Promise<SDKCatalogue>");
  if (process.argv.includes("--check")) {
    if (next !== original) throw new Error(relative + " is stale; regenerate it");
  } else fs.writeFileSync(file, next);
}

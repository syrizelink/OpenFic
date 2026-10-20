import * as Radix from "@radix-ui/themes";
import {
  Component,
  createElement,
  isValidElement,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ComponentType,
  type ReactNode,
  type CSSProperties,
} from "react";

import { UnitTextField as ProjectInput } from "@/components/unit-text-field";

import { inlineStyle, safeHref, safeCSSValue } from "./declarative-css";
import { ProjectComponent } from "./declarative-project-components";
import {
  resolveComponent,
  type UIAction,
  type UIProps,
  type UINode,
  type UIValue,
} from "./declarative-schema";
import { PluginIcon } from "./plugin-icon";

export interface TreeContext {
  action: UIAction;
  pluginId: string;
  portal: HTMLElement;
  animations: Map<string, string>;
  animationVariables: Set<string>;
}
function str(value: unknown, fallback = "") {
  return typeof value === "string" ? value : fallback;
}
const legacyProps = new Set([
  "key",
  "label",
  "text",
  "source",
  "children",
  "bold",
  "italic",
  "dimColor",
  "inverse",
  "plain",
  "hotkey",
  "flexDirection",
  "justifyContent",
  "alignItems",
  "marginTop",
  "padding",
  "paddingX",
  "paddingY",
  "borderStyle",
  "borderColor",
]);
function InputControl({
  component: Control,
  forwarded,
  props: p,
  action,
  children,
}: {
  component: ComponentType<Record<string, unknown>>;
  forwarded: Record<string, unknown>;
  props: UIProps;
  action: UIAction;
  children?: ReactNode;
}) {
  const [draft, setDraft] = useState(str(p.value, str(p.defaultValue)));
  const input = useRef<HTMLInputElement | HTMLTextAreaElement>(null);
  useEffect(() => {
    if (document.activeElement !== input.current) setDraft(str(p.value, str(p.defaultValue)));
  }, [p.value, p.defaultValue]);
  return (
    <Control
      {...forwarded}
      ref={input}
      value={draft}
      onChange={(event: { target: { value: string } }) => {
        setDraft(event.target.value);
        action(str(p.onInput || p.onChange), event.target.value, "input");
      }}
      onKeyDown={(event: { key: string; preventDefault: () => void }) => {
        if (event.key === "Enter" && p.onSubmit) {
          event.preventDefault();
          action(str(p.onSubmit), draft, "submit");
        }
      }}
    >
      {children}
    </Control>
  );
}
/** Drag locally even when the plugin only subscribes to committed values. */
function SliderControl({
  forwarded,
  props: p,
  action,
}: {
  forwarded: Record<string, unknown>;
  props: UIProps;
  action: UIAction;
}) {
  const root = useRef<HTMLSpanElement>(null);
  const external = JSON.stringify(p.value ?? p.defaultValue ?? [0]);
  const [draft, setDraft] = useState<number[]>(JSON.parse(external));
  useEffect(() => {
    setDraft(JSON.parse(external));
  }, [external]);
  // Themes forwards ARIA props to its root, while the focusable sliders are thumbs.
  // Name each thumb as well so SDK labels work for keyboard and screen reader users.
  const label = str(forwarded["aria-label"]);
  const labelledBy = str(forwarded["aria-labelledby"]);
  useLayoutEffect(() => {
    root.current?.querySelectorAll('[role="slider"]').forEach((thumb, index) => {
      if (label)
        thumb.setAttribute("aria-label", draft.length > 1 ? `${label} ${index + 1}` : label);
      else thumb.removeAttribute("aria-label");
      if (labelledBy) thumb.setAttribute("aria-labelledby", labelledBy);
      else thumb.removeAttribute("aria-labelledby");
    });
  }, [label, labelledBy, draft.length]);
  return (
    <Radix.Slider
      {...forwarded}
      ref={root}
      value={draft}
      onValueChange={(value) => {
        setDraft(value);
        if (p.onValueChange) action(str(p.onValueChange), value, "select");
      }}
      onValueCommit={(value) => {
        if (p.onValueCommit) action(str(p.onValueCommit), value, "change");
      }}
    />
  );
}
function radixComponent(name: string): ComponentType<Record<string, unknown>> | undefined {
  let value: unknown = Radix;
  for (const part of name.split("."))
    value =
      value && typeof value === "object" && part in value
        ? (value as Record<string, unknown>)[part]
        : undefined;
  return value as ComponentType<Record<string, unknown>> | undefined;
}
function isNode(node: UINode): node is { type: string; props: UIProps; children: UINode } {
  return Boolean(node && typeof node === "object" && !Array.isArray(node) && "type" in node);
}

/** Return real element children so Radix asChild/Trigger can forward refs and handlers. */
// oxlint-disable-next-line react-refresh/only-export-components
export function renderTree(node: UINode, context: TreeContext, index = 0): ReactNode {
  if (node == null || typeof node === "boolean") return null;
  if (typeof node !== "object") return String(node);
  if (Array.isArray(node)) {
    const children = node.map((child, i) => renderTree(child, context, i));
    return children.length === 1 ? children[0] : children;
  }
  if (!isNode(node)) return null;
  const p = node.props;
  const { source, name, definition } = resolveComponent(node.type);
  if (!definition)
    return (
      <Radix.Text
        key={index}
        color="gray"
      >
        Unsupported UI component: {node.type}
      </Radix.Text>
    );
  const children =
    typeof p.text === "string"
      ? p.text
      : typeof p.source === "string"
        ? p.source
        : renderTree(node.children, context);
  const fire = (key: string, value: UIValue = null, event = "change") =>
    context.action(str(p[key]), value, event);
  const props: Record<string, unknown> = {
    key: str(p.key, String(index)),
    "data-plugin-component": name,
    "data-component-source": source,
  };
  for (const [key, value] of Object.entries(p)) {
    if (legacyProps.has(key) || key.startsWith("on") || key === "style") continue;
    if (key in definition.props || /^(?:aria|data)-/.test(key)) props[key] = value;
  }
  props.style = inlineStyle(p, context.animations, context.animationVariables);
  if (p.hotkey) props["data-hotkey"] = p.hotkey;
  if (p.autoFocus) props["data-plugin-autofocus"] = "true";
  if (p.label && p["aria-label"] == null) props["aria-label"] = p.label;
  if (p.onPress || p.onClick)
    props.onClick = () => fire(p.onPress ? "onPress" : "onClick", null, "press");
  if (p.onFocus) props.onFocus = () => fire("onFocus");
  if (p.onBlur) props.onBlur = () => fire("onBlur");
  if (p.onOpenChange) props.onOpenChange = (open: boolean) => fire("onOpenChange", open);
  if (p.onCheckedChange || (p.onChange && ["Checkbox", "Switch"].includes(name))) {
    props.onCheckedChange = (checked: boolean | "indeterminate") =>
      fire(p.onCheckedChange ? "onCheckedChange" : "onChange", checked);
  }
  if (p.onValueChange || (p.onSelect && name.endsWith("Root"))) {
    props.onValueChange = (value: UIValue) =>
      fire(p.onValueChange ? "onValueChange" : "onSelect", value, "select");
  }
  if (p.onValueCommit) props.onValueCommit = (value: UIValue) => fire("onValueCommit", value);
  if (name.endsWith(".Item") && p.onSelect)
    props.onSelect = () => fire("onSelect", p.value ?? null, "press");
  if (name.endsWith("CheckboxItem") && p.onCheckedChange)
    props.onCheckedChange = (value: boolean | "indeterminate") => fire("onCheckedChange", value);
  if (p.color === "magenta") props.color = "purple";
  if (p.color === "white" || p.color === "black") {
    delete props.color;
    props.style = { ...(props.style as object), color: "var(--gray-12)" };
  }
  // Preserve the original Box's Flex semantics and numeric 4px spacing.
  let Control = radixComponent(name);
  if (node.type === "Box") {
    Control = Radix.Flex as unknown as ComponentType<Record<string, unknown>>;
    props.direction = p.direction ?? p.flexDirection ?? "column";
    if (typeof p.gap === "number") {
      props.style = { ...(props.style as object), gap: Math.max(0, Math.min(8, p.gap)) * 4 };
      delete props.gap;
    }
    props.style = {
      ...(props.style as object),
      ...(p.justifyContent ? { justifyContent: p.justifyContent } : {}),
      ...(p.alignItems ? { alignItems: p.alignItems } : {}),
      ...(typeof p.marginTop === "number" ? { marginTop: p.marginTop * 4 } : {}),
      ...(typeof (p.paddingX ?? p.padding) === "number"
        ? { paddingInline: Number(p.paddingX ?? p.padding) * 4 }
        : {}),
      ...(typeof (p.paddingY ?? p.padding) === "number"
        ? { paddingBlock: Number(p.paddingY ?? p.padding) * 4 }
        : {}),
    };
  }
  if (name.endsWith("Content") || name === "Tooltip") props.container = context.portal;
  if (name === "Link" || name === "TabNav.Link") {
    const href = safeHref(p.href);
    if (!href)
      return (
        <Radix.Text
          key={str(p.key, String(index))}
          style={props.style as CSSProperties}
        >
          {p.label ? str(p.label) : children}
        </Radix.Text>
      );
    props.href = href;
    props.target = p.target ?? "_blank";
    props.rel = "noopener noreferrer";
  }
  if (name === "Avatar" && p.src && !safeHref(p.src)) delete props.src;
  if (name === "Progress" && typeof p.value === "number")
    props.value = Math.max(0, Math.min(typeof p.max === "number" ? p.max : 100, p.value));
  if ((name === "Code" && node.type === "Code") || node.type === "Markdown")
    return (
      <pre
        key={index}
        className="plugin-declarative-code"
      >
        <Radix.Code {...props}>{children}</Radix.Code>
      </pre>
    );
  if (source === "project") {
    if (name === "Icon") {
      const label = str(p["aria-label"], str(p.label));
      const forwarded = Object.fromEntries(
        Object.entries(props).filter(
          ([key]) => !["key", "name", "size", "strokeWidth", "absoluteStrokeWidth"].includes(key),
        ),
      );
      return (
        <PluginIcon
          {...forwarded}
          key={props.key as string}
          name={str(p.name, "Puzzle")}
          size={Math.max(8, Math.min(96, Number(p.size) || 18))}
          strokeWidth={Math.max(0.5, Math.min(4, Number(p.strokeWidth) || 2))}
          color={typeof p.color === "string" && safeCSSValue(p.color) ? p.color : undefined}
          absoluteStrokeWidth={p.absoluteStrokeWidth === true}
          aria-hidden={label ? undefined : true}
          aria-label={label || undefined}
          role={label ? "img" : undefined}
        />
      );
    }
    const change = (value: UIValue, kind = "change") =>
      context.action(
        str(p.onPositionChange || p.onValueChange || p.onChange || p.onSelect || p.onInput),
        value,
        kind,
      );
    if (name === "StepperNumberInput") {
      props.onChange = (value: string) => context.action(str(p.onChange), value, "input");
      props.onCommit = (value: number) => context.action(str(p.onCommit), value, "change");
    }
    if (name === "UnitTextField")
      return (
        <InputControl
          key={props.key as string}
          component={ProjectInput as unknown as ComponentType<Record<string, unknown>>}
          forwarded={props}
          props={p}
          action={context.action}
        />
      );
    const projectChildren =
      name === "InfoTooltip" && !isValidElement(children) ? (
        <Radix.Button
          type="button"
          size="1"
        >
          {p.label ? str(p.label) : children}
        </Radix.Button>
      ) : (
        children
      );
    const element = (
      <ProjectComponent
        key={props.key as string}
        name={name}
        props={p}
        forwarded={props}
        pluginId={context.pluginId}
        change={change}
      >
        {projectChildren}
      </ProjectComponent>
    );
    if (["Spinner", "CircularProgress", "Image", "FloatingPanel"].includes(name)) return element;
    const wrapper = Object.fromEntries(
      Object.entries(props).filter(
        ([key]) =>
          /^(?:aria|data)-/.test(key) ||
          [
            "id",
            "className",
            "title",
            "role",
            "tabIndex",
            "dir",
            "lang",
            "hidden",
            "style",
            "onClick",
            "onFocus",
            "onBlur",
          ].includes(key),
      ),
    );
    if (name === "InfoTooltip") {
      delete wrapper.className; // Tooltip's className belongs to its portal content.
      return (
        <span
          {...wrapper}
          key={props.key as string}
        >
          {element}
        </span>
      );
    }
    return (
      <div
        {...wrapper}
        key={props.key as string}
      >
        {element}
      </div>
    );
  }
  if (!Control)
    return (
      <Radix.Text
        key={index}
        color="gray"
      >
        Unsupported UI component: {node.type}
      </Radix.Text>
    );
  if (["TextField.Root", "TextArea"].includes(name))
    return (
      <InputControl
        key={props.key as string}
        component={Control}
        forwarded={props}
        props={p}
        action={context.action}
      >
        {name === "TextField.Root" ? children : undefined}
      </InputControl>
    );
  if (name === "Slider")
    return (
      <SliderControl
        key={props.key as string}
        forwarded={props}
        props={p}
        action={context.action}
      />
    );
  const elementChild =
    /^(?:Dialog|AlertDialog|Popover|HoverCard|DropdownMenu|ContextMenu)\.(?:Trigger|Close|Cancel|Action)$/.test(
      name,
    ) ||
    name === "Tooltip" ||
    name === "AccessibleIcon";
  const empty = children == null || (Array.isArray(children) && children.length === 0);
  const content = empty
    ? p.label && name !== "Select.Trigger"
      ? str(p.label)
      : undefined
    : children;
  const child =
    elementChild && !isValidElement(content) ? (
      <Radix.Button
        type="button"
        size="1"
      >
        {content}
      </Radix.Button>
    ) : (
      content
    );
  const voidControl = [
    "Avatar",
    "Progress",
    "Separator",
    "Slider",
    "Spinner",
    "Checkbox",
    "Radio",
    "Switch",
  ].includes(name);
  return createElement(Control, props, voidControl ? undefined : child);
}

export class DeclarativeErrorBoundary extends Component<
  { children: ReactNode; resetKey: unknown },
  { error: string | null; resetKey: unknown }
> {
  state: { error: string | null; resetKey: unknown } = {
    error: null,
    resetKey: this.props.resetKey,
  };
  static getDerivedStateFromError(error: Error) {
    return { error: error.message };
  }
  static getDerivedStateFromProps(props: { resetKey: unknown }, state: { resetKey: unknown }) {
    return props.resetKey !== state.resetKey ? { error: null, resetKey: props.resetKey } : null;
  }
  render() {
    return this.state.error ? (
      <Radix.Text
        role="alert"
        color="red"
      >
        Invalid plugin UI: {this.state.error}
      </Radix.Text>
    ) : (
      this.props.children
    );
  }
}

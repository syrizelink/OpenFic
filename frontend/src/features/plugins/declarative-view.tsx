import {
  Badge,
  Box,
  Button,
  Checkbox,
  Code,
  Flex,
  Heading,
  Link,
  Progress,
  Select,
  Separator,
  Switch,
  Text,
  TextField,
  useThemeContext,
} from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useParams, useSearchParams } from "react-router";

import { Spinner } from "@/components/spinner";
import { apiClient } from "@/lib/api-client";

import { pluginError, type InstalledPlugin, type PluginView } from "./api";

type Scalar = string | number | boolean | null;
type Props = Record<string, Scalar | { value: string; label: string }[]>;
type UINode = Scalar | UINode[] | { type: string; props: Props; children: UINode };
interface UIDocument {
  version: 1;
  trees: { component: string; requestId: string; tree: UINode }[];
  panes: { id: string; title: string; focus: boolean; closeOnEscape: boolean }[];
  commands: { name: string }[];
}
type Action = (id: string, value?: Scalar, event?: string) => void;
const colors: Record<string, string> = {
  red: "var(--red-11)",
  green: "var(--green-11)",
  blue: "var(--blue-11)",
  cyan: "var(--cyan-11)",
  magenta: "var(--purple-11)",
  yellow: "var(--amber-11)",
  gray: "var(--gray-11)",
  white: "var(--gray-12)",
  black: "var(--gray-12)",
};
function str(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}
function spacing(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value)
    ? Math.max(0, Math.min(8, value)) * 4
    : 0;
}
function safeHref(value: unknown): string | undefined {
  if (typeof value !== "string") return;
  try {
    const url = new URL(value);
    if (["https:", "http:"].includes(url.protocol)) return url.href;
  } catch {
    /* Invalid URLs render as text. */
  }
}

function Tree({ node, action }: { node: UINode; action: Action }): ReactNode {
  if (node == null || typeof node === "boolean") return null;
  if (typeof node !== "object") return String(node);
  if (Array.isArray(node))
    return node.map((child, index) => (
      <Tree
        key={
          typeof child === "object" && child && !Array.isArray(child)
            ? str(child.props.key, String(index))
            : index
        }
        node={child}
        action={action}
      />
    ));
  const p = node.props;
  const children =
    typeof p.text === "string" ? (
      p.text
    ) : typeof p.source === "string" ? (
      p.source
    ) : (
      <Tree
        node={node.children}
        action={action}
      />
    );
  const style: CSSProperties = {
    color: colors[str(p.color)],
    fontWeight: p.bold || p.inverse ? "bold" : undefined,
    fontStyle: p.italic ? "italic" : undefined,
    opacity: p.dimColor ? 0.65 : undefined,
    background: p.inverse ? "var(--gray-a4)" : undefined,
  };
  const label = str(p.label, str(p.placeholder, node.type));
  const fire = (key: string, value?: Scalar, event?: string) => action(str(p[key]), value, event);
  switch (node.type) {
    case "Box":
      return (
        <Flex
          style={{
            ...style,
            minWidth: 0,
            flexDirection: p.flexDirection === "row" ? "row" : "column",
            flexWrap: "wrap",
            gap: spacing(p.gap),
            marginTop: spacing(p.marginTop),
            paddingInline: spacing(p.paddingX ?? p.padding),
            paddingBlock: spacing(p.paddingY ?? p.padding),
            justifyContent: ["space-between", "space-around", "center", "flex-end"].includes(
              str(p.justifyContent),
            )
              ? str(p.justifyContent)
              : undefined,
            alignItems: ["center", "flex-start", "flex-end", "stretch"].includes(str(p.alignItems))
              ? str(p.alignItems)
              : undefined,
          }}
        >
          {children}
        </Flex>
      );
    case "Text":
      return (
        <Text style={{ ...style, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
          {children}
        </Text>
      );
    case "Button":
      return (
        <Button
          type="button"
          size="1"
          variant="soft"
          disabled={Boolean(p.disabled)}
          data-hotkey={str(p.hotkey)}
          data-plugin-autofocus={p.autoFocus ? "true" : undefined}
          onClick={() => fire("onPress", null, "press")}
        >
          {p.label ? label : children}
        </Button>
      );
    case "Input":
      return (
        <DeclarativeInput
          key={str(p.key)}
          props={p}
          action={action}
        />
      );
    case "Select": {
      const options = Array.isArray(p.options)
        ? p.options.filter((option) => option.value !== "")
        : [];
      return (
        <Select.Root
          size="1"
          value={str(p.value)}
          disabled={Boolean(p.disabled)}
          onValueChange={(value) => fire("onSelect", value, "select")}
        >
          <Select.Trigger
            aria-label={label}
            placeholder={str(p.placeholder)}
          />
          <Select.Content>
            {options.map((option, index) => (
              <Select.Item
                key={`${option.value}:${index}`}
                value={option.value}
              >
                {option.label}
              </Select.Item>
            ))}
          </Select.Content>
        </Select.Root>
      );
    }
    case "Checkbox":
    case "Switch": {
      const Control = node.type === "Checkbox" ? Checkbox : Switch;
      return (
        <Flex
          asChild
          align="center"
          gap="2"
        >
          <label>
            <Control
              aria-label={label}
              checked={Boolean(p.checked)}
              disabled={Boolean(p.disabled)}
              onCheckedChange={(value) => fire("onChange", value === true, "change")}
            />
            {p.label ? label : children}
          </label>
        </Flex>
      );
    }
    case "Link": {
      const href = safeHref(p.href);
      return href ? (
        <Link
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          style={style}
        >
          {p.label ? label : children || href}
        </Link>
      ) : (
        <Text style={style}>{p.label ? label : children}</Text>
      );
    }
    case "Code":
    case "Markdown":
      return (
        <Box asChild>
          <pre className="plugin-declarative-code">
            <Code style={style}>{children}</Code>
          </pre>
        </Box>
      );
    case "Badge":
      return <Badge style={style}>{p.label ? label : children}</Badge>;
    case "Separator":
      return <Separator size="4" />;
    case "Progress":
      return (
        <Progress
          aria-label={label}
          value={typeof p.value === "number" ? Math.max(0, Math.min(100, p.value)) : undefined}
        />
      );
    default:
      return (
        <Text
          color="gray"
          size="1"
        >
          Unsupported UI component: {node.type}
        </Text>
      );
  }
}

function DeclarativeInput({ props: p, action }: { props: Props; action: Action }) {
  const [draft, setDraft] = useState(str(p.value));
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    // An older server acknowledgement must not replace newer local keystrokes.
    if (document.activeElement !== input.current) setDraft(str(p.value));
  }, [p.value]);
  return (
    <TextField.Root
      ref={input}
      size="1"
      aria-label={str(p.label, str(p.placeholder, "Input"))}
      value={draft}
      placeholder={str(p.placeholder)}
      disabled={Boolean(p.disabled)}
      onChange={(event) => {
        setDraft(event.target.value);
        if (p.onInput) action(str(p.onInput), event.target.value, "input");
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" && p.onSubmit) {
          event.preventDefault();
          action(str(p.onSubmit), draft, "submit");
        }
      }}
    />
  );
}

export function DeclarativeView({
  plugin,
  view,
  context = {},
  embedded = false,
}: {
  plugin: InstalledPlugin;
  view: PluginView;
  context?: Record<string, unknown>;
  embedded?: boolean;
}) {
  const { i18n } = useTranslation();
  const { appearance } = useThemeContext();
  const params = useParams();
  const [search] = useSearchParams();
  const projectId = context.projectId ?? params.projectId ?? search.get("projectId");
  const contextKey = JSON.stringify({
    ...context,
    pluginId: plugin.id,
    projectId,
    language: i18n.language,
    theme: appearance === "dark" ? "dark" : "light",
    settings: plugin.configuration,
    capabilities: plugin.capabilities,
    slot: view.slot,
    sdkVersion: "2.0.0",
  });
  const root = useRef<HTMLDivElement>(null);
  const [columns, setColumns] = useState(100);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const queue = useRef<Promise<void>>(Promise.resolve());
  const generation = useRef({ active: true, pending: 0 });
  const paneKey = useRef("");
  const {
    data,
    error: renderError,
    refetch,
  } = useQuery({
    queryKey: ["plugin-declarative", plugin.id, plugin.version, view.id, contextKey, columns],
    queryFn: async ({ signal }) =>
      (
        await apiClient.post<UIDocument>(
          `/plugins/${plugin.id}/views/${view.id}/render`,
          { context: JSON.parse(contextKey), columns },
          { signal },
        )
      ).data,
    refetchOnWindowFocus: false,
  });
  const actions = useRef<Action>(() => {});
  const run: Action = (id, value = null, event = "press") => {
    if (!id) return;
    const current = generation.current;
    if (current.pending >= 32) {
      setError("Too many pending UI actions");
      return;
    }
    current.pending++;
    setError(null);
    queue.current = queue.current
      .then(async () => {
        if (!current.active) return;
        const response = await apiClient.post<{ result: unknown }>(
          `/plugins/${plugin.id}/views/${view.id}/action`,
          {
            id,
            value,
            event,
            context: JSON.parse(contextKey),
          },
        );
        if (current.active && event === "command") {
          const result = response.data.result;
          setMessage(
            result && typeof result === "object" && "text" in result ? str(result.text) : "",
          );
        }
        if (current.active) await refetch();
      })
      .catch((fault: unknown) => {
        if (current.active) setError(pluginError(fault));
      })
      .finally(() => {
        current.pending--;
      });
  };
  useEffect(() => {
    actions.current = run;
  });
  useEffect(() => {
    const lifetime = { active: true, pending: 0 };
    generation.current = lifetime;
    setError(null);
    setMessage("");
    return () => {
      lifetime.active = false;
    };
  }, [contextKey, plugin.id, view.id]);
  useEffect(() => {
    const element = root.current;
    if (!element) return;
    const observer = new ResizeObserver(() => {
      const next = Math.max(20, Math.min(240, Math.floor(element.clientWidth / 7.2)));
      setColumns((previous) => (previous === next ? previous : next));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const invalidate = (event: Event) => {
      const detail = (event as CustomEvent<{ event: string }>).detail;
      if (detail.event !== "ui.invalidate" && detail.event !== "data.changed") return;
      clearTimeout(timer);
      timer = setTimeout(() => {
        void refetch();
      }, 50);
    };
    window.addEventListener("openfic:plugin-event", invalidate);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("openfic:plugin-event", invalidate);
    };
  }, [refetch]);
  useEffect(() => {
    const next = data?.panes.map((pane) => pane.id).join("/") ?? "";
    if (next && next !== paneKey.current && data?.panes.some((pane) => pane.focus)) {
      root.current?.querySelector<HTMLElement>('[data-plugin-autofocus="true"]')?.focus();
    } else if (!next && paneKey.current) {
      root.current?.querySelector<HTMLElement>("button")?.focus();
    }
    paneKey.current = next;
  }, [data]);
  const trees = data?.trees.filter((entry) => entry.tree != null) ?? [];
  return (
    <div
      ref={root}
      className={`plugin-declarative${embedded ? " plugin-declarative-embedded" : ""}`}
      data-plugin-view={`${plugin.id}/${view.id}`}
      data-renderer="declarative"
      data-empty={String(!trees.length && !error && !renderError)}
      aria-label={view.title}
      onKeyDown={(event) => {
        if (event.ctrlKey || event.metaKey || event.altKey) return;
        const pane = data?.panes.find((item) => item.closeOnEscape);
        if (event.key === "Escape" && pane) {
          event.preventDefault();
          event.stopPropagation();
          actions.current(pane.id, null, "close");
          return;
        }
        if (
          (event.target as HTMLElement).closest(
            'input,textarea,[contenteditable="true"],[role="combobox"],[role="switch"],[role="checkbox"]',
          )
        )
          return;
        const button = [
          ...(root.current?.querySelectorAll<HTMLButtonElement>("button[data-hotkey]") ?? []),
        ].find((item) => item.dataset.hotkey?.toLowerCase() === event.key.toLowerCase());
        if (button && !button.disabled) {
          event.preventDefault();
          event.stopPropagation();
          button.click();
        }
      }}
    >
      {!embedded && (
        <Flex
          direction="column"
          gap="2"
          mb="3"
        >
          <Heading
            as="h2"
            size="4"
            weight="bold"
          >
            {view.title}
          </Heading>
          {plugin.compatibility?.warnings?.map((warning) => (
            <Text
              key={warning}
              size="1"
              color="gray"
            >
              {warning}
            </Text>
          ))}
          <Flex
            gap="2"
            wrap="wrap"
          >
            {data?.commands.map((command) => (
              <Button
                key={command.name}
                size="1"
                variant="soft"
                onClick={() => run(command.name, "", "command")}
              >
                /{command.name}
              </Button>
            ))}
          </Flex>
        </Flex>
      )}
      {!data && !renderError && !embedded && <Spinner />}
      {message && (
        <Text
          as="p"
          role="status"
        >
          {message}
        </Text>
      )}
      {(error || renderError) && (
        <Text
          as="p"
          role="alert"
          color="red"
        >
          {error ?? pluginError(renderError)}
        </Text>
      )}
      {trees.map((entry, index) => (
        <section
          key={`${entry.component}:${entry.requestId}:${index}`}
          data-component={entry.component}
          role={entry.component === "Pane" ? "region" : undefined}
          aria-label={
            entry.component === "Pane"
              ? data?.panes.find((pane) => pane.id === entry.requestId)?.title || plugin.name
              : undefined
          }
          aria-live={entry.component === "Pane" ? undefined : "polite"}
        >
          <Tree
            node={entry.tree}
            action={run}
          />
        </section>
      ))}
    </div>
  );
}

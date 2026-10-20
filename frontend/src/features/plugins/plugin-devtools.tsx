import {
  Badge,
  Box,
  Button,
  Dialog,
  Flex,
  Heading,
  Popover,
  Select,
  Text,
  TextArea,
  TextField,
  Theme,
} from "@radix-ui/themes";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { apiClient } from "@/lib/api-client";
import {
  applyThemePalette,
  DEFAULT_THEME_CONFIG,
  DEFAULT_THEME_PRESET_ID,
  resolveThemePalette,
} from "@/lib/theme";

import { fetchSettings } from "../settings/lib/settings-api";
import {
  fetchPluginDevelopment,
  fetchPlugins,
  pluginError,
  PLUGINS_QUERY_KEY,
  type PluginView,
} from "./api";
import { enablePluginDiagnostics, type PluginDiagnostic } from "./plugin-diagnostics";
import { PluginFrame } from "./plugin-page";
import { PluginRuntime } from "./plugin-runtime";

import "./plugin-devtools.css";

function Choice({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="plugin-devtools-choice">
      <Text size="2">{label}</Text>
      <Select.Root
        value={value}
        onValueChange={onChange}
      >
        <Select.Trigger aria-label={label} />
        <Select.Content>
          {options.map((option) => (
            <Select.Item
              key={option.value}
              value={option.value}
            >
              {option.label}
            </Select.Item>
          ))}
        </Select.Content>
      </Select.Root>
    </label>
  );
}
function JSONView({ value }: { value: unknown }) {
  return <pre className="plugin-devtools-json">{JSON.stringify(value, null, 2)}</pre>;
}
function TreeInspector({ node }: { node: unknown }) {
  if (Array.isArray(node))
    return (
      <>
        {node.map((child, index) => (
          <TreeInspector
            key={index}
            node={child}
          />
        ))}
      </>
    );
  if (!node || typeof node !== "object")
    return node == null ? null : <div className="plugin-devtools-tree-text">{String(node)}</div>;
  const value = node as { type?: string; props?: unknown; children?: unknown };
  if (!value.type) return <JSONView value={node} />;
  return (
    <details
      open
      className="plugin-devtools-tree"
    >
      <summary>{value.type}</summary>
      <JSONView value={value.props ?? {}} />
      <div>
        <TreeInspector node={value.children} />
      </div>
    </details>
  );
}

export function PluginDevtoolsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useSearchParams();
  const { data: development, error: developmentError } = useQuery({
    queryKey: ["plugin-development"],
    queryFn: fetchPluginDevelopment,
    refetchInterval: 1000,
  });
  const { data: plugins = [] } = useQuery({
    queryKey: PLUGINS_QUERY_KEY,
    queryFn: fetchPlugins,
    refetchInterval: 1000,
  });
  const selected = search.get("pluginId") ?? development?.pluginId ?? plugins[0]?.id ?? "";
  const plugin = plugins.find((item) => item.id === selected);
  const [chosenView, setChosenView] = useState("");
  const view = plugin?.views.find((item) => item.id === chosenView) ?? plugin?.views[0];
  const [width, setWidth] = useState("960");
  const [theme, setTheme] = useState("light");
  const [language, setLanguage] = useState("zh-CN");
  const [draft, setDraft] = useState("{}");
  const [context, setContext] = useState("{}");
  const [fault, setFault] = useState("");
  const [filter, setFilter] = useState("all");
  const [tab, setTab] = useState("tree");
  const [traceId, setTraceId] = useState<number>();
  const [reloadKey, setReloadKey] = useState(0);
  const inspector = useQuery({
    queryKey: ["plugin-inspector", selected],
    enabled: Boolean(development?.inspector && plugin),
    queryFn: async () =>
      (await apiClient.get<{ entries: PluginDiagnostic[] }>(`/plugins/${selected}/inspector`)).data,
    refetchInterval: 1000,
  });
  const entries = inspector.data?.entries ?? [];
  const visible = entries.filter(
    (entry) =>
      filter === "all" ||
      (filter === "errors" ? entry.status === "error" : entry.kind.includes(filter)),
  );
  const active = entries.find((entry) => entry.sequence === traceId) ?? visible.at(-1);
  const render = [...entries]
    .reverse()
    .find(
      (entry) =>
        entry.kind === "frontend.render" &&
        entry.viewId === view?.id &&
        entry.status === "ok" &&
        entry.result &&
        typeof entry.result === "object" &&
        "document" in entry.result,
    );
  const renderData = render?.result as
    | { document?: { trees?: { tree: unknown }[] }; compiledCSS?: string; warnings?: string[] }
    | undefined;
  useEffect(() => {
    enablePluginDiagnostics(Boolean(development?.inspector));
  }, [development?.inspector]);
  const preview = useMemo(
    () =>
      "/plugin-development-preview?" +
      new URLSearchParams({
        pluginId: selected,
        viewId: view?.id ?? "",
        width,
        theme,
        language,
        context,
      }).toString(),
    [selected, view?.id, width, theme, language, context],
  );
  if (developmentError) return <p role="alert">{pluginError(developmentError)}</p>;
  if (!development) return <p role="status">正在连接开发工具…</p>;
  if (!development.inspector)
    return (
      <section className="plugin-devtools">
        <Heading>插件开发工具未启用</Heading>
        <p>使用 openfic plugin dev 或 openfic serve --plugin-devtools 显式开启。</p>
      </section>
    );
  return (
    <section
      className="plugin-devtools"
      aria-label="插件开发工具"
    >
      <Flex
        align="center"
        gap="3"
        wrap="wrap"
      >
        <Heading size="6">插件开发工具</Heading>
        <Badge color={development.status === "error" ? "red" : "green"}>
          {development.enabled
            ? `热重载 ${development.status} · #${development.revision ?? 0}`
            : "Inspector 已开启"}
        </Badge>
        {development.enabled && (
          <Button
            onClick={() => {
              void apiClient
                .post("/plugins/development/reload")
                .then(() => queryClient.invalidateQueries({ queryKey: ["plugin-development"] }))
                .catch((error) => setFault(pluginError(error)));
            }}
          >
            重新加载源码
          </Button>
        )}
      </Flex>
      {development.source && (
        <Text
          as="p"
          size="2"
          color="gray"
        >
          源码：{development.source}
        </Text>
      )}
      <Text
        as="p"
        size="2"
        color="gray"
      >
        在独立视口中运行真实插件。编辑器操作需要真实编辑器上下文；预览不会伪造写入成功。诊断仅保留最近
        200 条于服务端内存，清空或关闭服务即丢弃。
      </Text>
      {development.diagnostics?.map((item, index) => (
        <p
          key={index}
          className={item.severity === "error" ? "plugin-error" : "plugin-muted"}
          data-diagnostic-code={item.code}
        >
          {item.severity} · {item.file}:{item.line ?? "-"} · {item.message}
        </p>
      ))}
      {fault && <p role="alert">{fault}</p>}
      {!!development.checks?.length && (
        <details>
          <summary>源码检查覆盖范围</summary>
          {development.checks.map((check, index) => (
            <p key={index}>
              {check.name}: {check.status}
              {check.reason ? ` · ${check.reason}` : ""}
            </p>
          ))}
          <Text size="2">
            热重载执行离线预检。需要执行项目脚本时运行 openfic plugin check --run-checks。
          </Text>
        </details>
      )}
      <Flex
        gap="3"
        wrap="wrap"
        align="end"
      >
        <Choice
          label="插件"
          value={selected}
          onChange={(value) => {
            setSearch({ pluginId: value });
            setChosenView("");
            setTraceId(undefined);
          }}
          options={plugins.map((item) => ({ value: item.id, label: item.name }))}
        />
        {view && (
          <Choice
            label="视图 / 插槽"
            value={view.id}
            onChange={setChosenView}
            options={plugin!.views.map((item) => ({
              value: item.id,
              label: `${item.title} · ${item.slot}`,
            }))}
          />
        )}
        <Choice
          label="视口"
          value={width}
          onChange={setWidth}
          options={[
            { value: "960", label: "桌面 · 960px" },
            { value: "768", label: "平板 · 768px" },
            { value: "390", label: "手机 · 390px" },
          ]}
        />
        <Choice
          label="主题"
          value={theme}
          onChange={setTheme}
          options={[
            { value: "light", label: "浅色" },
            { value: "dark", label: "深色" },
          ]}
        />
        <Choice
          label="语言"
          value={language}
          onChange={setLanguage}
          options={[
            { value: "zh-CN", label: "简体中文" },
            { value: "en", label: "English" },
          ]}
        />
        <Button
          variant="soft"
          onClick={() => setReloadKey((value) => value + 1)}
        >
          刷新预览
        </Button>
      </Flex>
      <details className="plugin-devtools-context">
        <summary>预览上下文</summary>
        <TextArea
          aria-label="预览上下文 JSON"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <Button
          onClick={() => {
            try {
              const value: unknown = JSON.parse(draft);
              if (
                !value ||
                typeof value !== "object" ||
                Array.isArray(value) ||
                draft.length > 8000
              )
                throw new Error("上下文必须是 JSON 对象，且不超过 8000 字符");
              setContext(JSON.stringify(value));
              setFault("");
            } catch (error) {
              setFault(pluginError(error));
            }
          }}
        >
          应用上下文
        </Button>
      </details>
      {plugin && (
        <Flex
          gap="2"
          wrap="wrap"
        >
          {plugin.capabilities.map((capability) => (
            <Badge key={capability}>{capability}</Badge>
          ))}
        </Flex>
      )}
      <div className="plugin-devtools-layout">
        <div className="plugin-devtools-stage">
          {plugin && view ? (
            <iframe
              key={`${selected}:${view.id}:${reloadKey}`}
              src={preview}
              title="插件独立视口预览"
              className="plugin-devtools-preview"
              style={{ width: Number(width), height: 660 }}
            />
          ) : (
            <p>没有可预览视图。使用 openfic plugin dev 启动插件源码。</p>
          )}
        </div>
        <section
          className="plugin-devtools-inspector"
          aria-label="插件 Inspector"
        >
          <Flex
            gap="2"
            wrap="wrap"
          >
            <Button
              variant={tab === "tree" ? "solid" : "soft"}
              onClick={() => setTab("tree")}
            >
              组件树 / Props
            </Button>
            <Button
              variant={tab === "css" ? "solid" : "soft"}
              onClick={() => setTab("css")}
            >
              CSS
            </Button>
            <Button
              variant={tab === "trace" ? "solid" : "soft"}
              onClick={() => setTab("trace")}
            >
              调用 / 事件
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                void apiClient
                  .delete(`/plugins/${selected}/inspector`)
                  .then(() => {
                    setTraceId(undefined);
                    return inspector.refetch();
                  })
                  .catch((error) => setFault(pluginError(error)));
              }}
            >
              清空记录
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                const url = URL.createObjectURL(
                  new Blob([JSON.stringify({ pluginId: selected, entries }, null, 2)], {
                    type: "application/json",
                  }),
                );
                const a = document.createElement("a");
                a.href = url;
                a.download = `${selected}-diagnostics.json`;
                a.click();
                setTimeout(() => URL.revokeObjectURL(url), 1000);
              }}
            >
              导出诊断
            </Button>
          </Flex>
          {inspector.error && <p role="alert">{pluginError(inspector.error)}</p>}
          {tab === "tree" && (
            <div data-inspector="tree">
              {renderData?.document?.trees ? (
                renderData.document.trees.map((tree, index) => (
                  <TreeInspector
                    key={index}
                    node={tree.tree}
                  />
                ))
              ) : (
                <p>等待预览渲染。超出诊断大小上限时文档会标记截断。</p>
              )}
              <details>
                <summary>实际上下文</summary>
                <JSONView value={render?.request} />
              </details>
            </div>
          )}
          {tab === "css" && (
            <div data-inspector="css">
              {renderData?.warnings?.map((warning, index) => (
                <p
                  role="status"
                  key={index}
                >
                  {warning}
                </p>
              ))}
              <Heading size="3">原始 CSS</Heading>
              <JSONView value={(renderData?.document as { css?: string })?.css} />
              <Heading size="3">宿主编译后的 CSS</Heading>
              <pre className="plugin-devtools-json">
                {renderData?.compiledCSS ?? "等待样式诊断…"}
              </pre>
            </div>
          )}
          {tab === "trace" && (
            <div data-inspector="trace">
              <Choice
                label="记录筛选"
                value={filter}
                onChange={setFilter}
                options={[
                  { value: "all", label: "全部" },
                  { value: "errors", label: "错误" },
                  { value: "sdk", label: "SDK" },
                  { value: "hook", label: "Agent Hook" },
                  { value: "observer", label: "提交后事件" },
                  { value: "frontend", label: "前端 / Action" },
                ]}
              />
              <div className="plugin-devtools-traces">
                {[...visible].reverse().map((entry) => (
                  <button
                    key={entry.sequence}
                    type="button"
                    data-status={entry.status}
                    aria-pressed={active?.sequence === entry.sequence}
                    onClick={() => setTraceId(entry.sequence)}
                  >
                    {entry.kind} · {entry.method} · {entry.status} · {entry.durationMs?.toFixed(1)}
                    ms
                  </button>
                ))}
              </div>
              <JSONView value={active} />
            </div>
          )}
        </section>
      </div>
    </section>
  );
}

export function PluginDevelopmentCanvas() {
  const [search] = useSearchParams();
  const { i18n } = useTranslation();
  const { data: development } = useQuery({
    queryKey: ["plugin-development"],
    queryFn: fetchPluginDevelopment,
    refetchInterval: 1000,
  });
  const { data: plugins = [] } = useQuery({
    queryKey: PLUGINS_QUERY_KEY,
    queryFn: fetchPlugins,
    refetchInterval: 1000,
  });
  const plugin = plugins.find((item) => item.id === search.get("pluginId"));
  const view = plugin?.views.find((item) => item.id === search.get("viewId"));
  const appearance = search.get("theme") === "dark" ? "dark" : "light";
  const language = search.get("language") ?? "zh-CN";
  const { data: settings } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
    enabled: Boolean(development?.inspector),
    staleTime: 30000,
  });
  useEffect(() => {
    if (!development?.inspector) return;
    const preset =
      (appearance === "dark" ? settings?.darkThemePreset : settings?.lightThemePreset) ??
      DEFAULT_THEME_PRESET_ID;
    const palette = resolveThemePalette(
      preset,
      settings?.themeConfig ?? DEFAULT_THEME_CONFIG,
      appearance,
    );
    // This page lives in its own document; update the real project palette and
    // its portal observer without changing the surrounding Inspector's theme.
    applyThemePalette(palette, appearance, preset);
  }, [appearance, settings, development?.inspector]);
  useEffect(() => {
    enablePluginDiagnostics(Boolean(development?.inspector));
  }, [development?.inspector]);
  useEffect(() => {
    void i18n.changeLanguage(language);
  }, [i18n, language]);
  let context: Record<string, unknown> = {};
  try {
    const value: unknown = JSON.parse(search.get("context") ?? "{}");
    if (value && typeof value === "object" && !Array.isArray(value))
      context = value as Record<string, unknown>;
  } catch {
    /* Show default context after invalid manual URLs. */
  }
  if (!development?.inspector) return <p>开发工具未启用</p>;
  if (!plugin || !view) return <p>插件视图不可用</p>;
  if (plugin.status !== "enabled") return <p>请在插件管理中启用此插件。</p>;
  const frame = (
    <PluginFrame
      plugin={plugin}
      view={view}
      context={{ ...context, theme: appearance }}
      embedded
    />
  );
  return (
    <Theme
      appearance={appearance}
      hasBackground
      className="plugin-development-canvas"
    >
      <PluginRuntime />
      <Text
        as="p"
        size="1"
        color="gray"
      >
        {view.slot} · {plugin.version} · reload #{plugin.development_revision ?? 0}
      </Text>
      <PreviewSlot view={view}>{frame}</PreviewSlot>
    </Theme>
  );
}
function PreviewSlot({ view, children }: { view: PluginView; children: React.ReactNode }) {
  const toolbar = [
    "editor.toolbar",
    "editor.context",
    "editor.panel",
    "project.toolbar",
    "assistant.toolbar",
    "statusbar",
  ].includes(view.slot);
  if (toolbar && (view.presentation === "dialog" || view.slot === "editor.panel"))
    return (
      <Dialog.Root>
        <Dialog.Trigger>
          <Button>{view.title}</Button>
        </Dialog.Trigger>
        <Dialog.Content>
          <Dialog.Title>{view.title}</Dialog.Title>
          {children}
        </Dialog.Content>
      </Dialog.Root>
    );
  if (toolbar)
    return (
      <Box className="plugin-development-toolbar">
        <Text size="2">工具栏预览</Text>
        <Popover.Root>
          <Popover.Trigger>
            <Button>{view.title}</Button>
          </Popover.Trigger>
          <Popover.Content
            style={{ maxWidth: "calc(100vw - 24px)", maxHeight: "80dvh", overflow: "auto" }}
          >
            {children}
          </Popover.Content>
        </Popover.Root>
      </Box>
    );
  if (view.slot === "app.overlay") return <div className="plugin-overlays">{children}</div>;
  return (
    <Box
      className={view.slot === "assistant.above-prompt" ? "plugin-slot-assistant-above-prompt" : ""}
    >
      {children}
      {view.slot === "assistant.above-prompt" && (
        <TextField.Root
          placeholder="输入框区域预览"
          readOnly
        />
      )}
    </Box>
  );
}

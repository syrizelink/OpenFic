import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { restrictToFirstScrollableAncestor, restrictToVerticalAxis } from "@dnd-kit/modifiers";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  Badge,
  Button,
  Checkbox,
  Dialog,
  Flex,
  Heading,
  IconButton,
  Select,
  Skeleton,
  Switch,
  Text,
  TextArea,
  TextField,
} from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, GripVertical, Package, Plus, RefreshCw, TriangleAlert } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { defaultUrlTransform } from "streamdown";

import { ConfirmDialog, StreamingMarkdown, Tabs, toast } from "@/components";
import { apiClient, getApiBaseUrl } from "@/lib/api-client";
import { openExternalLink } from "@/lib/desktop-appearance-bridge";

import {
  downloadPlugin,
  pluginsQueryOptions,
  fetchPluginDevelopment,
  installPlugin,
  pluginError,
  savePluginOrder,
  PLUGINS_QUERY_KEY,
  type InstalledPlugin,
} from "./api";
import { PluginSlot } from "./plugin-slot";

import "./plugins.css";

const PLUGIN_RISK_ACKNOWLEDGED_KEY = "openfic-plugin-risk-acknowledged";

function getPluginHomepage(value: string | null | undefined): URL | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password
      ? url
      : null;
  } catch {
    return null;
  }
}

function PluginIcon({
  plugin,
  placement,
}: {
  plugin: InstalledPlugin;
  placement: "list" | "detail";
}) {
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const source = plugin.icon
    ? `${getApiBaseUrl()}/plugins/${encodeURIComponent(plugin.id)}/icon?${new URLSearchParams({
        version: plugin.version,
        revision: String(plugin.development_revision ?? 0),
        path: plugin.icon,
      })}`
    : null;
  if (!source || failedSource === source)
    return placement === "list" ? (
      <Package
        size={14}
        aria-hidden="true"
      />
    ) : null;
  return (
    <img
      className={placement === "list" ? "plugin-icon-list" : "plugin-icon-detail"}
      src={source}
      alt=""
      aria-hidden="true"
      onError={() => setFailedSource(source)}
    />
  );
}

interface PluginManagerProps {
  onOpenView?: () => void;
  mobilePage: "list" | "detail";
  onMobileDetailTitleChange: (title: string | null) => void;
  onMobilePageChange: (page: "list" | "detail") => void;
}

export function PluginManager({
  onOpenView,
  mobilePage,
  onMobileDetailTitleChange,
  onMobilePageChange,
}: PluginManagerProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { data: development } = useQuery({
    queryKey: ["plugin-development"],
    queryFn: fetchPluginDevelopment,
    staleTime: 30000,
  });
  const {
    data: plugins = [],
    isLoading,
    isFetching,
    error: loadError,
    refetch,
  } = useQuery(pluginsQueryOptions);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [riskAcknowledged, setRiskAcknowledged] = useState(() => {
    try {
      return localStorage.getItem(PLUGIN_RISK_ACKNOWLEDGED_KEY) === "true";
    } catch {
      return false;
    }
  });
  const plugin = plugins.find((entry) => entry.id === selectedId) ?? plugins[0];
  const homepage = getPluginHomepage(plugin?.homepage);
  const {
    data: detail,
    isError: detailError,
    isLoading: isDetailLoading,
  } = useQuery({
    queryKey: [
      "plugin-detail",
      plugin?.id,
      plugin?.version,
      plugin?.development_revision,
      plugin?.detail,
    ],
    queryFn: async () =>
      (await apiClient.get<string>(`/plugins/${plugin!.id}/detail`, { responseType: "text" })).data,
    enabled: !!plugin?.detail,
  });
  const hasIntroduction =
    !!plugin?.detail && (detail === undefined || detailError || !!detail.trim());
  const [trusted, setTrusted] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isRefreshSpinning, setIsRefreshSpinning] = useState(false);
  const refreshFinished = useRef(false);
  const [installation, setInstallation] = useState<{ updateId?: string } | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [dropPosition, setDropPosition] = useState<{ row: HTMLElement; top: number } | null>(null);
  const [logs, setLogs] = useState<{
    id: string;
    entries: { time: string; level: string; action: string; message: string }[];
  } | null>(null);
  const [removing, setRemoving] = useState<InstalledPlugin | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const orderMutation = useMutation({
    mutationFn: ({ pluginIds }: { pluginIds: string[]; previous: InstalledPlugin[] }) =>
      savePluginOrder(pluginIds),
    onError: (failure, { previous }) => {
      queryClient.setQueryData(PLUGINS_QUERY_KEY, previous);
      toast.error(pluginError(failure));
      return queryClient.invalidateQueries({ queryKey: PLUGINS_QUERY_KEY });
    },
    onSuccess: () => toast.success(t("plugins.orderSaved")),
  });
  const busy = isRunning || orderMutation.isPending;

  useLayoutEffect(() => {
    if (!dropPosition || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const { row, top } = dropPosition;
    const offset = top - row.getBoundingClientRect().top;
    if (offset)
      row.animate([{ transform: `translateY(${offset}px)` }, { transform: "none" }], {
        duration: 200,
        easing: "ease",
      });
  }, [dropPosition]);

  useEffect(() => {
    onMobileDetailTitleChange(plugin?.name ?? null);
  }, [onMobileDetailTitleChange, plugin?.name]);

  useEffect(() => {
    if (loadError) toast.error(pluginError(loadError), { id: "plugin-manager-load-error" });
  }, [loadError]);

  async function run(action: () => Promise<void>, success?: string) {
    setIsRunning(true);
    try {
      await action();
      if (success) toast.success(success);
    } catch (failure) {
      toast.error(pluginError(failure));
    } finally {
      await queryClient.invalidateQueries({ queryKey: PLUGINS_QUERY_KEY });
      setIsRunning(false);
    }
  }

  function handleOpenInstallation(updateId?: string) {
    setTrusted(false);
    setInstallation({ updateId });
  }

  function handleDragEnd({ active, over }: DragEndEvent) {
    const row = Array.from(
      listRef.current?.querySelectorAll<HTMLElement>(".plugin-list-row") ?? [],
    ).find((element) => element.dataset.sortablePluginId === active.id);
    const previousTop = row?.getBoundingClientRect().top;
    if (row && previousTop !== undefined) setDropPosition({ row, top: previousTop });
    if (busy || !over || active.id === over.id) return;
    const from = plugins.findIndex((entry) => entry.id === active.id);
    const to = plugins.findIndex((entry) => entry.id === over.id);
    if (from < 0 || to < 0) return;
    setSelectedId(plugin?.id ?? null);
    const reordered = arrayMove(plugins, from, to);
    void queryClient.cancelQueries({ queryKey: PLUGINS_QUERY_KEY });
    queryClient.setQueryData(PLUGINS_QUERY_KEY, reordered);
    orderMutation.mutate({ pluginIds: reordered.map((entry) => entry.id), previous: plugins });
  }

  return (
    <section
      className="plugin-manager"
      aria-label={t("plugins.management")}
      data-mobile-page={mobilePage}
    >
      <div
        className="plugin-manager-layout"
        inert={!riskAcknowledged}
      >
        <div className="plugin-list-panel">
          <Flex
            align="center"
            justify="between"
            gap="2"
            className="plugin-list-header"
          >
            <Text
              size="2"
              weight="medium"
            >
              {t("plugins.totalCount", { count: plugins.length })}
            </Text>
            <Flex gap="1">
              <IconButton
                variant="ghost"
                color="gray"
                size="2"
                aria-label={t("plugins.install")}
                disabled={busy}
                onClick={() => handleOpenInstallation()}
              >
                <Plus size={14} />
              </IconButton>
              <IconButton
                variant="ghost"
                color="gray"
                size="2"
                aria-label={t("common.refresh")}
                disabled={isFetching || isRefreshSpinning || busy}
                onClick={() => {
                  refreshFinished.current = false;
                  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches)
                    setIsRefreshSpinning(true);
                  void refetch().finally(() => {
                    refreshFinished.current = true;
                  });
                }}
              >
                <RefreshCw
                  size={14}
                  className={isRefreshSpinning ? "animate-spin" : undefined}
                  onAnimationIteration={() => {
                    if (refreshFinished.current) setIsRefreshSpinning(false);
                  }}
                />
              </IconButton>
            </Flex>
          </Flex>
          <Text
            as="p"
            size="1"
            color="gray"
            className="plugin-list-hint"
          >
            {t("plugins.orderHint")}
          </Text>
          <div
            ref={listRef}
            className="plugin-list-body"
          >
            {isLoading ? (
              <Text
                size="2"
                color="gray"
              >
                {t("plugins.loading")}
              </Text>
            ) : plugins.length === 0 && !loadError ? (
              <Text
                size="2"
                color="gray"
                className="plugin-list-empty"
              >
                {t("plugins.empty")}
              </Text>
            ) : (
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                modifiers={[restrictToVerticalAxis, restrictToFirstScrollableAncestor]}
                onDragEnd={handleDragEnd}
              >
                <SortableContext
                  items={plugins.map((entry) => entry.id)}
                  strategy={verticalListSortingStrategy}
                >
                  {plugins.map((entry) => (
                    <PluginListItem
                      key={entry.id}
                      plugin={entry}
                      selected={plugin?.id === entry.id}
                      disabled={busy || plugins.length < 2}
                      switchDisabled={busy}
                      onToggle={(enabled) =>
                        void run(async () => {
                          await apiClient.patch(`/plugins/${entry.id}/enabled`, { enabled });
                        })
                      }
                      onSelect={() => {
                        setSelectedId(entry.id);
                        onMobilePageChange("detail");
                      }}
                    />
                  ))}
                </SortableContext>
              </DndContext>
            )}
          </div>
          {development?.inspector && (
            <div className="plugin-list-footer">
              <Button
                asChild
                variant="soft"
                color="gray"
                size="1"
              >
                <Link
                  to="/extensions/devtools"
                  onClick={onOpenView}
                >
                  {t("plugins.devtools")}
                </Link>
              </Button>
            </div>
          )}
        </div>
        <div className="plugin-detail-panel">
          {plugin ? (
            <div
              className="plugin-detail"
              key={plugin.id}
              data-plugin-id={plugin.id}
            >
              <section className="plugin-detail-section">
                <Flex
                  align="center"
                  gap="3"
                >
                  <PluginIcon
                    plugin={plugin}
                    placement="detail"
                  />
                  <Flex
                    direction="column"
                    gap="1"
                    className="plugin-detail-identity"
                  >
                    <Flex
                      align="center"
                      gap="2"
                      wrap="wrap"
                    >
                      <Text
                        size="3"
                        weight="bold"
                      >
                        {plugin.name}
                      </Text>
                      <Badge color="green">{plugin.version}</Badge>
                    </Flex>
                    <Text
                      size="1"
                      color="gray"
                    >
                      {plugin.author ? `@${plugin.author}/${plugin.id}` : plugin.id}
                    </Text>
                  </Flex>
                  {homepage && (
                    <IconButton
                      asChild
                      className="plugin-homepage-link"
                      size="1"
                      variant="ghost"
                      color="gray"
                    >
                      <a
                        href={homepage.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={t("plugins.openHomepage")}
                        title={t("plugins.openHomepage")}
                        onClick={(event) => {
                          event.preventDefault();
                          openExternalLink(homepage.href);
                        }}
                      >
                        {["github.com", "www.github.com"].includes(
                          homepage.hostname.replace(/\.$/, ""),
                        ) ? (
                          <span
                            className="plugin-homepage-github"
                            aria-hidden="true"
                          />
                        ) : (
                          <ExternalLink
                            size={16}
                            aria-hidden="true"
                          />
                        )}
                      </a>
                    </IconButton>
                  )}
                </Flex>
                <PluginDescription
                  key={plugin.description}
                  description={plugin.description || t("plugins.noDescription")}
                />
                {plugin.error && (
                  <Text
                    as="p"
                    size="2"
                    color="red"
                    role="alert"
                  >
                    {plugin.error}
                  </Text>
                )}
              </section>
              <Tabs.Root
                key={`${plugin.id}:${hasIntroduction}`}
                className="plugin-detail-tabs"
                defaultValue={hasIntroduction ? "introduction" : "settings"}
              >
                <Tabs.List>
                  {hasIntroduction && (
                    <Tabs.Trigger value="introduction">{t("plugins.tabIntroduction")}</Tabs.Trigger>
                  )}
                  <Tabs.Trigger value="settings">{t("plugins.tabSettings")}</Tabs.Trigger>
                  <Tabs.Trigger value="management">{t("plugins.tabManagement")}</Tabs.Trigger>
                  <Tabs.Trigger value="information">{t("plugins.tabInformation")}</Tabs.Trigger>
                </Tabs.List>
                {hasIntroduction && (
                  <Tabs.Content
                    value="introduction"
                    className="plugin-detail-tab-content"
                  >
                    {detailError ? (
                      <Text
                        size="2"
                        color="red"
                      >
                        {t("plugins.detailFailed")}
                      </Text>
                    ) : isDetailLoading ? (
                      <Flex
                        direction="column"
                        gap="3"
                        role="status"
                        aria-label={t("common.loading")}
                      >
                        <Skeleton
                          width="45%"
                          height="24px"
                          mb="2"
                        />
                        <Skeleton
                          width="100%"
                          height="16px"
                        />
                        <Skeleton
                          width="100%"
                          height="16px"
                        />
                        <Skeleton
                          width="72%"
                          height="16px"
                        />
                      </Flex>
                    ) : detail ? (
                      <StreamingMarkdown
                        content={detail}
                        showImageDownload={false}
                        urlTransform={(url, key, node) => {
                          if (node.tagName !== "img" || key !== "src")
                            return defaultUrlTransform(url, key, node);
                          const base = new URL(
                            plugin.detail!.split("/").map(encodeURIComponent).join("/"),
                            "https://plugin-detail.invalid/",
                          );
                          try {
                            const image = new URL(url, base);
                            if (image.origin !== base.origin)
                              return defaultUrlTransform(url, key, node);
                            return `${getApiBaseUrl()}/plugins/${encodeURIComponent(plugin.id)}/detail-images${image.pathname}${image.search}${image.hash}`;
                          } catch {
                            return "";
                          }
                        }}
                      />
                    ) : null}
                  </Tabs.Content>
                )}
                <Tabs.Content
                  value="settings"
                  forceMount
                  className="plugin-detail-tab-content"
                >
                  {plugin.settings.length > 0 ? (
                    <PluginConfiguration
                      key={`${plugin.id}:${JSON.stringify(plugin.configuration)}`}
                      plugin={plugin}
                      disabled={busy}
                      onSave={(settings) =>
                        run(async () => {
                          await apiClient.put(`/plugins/${plugin.id}/settings`, { settings });
                        }, t("plugins.saved"))
                      }
                    />
                  ) : (
                    <Text
                      size="2"
                      color="gray"
                    >
                      {t("plugins.noConfiguration")}
                    </Text>
                  )}
                </Tabs.Content>
                <Tabs.Content
                  value="management"
                  className="plugin-detail-tab-content plugin-detail-section"
                >
                  <Flex
                    wrap="wrap"
                    gap="2"
                  >
                    <Button
                      size="2"
                      variant="soft"
                      color="gray"
                      disabled={busy}
                      onClick={() => handleOpenInstallation(plugin.id)}
                    >
                      {t("plugins.update")}
                    </Button>
                    <Button
                      size="2"
                      variant="soft"
                      color="gray"
                      disabled={busy}
                      onClick={() => void run(() => downloadPlugin(plugin))}
                    >
                      {t("plugins.export")}
                    </Button>
                    <Button
                      size="2"
                      variant="soft"
                      color="gray"
                      disabled={busy}
                      onClick={() =>
                        void run(async () => {
                          const { data } = await apiClient.get(`/plugins/${plugin.id}/logs`);
                          setLogs({ id: plugin.id, entries: data });
                        })
                      }
                    >
                      {t("plugins.logs")}
                    </Button>
                    <Button
                      size="2"
                      variant="soft"
                      color="red"
                      disabled={busy}
                      onClick={() => setRemoving(plugin)}
                    >
                      {t("plugins.uninstall")}
                    </Button>
                  </Flex>
                  {plugin.status === "enabled" &&
                    plugin.views.filter((view) => view.slot === "sidebar.extensions").length >
                      0 && (
                      <Flex
                        wrap="wrap"
                        gap="2"
                      >
                        {plugin.views
                          .filter((view) => view.slot === "sidebar.extensions")
                          .map((view) => (
                            <Button
                              asChild
                              key={view.id}
                              size="2"
                              variant="outline"
                            >
                              <Link
                                to={`/extensions/${plugin.id}/${view.id}`}
                                onClick={onOpenView}
                              >
                                {view.title}
                              </Link>
                            </Button>
                          ))}
                      </Flex>
                    )}
                </Tabs.Content>
                <Tabs.Content
                  value="information"
                  className="plugin-detail-tab-content"
                >
                  <dl className="plugin-information">
                    <div className="plugin-information-row">
                      <dt>{t("plugins.informationId")}</dt>
                      <dd>{plugin.id}</dd>
                    </div>
                    <div className="plugin-information-row">
                      <dt>{t("plugins.informationVersion")}</dt>
                      <dd>{plugin.version}</dd>
                    </div>
                    <div className="plugin-information-row">
                      <dt>{t("plugins.informationAuthor")}</dt>
                      <dd>{plugin.author || t("plugins.none")}</dd>
                    </div>
                    {homepage && (
                      <div className="plugin-information-row">
                        <dt>{t("plugins.informationHomepage")}</dt>
                        <dd>
                          <a
                            href={homepage.href}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(event) => {
                              event.preventDefault();
                              openExternalLink(homepage.href);
                            }}
                          >
                            {homepage.href}
                          </a>
                        </dd>
                      </div>
                    )}
                    <div className="plugin-information-row">
                      <dt>{t("plugins.capabilities")}</dt>
                      <dd className="plugin-permission-value">
                        {plugin.capabilities.length ? (
                          <PluginPermissions capabilities={plugin.capabilities} />
                        ) : (
                          t("plugins.none")
                        )}
                      </dd>
                    </div>
                  </dl>
                </Tabs.Content>
              </Tabs.Root>
              <PluginSlot slot="settings.plugins" />
            </div>
          ) : (
            <Flex
              direction="column"
              align="center"
              justify="center"
              gap="3"
              className="plugin-detail-empty"
            >
              <Package
                size={32}
                aria-hidden="true"
              />
              <Text
                size="2"
                color="gray"
              >
                {t("plugins.description")}
              </Text>
              <Button
                variant="soft"
                disabled={busy || isLoading}
                onClick={() => handleOpenInstallation()}
              >
                {t("plugins.install")}
              </Button>
            </Flex>
          )}
        </div>
      </div>
      {!riskAcknowledged && (
        <div className="plugin-risk-overlay">
          <div
            className="plugin-risk-notice"
            role="region"
            aria-labelledby="plugin-risk-title"
          >
            <TriangleAlert
              size={24}
              aria-hidden="true"
            />
            <Heading
              as="h3"
              size="4"
              id="plugin-risk-title"
            >
              {t("plugins.riskTitle")}
            </Heading>
            <Text
              as="p"
              size="2"
              color="gray"
            >
              {t("plugins.riskDescription")}
            </Text>
            <Button
              onClick={() => {
                try {
                  localStorage.setItem(PLUGIN_RISK_ACKNOWLEDGED_KEY, "true");
                } catch {
                  // Storage may be unavailable in private browsing.
                }
                setRiskAcknowledged(true);
              }}
            >
              {t("plugins.riskConfirm")}
            </Button>
          </div>
        </div>
      )}
      <Dialog.Root
        open={installation !== null}
        onOpenChange={(open) => {
          if (!open && !busy) setInstallation(null);
        }}
      >
        <Dialog.Content className="plugin-install-dialog">
          <Dialog.Title>
            {t(installation?.updateId ? "plugins.update" : "plugins.install")}
          </Dialog.Title>
          <Dialog.Description
            size="2"
            color="gray"
          >
            {t("plugins.description")}
          </Dialog.Description>
          <Text
            as="label"
            size="2"
            className="plugin-trust-label"
          >
            <Checkbox
              checked={trusted}
              onCheckedChange={(value) => setTrusted(value === true)}
              disabled={busy}
            />
            {t("plugins.trust")}
          </Text>
          <Flex
            gap="2"
            justify="end"
          >
            <Button
              variant="soft"
              color="gray"
              disabled={busy}
              onClick={() => setInstallation(null)}
            >
              {t("plugins.cancel")}
            </Button>
            <Button
              disabled={!trusted || busy}
              onClick={() => uploadRef.current?.click()}
            >
              {t(busy ? "plugins.working" : "plugins.selectPackage")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
      <input
        ref={uploadRef}
        type="file"
        accept=".zip"
        hidden
        aria-label={t("plugins.package")}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file && trusted && installation)
            void run(async () => {
              await installPlugin(file, installation.updateId);
              setInstallation(null);
            }, t("plugins.installed"));
          event.target.value = "";
        }}
      />
      <ConfirmDialog
        open={removing !== null}
        onOpenChange={(open) => {
          if (!open && !busy) setRemoving(null);
        }}
        title={t("plugins.uninstall")}
        description={t("plugins.confirmUninstall", { name: removing?.name })}
        confirmText={t("plugins.confirm")}
        cancelText={t("plugins.cancel")}
        loading={busy}
        onConfirm={() => {
          if (!removing) return;
          void run(async () => {
            await apiClient.delete(`/plugins/${removing.id}`);
            setRemoving(null);
            setLogs(null);
            onMobilePageChange("list");
          });
        }}
      />
      <Dialog.Root
        open={logs !== null}
        onOpenChange={(open) => {
          if (!open) setLogs(null);
        }}
      >
        <Dialog.Content>
          <Dialog.Title>{t("plugins.logs")}</Dialog.Title>
          <Dialog.Description size="2">{logs?.id}</Dialog.Description>
          <pre className="plugin-logs">
            {logs?.entries
              .map((entry) => `${entry.time} [${entry.level}] ${entry.action}: ${entry.message}`)
              .join("\n") || t("plugins.emptyLogs")}
          </pre>
          <Flex justify="end">
            <Dialog.Close>
              <Button
                variant="soft"
                color="gray"
              >
                {t("plugins.close")}
              </Button>
            </Dialog.Close>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
    </section>
  );
}

interface PluginListItemProps {
  plugin: InstalledPlugin;
  selected: boolean;
  disabled: boolean;
  switchDisabled: boolean;
  onToggle: (enabled: boolean) => void;
  onSelect: () => void;
}

function PluginListItem({
  plugin,
  selected,
  disabled,
  switchDisabled,
  onToggle,
  onSelect,
}: PluginListItemProps) {
  const { t } = useTranslation();
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: plugin.id, disabled });
  return (
    <div
      ref={setNodeRef}
      className="plugin-list-row"
      data-sortable-plugin-id={plugin.id}
      data-selected={selected}
      data-dragging={isDragging}
      style={{
        transform: CSS.Transform.toString(transform),
        transition: [transition, "background-color 140ms ease", "color 140ms ease"]
          .filter(Boolean)
          .join(", "),
      }}
    >
      <button
        ref={setActivatorNodeRef}
        {...attributes}
        {...listeners}
        type="button"
        className="plugin-list-drag-handle"
        disabled={disabled}
        aria-label={t("plugins.reorder", { name: plugin.name })}
      >
        <GripVertical
          size={14}
          aria-hidden="true"
        />
      </button>
      <div className="plugin-list-item">
        <Flex
          align="center"
          gap="2"
          className="plugin-list-heading"
        >
          <button
            type="button"
            className="plugin-list-title"
            aria-pressed={selected}
            onClick={onSelect}
          >
            <PluginIcon
              plugin={plugin}
              placement="list"
            />
            <Text
              size="2"
              truncate
              weight={selected ? "medium" : "regular"}
            >
              {plugin.name}
            </Text>
            <Badge
              size="1"
              color="green"
              variant="soft"
            >
              {plugin.version}
            </Badge>
          </button>
          <Switch
            className="plugin-list-switch"
            size="1"
            checked={plugin.status === "enabled"}
            disabled={switchDisabled}
            aria-label={`${plugin.name}: ${t(plugin.status === "enabled" ? "plugins.disable" : "plugins.enable")}`}
            onCheckedChange={onToggle}
          />
        </Flex>
        <span className="plugin-list-description">
          {plugin.description || t("plugins.noDescription")}
        </span>
      </div>
    </div>
  );
}

function PluginDescription({ description }: { description: string }) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const measureRef = useRef<HTMLParagraphElement>(null);
  const measureTextRef = useRef<HTMLSpanElement>(null);
  const measureSuffixRef = useRef<HTMLSpanElement>(null);
  const [prefix, setPrefix] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const expandLabel = t("plugins.expandDescription");

  useLayoutEffect(() => {
    const container = containerRef.current;
    const measure = measureRef.current;
    const measureText = measureTextRef.current;
    const suffix = measureSuffixRef.current;
    if (!container || !measure || !measureText || !suffix) return;
    let isActive = true;

    const updateTruncation = () => {
      if (!container.getBoundingClientRect().width) return;
      const lineHeight = Number.parseFloat(getComputedStyle(measure).lineHeight);
      if (!Number.isFinite(lineHeight)) return;
      const maxHeight = lineHeight * 2 + 0.5;
      measureText.textContent = description;
      suffix.hidden = true;
      if (measure.getBoundingClientRect().height <= maxHeight) {
        setPrefix(null);
        return;
      }
      suffix.hidden = false;
      const graphemes = Array.from(
        new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(description),
        (item) => item.segment,
      );
      let low = 0;
      let high = graphemes.length;
      while (low < high) {
        const middle = Math.ceil((low + high) / 2);
        measureText.textContent = graphemes.slice(0, middle).join("").trimEnd();
        if (measure.getBoundingClientRect().height <= maxHeight) low = middle;
        else high = middle - 1;
      }
      setPrefix(graphemes.slice(0, low).join("").trimEnd());
    };

    updateTruncation();
    const observer = new ResizeObserver(updateTruncation);
    observer.observe(container);
    document.fonts.addEventListener("loadingdone", updateTruncation);
    void document.fonts.ready.then(() => {
      if (isActive) updateTruncation();
    });
    return () => {
      isActive = false;
      observer.disconnect();
      document.fonts.removeEventListener("loadingdone", updateTruncation);
    };
  }, [description, expandLabel]);

  return (
    <div
      ref={containerRef}
      className="plugin-description"
    >
      <Text
        as="p"
        size="2"
        color="gray"
        className="plugin-description-text"
      >
        {isExpanded || prefix === null ? description : prefix}
        {(isExpanded || prefix !== null) && (
          <span className="plugin-description-suffix">
            {!isExpanded && "..."}
            <button
              type="button"
              className="plugin-description-expand"
              aria-expanded={isExpanded}
              onClick={() => setIsExpanded(!isExpanded)}
            >
              {isExpanded ? t("plugins.collapseDescription") : expandLabel}
            </button>
          </span>
        )}
      </Text>
      <div
        className="plugin-description-measure-container"
        aria-hidden="true"
      >
        <Text
          as="p"
          size="2"
          color="gray"
          className="plugin-description-text"
          ref={measureRef}
        >
          <span ref={measureTextRef} />
          <span
            ref={measureSuffixRef}
            className="plugin-description-suffix"
          >
            ...<span className="plugin-description-expand">{expandLabel}</span>
          </span>
        </Text>
      </div>
    </div>
  );
}

function PluginPermissions({ capabilities }: { capabilities: string[] }) {
  const { t, i18n } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const measureRef = useRef<HTMLDivElement>(null);
  const counterRef = useRef<HTMLButtonElement>(null);
  const [visibleCount, setVisibleCount] = useState(0);
  const [isExpanded, setIsExpanded] = useState(false);
  const labels = capabilities.map((capability) => {
    const key = `plugins.capabilityNames.${capability.replaceAll(".", "_")}`;
    if (i18n.exists(key)) return t(key);
    const [resource, action, ...rest] = capability.split(".");
    const resourceKey = `plugins.capabilityResources.${resource}`;
    if (rest.length === 0 && (action === "read" || action === "write") && i18n.exists(resourceKey))
      return t(`plugins.capabilityActions.${action}`, { resource: t(resourceKey) });
    return capability;
  });

  useLayoutEffect(() => {
    const container = containerRef.current;
    const measure = measureRef.current;
    const counter = counterRef.current;
    if (!container || !measure || !counter) return;

    const updateVisibleCount = () => {
      const available = container.getBoundingClientRect().width;
      const widths = Array.from(
        measure.children,
        (element) => element.getBoundingClientRect().width,
      );
      const gap = Number.parseFloat(getComputedStyle(measure).columnGap) || 0;
      const total = widths.reduce((sum, width) => sum + width, 0) + gap * (widths.length - 1);
      if (total <= available) {
        setVisibleCount(widths.length);
        return;
      }
      for (let count = widths.length - 1; count >= 0; count--) {
        counter.textContent = `+${widths.length - count}`;
        const used = widths.slice(0, count).reduce((sum, width) => sum + width, 0);
        if (used + gap * count + counter.getBoundingClientRect().width <= available) {
          setVisibleCount(count);
          return;
        }
      }
      setVisibleCount(0);
    };

    updateVisibleCount();
    const observer = new ResizeObserver(updateVisibleCount);
    observer.observe(container);
    observer.observe(measure);
    return () => observer.disconnect();
  }, [capabilities, i18n.resolvedLanguage, t]);

  const hiddenCount = capabilities.length - visibleCount;
  return (
    <div
      ref={containerRef}
      className="plugin-permission-list"
      data-expanded={isExpanded}
      role="group"
      aria-label={t("plugins.capabilities")}
      tabIndex={-1}
    >
      {labels.slice(0, isExpanded ? labels.length : visibleCount).map((label, index) => (
        <Badge
          key={`${capabilities[index]}:${index}`}
          size="1"
          color="gray"
          variant="soft"
        >
          {label}
        </Badge>
      ))}
      {!isExpanded && hiddenCount > 0 && (
        <Badge
          asChild
          size="1"
          color="gray"
          variant="soft"
        >
          <button
            type="button"
            className="plugin-permission-more"
            aria-label={t("plugins.expandPermissions", { count: hiddenCount })}
            onClick={(event) => {
              if (event.detail === 0) containerRef.current?.focus();
              setIsExpanded(true);
            }}
          >
            +{hiddenCount}
          </button>
        </Badge>
      )}
      <div
        className="plugin-permission-measure"
        aria-hidden="true"
      >
        <div
          ref={measureRef}
          className="plugin-permission-measure-items"
        >
          {labels.map((label, index) => (
            <Badge
              key={`${capabilities[index]}:${index}`}
              size="1"
              color="gray"
              variant="soft"
            >
              {label}
            </Badge>
          ))}
        </div>
        <Badge
          asChild
          size="1"
          color="gray"
          variant="soft"
        >
          <button
            ref={counterRef}
            type="button"
            tabIndex={-1}
            className="plugin-permission-more"
          />
        </Badge>
      </div>
    </div>
  );
}

interface PluginConfigurationProps {
  plugin: InstalledPlugin;
  disabled: boolean;
  onSave: (settings: InstalledPlugin["configuration"]) => Promise<void>;
}

function isEmptySetting(value: unknown): boolean {
  return value == null || (typeof value === "string" && !value.trim());
}

function PluginConfiguration({ plugin, disabled, onSave }: PluginConfigurationProps) {
  const { t } = useTranslation();
  const [values, setValues] = useState(plugin.configuration);
  const [configError, setConfigError] = useState("");
  const [invalidFields, setInvalidFields] = useState<string[]>([]);

  function handleSettingChange(key: string, value: unknown) {
    setValues({ ...values, [key]: value });
    if (!isEmptySetting(value))
      setInvalidFields((fields) => fields.filter((field) => field !== key));
  }

  return (
    <form
      className="plugin-configuration"
      onSubmit={(event) => {
        event.preventDefault();
        const parsed = { ...values };
        const missing: string[] = [];
        let parseError = "";
        for (const setting of plugin.settings) {
          const key = setting.key;
          const required = setting.required && setting.type !== "select";
          const keepSecret =
            setting.secret && parsed[key] === "" && plugin.configured_secrets?.includes(key);
          if (keepSecret) continue;
          if (isEmptySetting(parsed[key])) {
            if (required) missing.push(key);
            else if (["integer", "number", "json"].includes(setting.type)) delete parsed[key];
            continue;
          }
          if (setting.type === "json" && typeof parsed[key] === "string") {
            try {
              parsed[key] = JSON.parse(parsed[key] as string);
            } catch (error) {
              if (!parseError) parseError = String(error);
              continue;
            }
          }
          if (required && isEmptySetting(parsed[key])) missing.push(key);
        }
        setInvalidFields(missing);
        setConfigError(parseError);
        if (missing.length === 0 && !parseError) void onSave(parsed);
      }}
    >
      {plugin.settings.map((setting) => (
        <div
          key={setting.key}
          className="plugin-setting"
          data-type={setting.type}
          data-invalid={invalidFields.includes(setting.key) || undefined}
        >
          <div className="plugin-setting-label">
            <Text
              size="2"
              weight="medium"
            >
              {setting.label}
              {setting.required && setting.type !== "select" && (
                <Text
                  color="red"
                  aria-hidden="true"
                >
                  {" "}
                  *
                </Text>
              )}
            </Text>
            {setting.description && (
              <Text
                size="1"
                color="gray"
              >
                {setting.description}
              </Text>
            )}
          </div>
          {setting.type === "boolean" ? (
            <Switch
              aria-label={setting.label}
              aria-required={setting.required || undefined}
              checked={values[setting.key] === true}
              disabled={disabled}
              onCheckedChange={(value) => handleSettingChange(setting.key, value)}
            />
          ) : setting.type === "select" ? (
            <Select.Root
              value={String(values[setting.key] ?? setting.default ?? "")}
              disabled={disabled}
              onValueChange={(value) => setValues({ ...values, [setting.key]: value })}
            >
              <Select.Trigger
                className="plugin-setting-control"
                aria-label={setting.label}
              />
              <Select.Content>
                {setting.options?.map((option) => (
                  <Select.Item
                    key={option.value}
                    value={option.value}
                  >
                    {option.label}
                  </Select.Item>
                ))}
              </Select.Content>
            </Select.Root>
          ) : setting.type === "json" ? (
            <TextArea
              className="plugin-setting-control"
              aria-label={setting.label}
              aria-required={setting.required || undefined}
              aria-invalid={invalidFields.includes(setting.key) || undefined}
              disabled={disabled}
              value={
                typeof values[setting.key] === "string"
                  ? (values[setting.key] as string)
                  : (JSON.stringify(values[setting.key], null, 2) ?? "")
              }
              onChange={(event) => handleSettingChange(setting.key, event.target.value)}
              rows={8}
            />
          ) : (
            <TextField.Root
              className="plugin-setting-control"
              aria-label={setting.label}
              aria-required={setting.required || undefined}
              aria-invalid={invalidFields.includes(setting.key) || undefined}
              type={
                setting.secret
                  ? "password"
                  : ["integer", "number"].includes(setting.type)
                    ? "number"
                    : "text"
              }
              min={setting.minimum}
              max={setting.maximum}
              step={setting.type === "integer" ? 1 : "any"}
              disabled={disabled}
              value={String(values[setting.key] ?? "")}
              onChange={(event) =>
                handleSettingChange(
                  setting.key,
                  ["integer", "number"].includes(setting.type) && event.target.value !== ""
                    ? Number(event.target.value)
                    : event.target.value,
                )
              }
            />
          )}
        </div>
      ))}
      {invalidFields.length > 0 && (
        <Text
          size="2"
          color="red"
          role="alert"
        >
          {t("plugins.requiredFields")}
        </Text>
      )}
      {configError && (
        <Text
          size="2"
          color="red"
          role="alert"
        >
          {configError}
        </Text>
      )}
      <Button
        size="2"
        disabled={disabled}
        type="submit"
      >
        {t("plugins.save")}
      </Button>
    </form>
  );
}

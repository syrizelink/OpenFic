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
import {
  Badge,
  Button,
  Checkbox,
  Dialog,
  Flex,
  Heading,
  IconButton,
  Text,
  TextArea,
  TextField,
} from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GripVertical, Package, Plus, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { ConfirmDialog, toast } from "@/components";
import { apiClient } from "@/lib/api-client";

import {
  downloadPlugin,
  fetchPlugins,
  fetchPluginDevelopment,
  installPlugin,
  pluginError,
  savePluginOrder,
  PLUGINS_QUERY_KEY,
  type InstalledPlugin,
} from "./api";
import { PluginSlot } from "./plugin-slot";

import "./plugins.css";

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
  } = useQuery({ queryKey: PLUGINS_QUERY_KEY, queryFn: fetchPlugins });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const plugin = plugins.find((entry) => entry.id === selectedId) ?? plugins[0];
  const [trusted, setTrusted] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [installation, setInstallation] = useState<{ updateId?: string } | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
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
    mutationFn: savePluginOrder,
    onMutate: async (pluginIds) => {
      await queryClient.cancelQueries({ queryKey: PLUGINS_QUERY_KEY });
      const previous = queryClient.getQueryData<InstalledPlugin[]>(PLUGINS_QUERY_KEY);
      if (previous) {
        const positions = new Map(pluginIds.map((id, index) => [id, index]));
        queryClient.setQueryData(
          PLUGINS_QUERY_KEY,
          [...previous].sort(
            (left, right) =>
              (positions.get(left.id) ?? pluginIds.length) -
              (positions.get(right.id) ?? pluginIds.length),
          ),
        );
      }
      return { previous };
    },
    onError: (failure, _pluginIds, context) => {
      if (context?.previous) queryClient.setQueryData(PLUGINS_QUERY_KEY, context.previous);
      toast.error(pluginError(failure));
    },
    onSuccess: () => toast.success(t("plugins.orderSaved")),
    onSettled: () => queryClient.invalidateQueries({ queryKey: PLUGINS_QUERY_KEY }),
  });
  const busy = isRunning || orderMutation.isPending;

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
    if (busy || !over || active.id === over.id) return;
    const from = plugins.findIndex((entry) => entry.id === active.id);
    const to = plugins.findIndex((entry) => entry.id === over.id);
    if (from < 0 || to < 0) return;
    setSelectedId(plugin?.id ?? null);
    orderMutation.mutate(arrayMove(plugins, from, to).map((entry) => entry.id));
  }

  return (
    <section
      className="plugin-manager"
      aria-label={t("plugins.management")}
      data-mobile-page={mobilePage}
    >
      <div className="plugin-manager-layout">
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
                disabled={isFetching || busy}
                onClick={() => void refetch()}
              >
                <RefreshCw size={14} />
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
          <div className="plugin-list-body">
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
                <Heading
                  as="h3"
                  size="3"
                >
                  {t("plugins.information")}
                </Heading>
                <Flex
                  align="center"
                  gap="2"
                  wrap="wrap"
                >
                  <Text
                    size="3"
                    weight="medium"
                  >
                    {plugin.name}
                  </Text>
                  <Badge
                    color={
                      plugin.status === "error"
                        ? "red"
                        : plugin.status === "enabled"
                          ? "green"
                          : "gray"
                    }
                  >
                    {t(`plugins.${plugin.status}`)}
                  </Badge>
                </Flex>
                <Text
                  as="p"
                  size="2"
                  color="gray"
                >
                  {plugin.description || t("plugins.noDescription")}
                </Text>
                <dl className="plugin-information">
                  <dt>{t("plugins.identifier")}</dt>
                  <dd>{plugin.id}</dd>
                  <dt>{t("plugins.version")}</dt>
                  <dd>{plugin.version}</dd>
                  <dt>{t("plugins.author")}</dt>
                  <dd>{plugin.author || t("plugins.none")}</dd>
                  <dt>{t("plugins.capabilities")}</dt>
                  <dd>{plugin.capabilities.join(", ") || t("plugins.none")}</dd>
                  {!!plugin.tools?.length && (
                    <>
                      <dt>{t("plugins.tools")}</dt>
                      <dd>{plugin.tools.join(", ")}</dd>
                    </>
                  )}
                  {!!plugin.graphs?.length && (
                    <>
                      <dt>{t("plugins.graphs")}</dt>
                      <dd>{plugin.graphs.join(", ")}</dd>
                    </>
                  )}
                </dl>
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
              <section className="plugin-detail-section">
                <Heading
                  as="h3"
                  size="3"
                >
                  {t("plugins.configuration")}
                </Heading>
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
              </section>
              <section className="plugin-detail-section">
                <Heading
                  as="h3"
                  size="3"
                >
                  {t("plugins.actions")}
                </Heading>
                <Flex
                  wrap="wrap"
                  gap="2"
                >
                  <Button
                    size="2"
                    disabled={busy}
                    onClick={() =>
                      void run(async () => {
                        await apiClient.patch(`/plugins/${plugin.id}/enabled`, {
                          enabled: plugin.status !== "enabled",
                        });
                      })
                    }
                  >
                    {t(plugin.status === "enabled" ? "plugins.disable" : "plugins.enable")}
                  </Button>
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
                  plugin.views.filter((view) => view.slot === "sidebar.extensions").length > 0 && (
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
              </section>
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
  onSelect: () => void;
}

function PluginListItem({ plugin, selected, disabled, onSelect }: PluginListItemProps) {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, isDragging } =
    useSortable({ id: plugin.id, disabled });
  return (
    <div
      ref={setNodeRef}
      className="plugin-list-row"
      data-selected={selected}
      data-dragging={isDragging}
      style={transform ? { transform: `translate3d(0, ${transform.y}px, 0)` } : undefined}
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
      <button
        type="button"
        className="plugin-list-item"
        aria-pressed={selected}
        onClick={onSelect}
      >
        <Flex
          align="center"
          gap="2"
          className="plugin-list-title"
        >
          <Package
            size={14}
            aria-hidden="true"
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
            color="gray"
            variant="soft"
          >
            {plugin.version}
          </Badge>
        </Flex>
        <Text
          size="1"
          color="gray"
          className="plugin-list-description"
        >
          {plugin.description || t("plugins.noDescription")}
        </Text>
      </button>
    </div>
  );
}

interface PluginConfigurationProps {
  plugin: InstalledPlugin;
  disabled: boolean;
  onSave: (settings: InstalledPlugin["configuration"]) => Promise<void>;
}

function PluginConfiguration({ plugin, disabled, onSave }: PluginConfigurationProps) {
  const { t } = useTranslation();
  const [values, setValues] = useState(plugin.configuration);
  const [configError, setConfigError] = useState("");
  return (
    <form
      className="plugin-configuration"
      onSubmit={(event) => {
        event.preventDefault();
        try {
          const parsed = { ...values };
          for (const setting of plugin.settings) {
            if (setting.type === "json" && typeof parsed[setting.key] === "string")
              parsed[setting.key] = JSON.parse(parsed[setting.key] as string);
          }
          setConfigError("");
          void onSave(parsed);
        } catch (error) {
          setConfigError(String(error));
        }
      }}
    >
      {plugin.settings.map((setting) => (
        <label
          key={setting.key}
          className="plugin-setting"
        >
          <Text
            size="2"
            weight="medium"
          >
            {setting.label}
          </Text>
          {setting.description && (
            <Text
              size="1"
              color="gray"
            >
              {setting.description}
            </Text>
          )}
          {setting.type === "boolean" ? (
            <Checkbox
              checked={values[setting.key] === true}
              disabled={disabled}
              onCheckedChange={(value) => setValues({ ...values, [setting.key]: value === true })}
            />
          ) : setting.type === "json" ? (
            <TextArea
              aria-label={setting.label}
              disabled={disabled}
              value={
                typeof values[setting.key] === "string"
                  ? (values[setting.key] as string)
                  : (JSON.stringify(values[setting.key], null, 2) ?? "")
              }
              onChange={(event) => setValues({ ...values, [setting.key]: event.target.value })}
              rows={8}
            />
          ) : (
            <TextField.Root
              aria-label={setting.label}
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
              required={!setting.secret}
              disabled={disabled}
              value={String(values[setting.key] ?? "")}
              onChange={(event) =>
                setValues({
                  ...values,
                  [setting.key]: ["integer", "number"].includes(setting.type)
                    ? Number(event.target.value)
                    : event.target.value,
                })
              }
            />
          )}
        </label>
      ))}
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

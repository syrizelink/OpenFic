import { Badge, Button, Checkbox, Flex, Text, TextField } from "@radix-ui/themes";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { apiClient } from "@/lib/api-client";

import {
  downloadPlugin,
  fetchPlugins,
  installPlugin,
  pluginError,
  PLUGINS_QUERY_KEY,
  type InstalledPlugin,
} from "./api";

import "./plugins.css";

export function PluginManager({ onOpenView }: { onOpenView?: () => void } = {}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const {
    data: plugins = [],
    isLoading,
    error: loadError,
  } = useQuery({ queryKey: PLUGINS_QUERY_KEY, queryFn: fetchPlugins });
  const [trusted, setTrusted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [updateId, setUpdateId] = useState<string>();
  const uploadRef = useRef<HTMLInputElement>(null);
  const [logs, setLogs] = useState<{
    id: string;
    entries: { time: string; level: string; action: string; message: string }[];
  } | null>(null);
  const [removing, setRemoving] = useState<InstalledPlugin | null>(null);

  async function run(action: () => Promise<void>, success?: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      if (success) setNotice(success);
    } catch (failure) {
      setError(pluginError(failure));
    } finally {
      await queryClient.invalidateQueries({ queryKey: PLUGINS_QUERY_KEY });
      setBusy(false);
    }
  }

  return (
    <section
      className="plugin-manager"
      aria-label={t("plugins.management")}
    >
      <h2>{t("plugins.management")}</h2>
      <p className="plugin-muted">{t("plugins.description")}</p>
      <div className="plugin-install-panel">
        <Text
          as="label"
          size="2"
        >
          <Flex
            gap="2"
            align="start"
          >
            <Checkbox
              checked={trusted}
              onCheckedChange={(value) => setTrusted(value === true)}
              disabled={busy}
            />
            {t("plugins.trust")}
          </Flex>
        </Text>
        <Button
          disabled={!trusted || busy}
          onClick={() => {
            setUpdateId(undefined);
            uploadRef.current?.click();
          }}
        >
          {busy ? t("plugins.working") : t("plugins.install")}
        </Button>
        <input
          ref={uploadRef}
          type="file"
          accept=".zip"
          hidden
          aria-label={t("plugins.package")}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file && trusted)
              void run(() => installPlugin(file, updateId), t("plugins.installed"));
            event.target.value = "";
          }}
        />
      </div>
      {(error || loadError) && (
        <p
          role="alert"
          className="plugin-error"
        >
          {error ?? pluginError(loadError)}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {isLoading && <p>{t("plugins.loading")}</p>}
      {!isLoading && !loadError && plugins.length === 0 && <p>{t("plugins.empty")}</p>}
      {plugins.map((plugin) => (
        <article
          className="plugin-card"
          key={plugin.id}
          data-plugin-id={plugin.id}
        >
          <Flex
            wrap="wrap"
            gap="2"
            align="center"
          >
            <Text weight="bold">{plugin.name}</Text>
            <Badge>{plugin.version}</Badge>
            <Badge
              color={
                plugin.status === "error" ? "red" : plugin.status === "enabled" ? "green" : "gray"
              }
            >
              {t(`plugins.${plugin.status}`)}
            </Badge>
          </Flex>
          <p className="plugin-muted">{plugin.description}</p>
          <Text
            size="1"
            color="gray"
          >
            {plugin.id}
            {plugin.author ? ` · ${plugin.author}` : ""}
          </Text>
          <p className="plugin-muted">
            {t("plugins.capabilities")}: {plugin.capabilities.join(", ") || t("plugins.none")}
          </p>
          {plugin.error && (
            <p
              role="alert"
              className="plugin-error"
            >
              {plugin.error}
            </p>
          )}
          <Flex
            wrap="wrap"
            gap="2"
          >
            <Button
              size="1"
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
              size="1"
              variant="soft"
              disabled={busy || !trusted}
              onClick={() => {
                setUpdateId(plugin.id);
                uploadRef.current?.click();
              }}
            >
              {t("plugins.update")}
            </Button>
            <Button
              size="1"
              variant="soft"
              disabled={busy}
              onClick={() => void run(() => downloadPlugin(plugin))}
            >
              {t("plugins.export")}
            </Button>
            <Button
              size="1"
              variant="soft"
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
              size="1"
              variant="soft"
              color="red"
              disabled={busy}
              onClick={() => setRemoving(plugin)}
            >
              {t("plugins.uninstall")}
            </Button>
            {plugin.status === "enabled" &&
              plugin.views.map((view) => (
                <Button
                  asChild
                  key={view.id}
                  size="1"
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
          {plugin.settings.length > 0 && (
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
          )}
        </article>
      ))}
      {removing && (
        <div
          className="plugin-card"
          role="alert"
        >
          <p>{t("plugins.confirmUninstall", { name: removing.name })}</p>
          <Flex gap="2">
            <Button
              color="red"
              disabled={busy}
              onClick={() =>
                void run(async () => {
                  await apiClient.delete(`/plugins/${removing.id}`);
                  setRemoving(null);
                  setLogs(null);
                })
              }
            >
              {t("plugins.confirm")}
            </Button>
            <Button
              variant="soft"
              disabled={busy}
              onClick={() => setRemoving(null)}
            >
              {t("plugins.cancel")}
            </Button>
          </Flex>
        </div>
      )}
      {logs && (
        <div className="plugin-card">
          <Flex justify="between">
            <Text weight="bold">
              {t("plugins.logs")} · {logs.id}
            </Text>
            <Button
              size="1"
              variant="soft"
              onClick={() => setLogs(null)}
            >
              {t("plugins.close")}
            </Button>
          </Flex>
          <pre className="plugin-logs">
            {logs.entries
              .map((entry) => `${entry.time} [${entry.level}] ${entry.action}: ${entry.message}`)
              .join("\n") || t("plugins.emptyLogs")}
          </pre>
        </div>
      )}
    </section>
  );
}

function PluginConfiguration({
  plugin,
  disabled,
  onSave,
}: {
  plugin: InstalledPlugin;
  disabled: boolean;
  onSave: (settings: InstalledPlugin["configuration"]) => Promise<void>;
}) {
  const { t } = useTranslation();
  const [values, setValues] = useState(plugin.configuration);
  return (
    <details className="plugin-configuration">
      <summary>{t("plugins.configuration")}</summary>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void onSave(values);
        }}
      >
        {plugin.settings.map((setting) => (
          <label
            key={setting.key}
            className="plugin-setting"
          >
            <Text size="2">{setting.label}</Text>
            {setting.type === "boolean" ? (
              <Checkbox
                checked={values[setting.key] === true}
                disabled={disabled}
                onCheckedChange={(value) => setValues({ ...values, [setting.key]: value === true })}
              />
            ) : (
              <TextField.Root
                type={setting.type === "integer" ? "number" : "text"}
                min={setting.minimum}
                max={setting.maximum}
                required
                disabled={disabled}
                value={String(values[setting.key] ?? "")}
                onChange={(event) =>
                  setValues({
                    ...values,
                    [setting.key]:
                      setting.type === "integer" ? Number(event.target.value) : event.target.value,
                  })
                }
              />
            )}
          </label>
        ))}
        <Button
          size="1"
          disabled={disabled}
          type="submit"
        >
          {t("plugins.save")}
        </Button>
      </form>
    </details>
  );
}

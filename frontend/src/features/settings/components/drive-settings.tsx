/**
 * Google Drive 同步设置面板。
 */

import { Box, Button, Flex, Switch, Text, TextField } from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { Copy, ExternalLink, LogOut, RefreshCw, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Spinner, toast } from "@/components";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { useTabsStore } from "@/features/writing/store/use-tabs-store";

import {
  disconnectDrive,
  fetchDriveAuthUrl,
  fetchDriveConfig,
  fetchDriveProjectStatus,
  syncDriveProject,
  updateDriveConfig,
  updateDriveProjectStatus,
} from "../lib/drive-api";
import type { DriveConfig } from "../lib/drive.types";

function getErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "detail" in detail) return String(detail.detail);
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return fallback;
}

function formatDateTime(value: string | null, locale: string): string {
  if (!value) return "-";
  return new Date(value).toLocaleString(locale);
}

export function DriveSettings() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const currentProjectId = useTabsStore((s) => s.currentProjectId);

  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [intervalInput, setIntervalInput] = useState("");
  const [isDisconnectDialogOpen, setIsDisconnectDialogOpen] = useState(false);

  const { data: config, isLoading: isConfigLoading } = useQuery({
    queryKey: ["drive-config"],
    queryFn: fetchDriveConfig,
    refetchInterval: (query) => (query.state.data?.connected ? false : 5000),
  });

  const { data: projectStatus, isLoading: isProjectStatusLoading } = useQuery({
    queryKey: ["drive-project-status", currentProjectId],
    queryFn: () => fetchDriveProjectStatus(currentProjectId as string),
    enabled: !!currentProjectId,
    refetchInterval: config?.connected ? 15000 : false,
  });

  useEffect(() => {
    if (config?.intervalMinutes != null) {
      setIntervalInput(String(config.intervalMinutes));
    }
  }, [config?.intervalMinutes]);

  useEffect(() => {
    if (config?.connected && currentProjectId) {
      queryClient.invalidateQueries({ queryKey: ["drive-project-status", currentProjectId] });
    }
  }, [config?.connected, currentProjectId, queryClient]);

  const saveConfigMutation = useMutation({
    mutationFn: (data: { clientId: string; clientSecret: string }) =>
      updateDriveConfig({
        clientId: data.clientId,
        clientSecret: data.clientSecret,
      }),
    onSuccess: (nextConfig) => {
      queryClient.setQueryData<DriveConfig>(["drive-config"], nextConfig);
      setClientId("");
      setClientSecret("");
      toast.success(t("sync.credentialsSaved"));
    },
    onError: (error) => toast.error(getErrorMessage(error, t("sync.credentialsSaveFailed"))),
  });

  const saveIntervalMutation = useMutation({
    mutationFn: (intervalMinutes: number) => updateDriveConfig({ intervalMinutes }),
    onSuccess: (nextConfig) => {
      queryClient.setQueryData<DriveConfig>(["drive-config"], nextConfig);
      toast.success(t("sync.intervalSaved"));
    },
    onError: (error) => toast.error(getErrorMessage(error, t("sync.intervalSaveFailed"))),
  });

  const connectMutation = useMutation({
    mutationFn: fetchDriveAuthUrl,
    onSuccess: ({ authUrl }) => {
      window.open(authUrl, "_blank", "noopener,noreferrer");
    },
    onError: (error) => toast.error(getErrorMessage(error, t("sync.connectFailed"))),
  });

  const disconnectMutation = useMutation({
    mutationFn: disconnectDrive,
    onSuccess: (nextConfig) => {
      queryClient.setQueryData<DriveConfig>(["drive-config"], nextConfig);
      queryClient.invalidateQueries({ queryKey: ["drive-project-status"] });
      setIsDisconnectDialogOpen(false);
      toast.success(t("sync.disconnected"));
    },
    onError: () => toast.error(t("sync.disconnectFailed")),
  });

  const toggleEnabledMutation = useMutation({
    mutationFn: ({ projectId, enabled }: { projectId: string; enabled: boolean }) =>
      updateDriveProjectStatus(projectId, enabled),
    onSuccess: (nextStatus) => {
      if (currentProjectId) {
        queryClient.setQueryData(["drive-project-status", currentProjectId], nextStatus);
      }
    },
    onError: (error) => toast.error(getErrorMessage(error, t("sync.toggleFailed"))),
  });

  const syncNowMutation = useMutation({
    mutationFn: (projectId: string) => syncDriveProject(projectId),
    onSuccess: (result) => {
      if (currentProjectId) {
        queryClient.invalidateQueries({ queryKey: ["drive-project-status", currentProjectId] });
      }
      if (result.status === "synced") {
        toast.success(t("sync.syncSuccess"));
      } else if (result.status === "unchanged") {
        toast.info(t("sync.syncUnchanged"));
      } else {
        toast.error(result.message || t("sync.syncFailed"));
      }
    },
    onError: (error) => toast.error(getErrorMessage(error, t("sync.syncFailed"))),
  });

  const handleSaveCredentials = useCallback(() => {
    const trimmedClientId = clientId.trim();
    const trimmedClientSecret = clientSecret.trim();
    if (!trimmedClientId || !trimmedClientSecret) {
      toast.error(t("sync.credentialsRequired"));
      return;
    }
    saveConfigMutation.mutate({
      clientId: trimmedClientId,
      clientSecret: trimmedClientSecret,
    });
  }, [clientId, clientSecret, saveConfigMutation, t]);

  const handleSaveInterval = useCallback(() => {
    const parsed = Number(intervalInput);
    if (!Number.isFinite(parsed) || parsed < 1) {
      toast.error(t("sync.intervalInvalid"));
      return;
    }
    saveIntervalMutation.mutate(parsed);
  }, [intervalInput, saveIntervalMutation, t]);

  const handleConnect = useCallback(() => {
    connectMutation.mutate();
  }, [connectMutation]);

  const handleCopy = useCallback(
    async (text: string) => {
      try {
        await navigator.clipboard.writeText(text);
        toast.success(t("common.copied"));
      } catch {
        toast.error(t("common.copyFailed"));
      }
    },
    [t],
  );

  const handleToggleEnabled = useCallback(
    (enabled: boolean) => {
      if (!currentProjectId) return;
      toggleEnabledMutation.mutate({ projectId: currentProjectId, enabled });
    },
    [currentProjectId, toggleEnabledMutation],
  );

  const handleSyncNow = useCallback(() => {
    if (!currentProjectId) return;
    syncNowMutation.mutate(currentProjectId);
  }, [currentProjectId, syncNowMutation]);

  if (isConfigLoading || (currentProjectId && isProjectStatusLoading)) {
    return (
      <Flex
        align="center"
        justify="center"
        style={{ height: "100%" }}
      >
        <Spinner size={18} />
      </Flex>
    );
  }

  const isConnected = !!config?.connected;
  const canSync = isConnected && !!currentProjectId;

  return (
    <Box>
      <Flex
        direction="column"
        gap="5"
      >
        <Flex
          direction="column"
          gap="1"
        >
          <Text
            size="2"
            color="gray"
          >
            {t("sync.description")}
          </Text>
        </Flex>

        {/* 凭据 */}
        <Flex
          direction="column"
          gap="3"
        >
          <Text
            size="2"
            weight="medium"
          >
            {t("sync.credentials")}
          </Text>
          <Text
            size="1"
            color="gray"
          >
            {t("sync.credentialsDescription")}
          </Text>
          <Flex
            direction="column"
            gap="2"
          >
            <TextField.Root
              value={clientId}
              placeholder={t("sync.clientIdPlaceholder")}
              onChange={(event) => setClientId(event.target.value)}
              autoComplete="off"
            />
            <TextField.Root
              value={clientSecret}
              placeholder={t("sync.clientSecretPlaceholder")}
              onChange={(event) => setClientSecret(event.target.value)}
              autoComplete="off"
              type="password"
            />
          </Flex>
          <Flex
            align="center"
            gap="2"
          >
            <Button
              onClick={handleSaveCredentials}
              disabled={saveConfigMutation.isPending || !clientId.trim() || !clientSecret.trim()}
            >
              <Save size={16} />
              {t("sync.saveCredentials")}
            </Button>
            {config?.hasCredentials ? (
              <Text
                size="1"
                color="green"
              >
                {t("sync.credentialsConfigured")}
              </Text>
            ) : null}
          </Flex>
        </Flex>

        {/* 连接 */}
        <Flex
          direction="column"
          gap="3"
        >
          <Text
            size="2"
            weight="medium"
          >
            {t("sync.connection")}
          </Text>

          {isConnected ? (
            <Flex
              direction="column"
              gap="2"
            >
              <Flex
                direction="column"
                gap="1"
              >
                <Text
                  size="2"
                  color="green"
                >
                  {t("sync.connected")}
                </Text>
                {config.email ? (
                  <Text
                    size="1"
                    color="gray"
                  >
                    {t("sync.account")}: {config.email}
                  </Text>
                ) : null}
              </Flex>
              <Box>
                <Button
                  variant="soft"
                  color="red"
                  onClick={() => setIsDisconnectDialogOpen(true)}
                >
                  <LogOut size={16} />
                  {t("sync.disconnect")}
                </Button>
              </Box>
            </Flex>
          ) : (
            <Flex
              direction="column"
              gap="2"
            >
              <Text
                size="2"
                color="gray"
              >
                {t("sync.notConnected")}
              </Text>
              <Box>
                <Button
                  onClick={handleConnect}
                  disabled={connectMutation.isPending}
                >
                  {connectMutation.isPending ? <Spinner size={12} /> : <ExternalLink size={16} />}
                  {t("sync.connect")}
                </Button>
              </Box>
            </Flex>
          )}

          {config?.redirectUri ? (
            <Flex
              align="center"
              gap="2"
              className="list-item-hover"
              style={{ padding: "var(--space-2)" }}
            >
              <Text
                size="1"
                color="gray"
                dir="ltr"
                style={{ wordBreak: "break-all", flex: 1 }}
              >
                {t("sync.redirectUri")}: {config.redirectUri}
              </Text>
              <Button
                variant="ghost"
                color="gray"
                size="1"
                onClick={() => handleCopy(config.redirectUri)}
                aria-label={t("common.copy")}
              >
                <Copy size={14} />
              </Button>
            </Flex>
          ) : null}
        </Flex>

        {/* 同步间隔 */}
        <Flex
          direction="column"
          gap="3"
        >
          <Text
            size="2"
            weight="medium"
          >
            {t("sync.interval")}
          </Text>
          <Flex
            align="center"
            gap="2"
          >
            <Box
              style={{
                width: 120,
              }}
            >
              <TextField.Root
                type="number"
                min={1}
                max={1440}
                value={intervalInput}
                onChange={(event) => setIntervalInput(event.target.value)}
                onBlur={handleSaveInterval}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.currentTarget.blur();
                  }
                }}
              />
            </Box>
            <Text
              size="2"
              color="gray"
            >
              {t("sync.intervalMinutes")}
            </Text>
            <Button
              variant="soft"
              onClick={handleSaveInterval}
              disabled={saveIntervalMutation.isPending}
            >
              {t("common.save")}
            </Button>
          </Flex>
          <Text
            size="1"
            color="gray"
          >
            {t("sync.intervalHint")}
          </Text>
        </Flex>

        {/* 当前项目 */}
        <Flex
          direction="column"
          gap="3"
        >
          <Text
            size="2"
            weight="medium"
          >
            {t("sync.currentProject")}
          </Text>

          {!currentProjectId ? (
            <Text
              size="2"
              color="gray"
            >
              {t("sync.noProjectOpen")}
            </Text>
          ) : projectStatus ? (
            <Flex
              direction="column"
              gap="3"
            >
              <Flex
                align="center"
                justify="between"
                gap="4"
              >
                <Flex
                  direction="column"
                  gap="1"
                >
                  <Text
                    size="2"
                    weight="medium"
                  >
                    {projectStatus.projectTitle}
                  </Text>
                  <Text
                    size="1"
                    color="gray"
                  >
                    {t("sync.chapters", { count: projectStatus.chapterCount })} ·{" "}
                    {t("sync.words", { count: projectStatus.wordCount.toLocaleString() })}
                  </Text>
                </Flex>
                <Switch
                  checked={projectStatus.enabled}
                  disabled={!isConnected || toggleEnabledMutation.isPending}
                  aria-label={t("sync.autoSync")}
                  onCheckedChange={handleToggleEnabled}
                />
              </Flex>

              <Flex
                align="center"
                gap="2"
              >
                <Button
                  onClick={handleSyncNow}
                  disabled={!canSync || syncNowMutation.isPending}
                >
                  {syncNowMutation.isPending ? <Spinner size={12} /> : <RefreshCw size={16} />}
                  {t("sync.syncNow")}
                </Button>
                {!isConnected ? (
                  <Text
                    size="1"
                    color="gray"
                  >
                    {t("sync.connectFirstHint")}
                  </Text>
                ) : null}
              </Flex>

              <Flex
                direction="column"
                gap="1"
              >
                <Flex
                  align="center"
                  gap="2"
                >
                  <Text
                    size="1"
                    color="gray"
                  >
                    {t("sync.lastSynced")}:{" "}
                    {projectStatus.lastSyncedAt
                      ? formatDateTime(projectStatus.lastSyncedAt, i18n.language)
                      : t("sync.never")}
                  </Text>
                </Flex>
                {projectStatus.docUrl ? (
                  <Flex
                    align="center"
                    gap="1"
                  >
                    <Text
                      size="1"
                      color="gray"
                    >
                      {t("sync.docUrl")}:
                    </Text>
                    <a
                      href={projectStatus.docUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="settings-link"
                    >
                      <Flex
                        align="center"
                        gap="1"
                      >
                        <Text size="1">{t("sync.openDoc")}</Text>
                        <ExternalLink size={12} />
                      </Flex>
                    </a>
                  </Flex>
                ) : null}
                {projectStatus.errorMessage ? (
                  <Text
                    size="1"
                    color="red"
                  >
                    {t("sync.error")}: {projectStatus.errorMessage}
                  </Text>
                ) : null}
              </Flex>
            </Flex>
          ) : null}
        </Flex>
      </Flex>

      <ConfirmDialog
        open={isDisconnectDialogOpen}
        onOpenChange={(open) => !open && setIsDisconnectDialogOpen(false)}
        title={t("sync.disconnect")}
        description={t("sync.disconnectConfirm")}
        onConfirm={() => disconnectMutation.mutate()}
        confirmText={t("sync.disconnect")}
        cancelText={t("common.cancel")}
        loading={disconnectMutation.isPending}
      />
    </Box>
  );
}

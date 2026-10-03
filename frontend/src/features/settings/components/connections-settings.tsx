/**
 * Connections Settings Component
 *
 * 外部连接设置面板，管理模型服务提供商连接。
 */

import { Box, Flex, Text, Button, IconButton, Tooltip, TextArea, Select } from "@radix-ui/themes";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Edit, Component, RefreshCw } from "lucide-react";
import { useState, useCallback, useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { toast } from "@/components/toast";
import { getApiBaseUrl } from "@/lib/api-client";
import type { ModelProvider } from "@/lib/model.types";
import "@/lib/desktop-appearance-bridge";

import {
  fetchProviders,
  fetchModelProviderCatalogProviders,
  createProvider,
  updateProvider,
  deleteProvider,
  startOpenAICodexAuth,
  fetchOpenAICodexAuthStatus,
  completeOpenAICodexAuth,
  fetchOpenAICodexRegistrations,
} from "../lib/model-api";
import { ProviderIcon } from "../lib/provider-icons";
import {
  getProviderDisplayName,
  isCustomProviderType,
  resolveProviderDisplayName,
} from "../lib/provider-utils";
import { AgentSettingsLockNotice } from "./agent-settings-lock-notice";
import { ConnectionFormDialog } from "./connection-form-dialog";

interface ConnectionsSettingsProps {
  isAgentSettingsLocked: boolean;
  isAgentSettingsLockLoading: boolean;
}

export function ConnectionsSettings({
  isAgentSettingsLocked,
  isAgentSettingsLockLoading,
}: ConnectionsSettingsProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [formOpen, setFormOpen] = useState(false);
  const [defaultProviderType, setDefaultProviderType] = useState("");
  const [editingConnection, setEditingConnection] = useState<ModelProvider | null>(null);
  const [deletingConnection, setDeletingConnection] = useState<ModelProvider | null>(null);
  const [authorizationId, setAuthorizationId] = useState<string | null>(null);
  const [manualCallbackOpen, setManualCallbackOpen] = useState(false);
  const [callbackUrl, setCallbackUrl] = useState("");
  const [callbackError, setCallbackError] = useState("");
  const [isCallbackSubmitting, setIsCallbackSubmitting] = useState(false);
  const [selectedRegistration, setSelectedRegistration] = useState("");
  const {
    data: registrations = [],
    isLoading: isRegistrationsLoading,
    error: registrationsError,
  } = useQuery({
    queryKey: ["openai-codex-registrations"],
    queryFn: fetchOpenAICodexRegistrations,
    enabled: formOpen && !editingConnection,
  });
  const registrationSelection =
    selectedRegistration || (registrations.length === 1 ? registrations[0].client_id : "");
  const backendHostname = new URL(getApiBaseUrl(), window.location.href).hostname;
  const isLocalBackend = ["localhost", "127.0.0.1"].includes(backendHostname);

  const { data: authorizationStatus, error: authorizationError } = useQuery({
    queryKey: ["openai-codex-auth", authorizationId],
    queryFn: () => fetchOpenAICodexAuthStatus(authorizationId!),
    enabled: authorizationId !== null,
    retry: false,
    refetchInterval: (query) =>
      !query.state.error && (!query.state.data || query.state.data.status === "pending")
        ? 1000
        : false,
  });

  useEffect(() => {
    if (!isAgentSettingsLocked) return;
    setFormOpen(false);
    setEditingConnection(null);
    setDeletingConnection(null);
    setManualCallbackOpen(false);
    setCallbackUrl("");
  }, [isAgentSettingsLocked]);

  useEffect(() => {
    if (!authorizationId) return;
    if (!authorizationError && (!authorizationStatus || authorizationStatus.status === "pending"))
      return;
    setAuthorizationId(null);
    setManualCallbackOpen(false);
    setCallbackUrl("");
    setCallbackError("");
    setSelectedRegistration(authorizationStatus?.registration_id ?? "");
    queryClient.invalidateQueries({ queryKey: ["openai-codex-registrations"] });
    queryClient.invalidateQueries({ queryKey: ["model-providers"] });
    queryClient.invalidateQueries({ queryKey: ["model-provider-models"] });
    if (authorizationStatus?.status === "success") {
      setFormOpen(false);
      setEditingConnection(null);
      toast.success(t("connections.openaiCodexConnected"));
    } else {
      toast.error(t("connections.openaiCodexAuthFailed"));
    }
  }, [authorizationId, authorizationStatus, authorizationError, queryClient, t]);

  // 获取所有连接
  const {
    data: connections,
    isLoading: isConnectionsLoading,
    isFetching: isConnectionsFetching,
  } = useQuery({
    queryKey: ["model-providers"],
    queryFn: fetchProviders,
  });

  const externalConnections = useMemo(
    () => connections?.filter((c) => !c.isBuiltin) ?? [],
    [connections],
  );

  const { data: catalogProviders, isLoading: isCatalogProvidersLoading } = useQuery({
    queryKey: ["model-provider-catalog", "providers"],
    queryFn: fetchModelProviderCatalogProviders,
  });

  // 创建连接
  const createMutation = useMutation({
    mutationFn: createProvider,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["model-providers"] });
      setFormOpen(false);
      toast.success(t("connections.createSuccess"));
    },
    onError: () => {
      toast.error(t("connections.createFailed"));
    },
  });

  // 更新连接
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: FormData }) => updateProvider(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["model-providers"] });
      setFormOpen(false);
      setEditingConnection(null);
      toast.success(t("connections.updateSuccess"));
    },
    onError: () => {
      toast.error(t("connections.updateFailed"));
    },
  });

  // 删除连接
  const deleteMutation = useMutation({
    mutationFn: deleteProvider,
    onSuccess: (revocationConfirmed) => {
      queryClient.invalidateQueries({ queryKey: ["model-providers"] });
      queryClient.invalidateQueries({ queryKey: ["openai-codex-registrations"] });
      if (deletingConnection?.providerType === "openai-codex" && !revocationConfirmed) {
        toast.error(t("connections.openaiCodexRevocationUnconfirmed"));
      } else {
        toast.success(t("connections.deleteSuccess"));
      }
      setDeletingConnection(null);
    },
    onError: () => {
      toast.error(t("connections.deleteFailed"));
    },
  });

  const openAICodexAuthMutation = useMutation({
    mutationFn: startOpenAICodexAuth,
  });

  // 打开创建对话框
  const handleCreate = useCallback(() => {
    if (!authorizationId) {
      setEditingConnection(null);
      setDefaultProviderType("");
      setSelectedRegistration("");
    }
    setFormOpen(true);
  }, [authorizationId]);

  const handleOpenAICodexAuth = useCallback(
    async (providerId?: string) => {
      setDefaultProviderType("openai-codex");
      const desktopHost = window.openficDesktopHost;
      const popup = desktopHost ? null : window.open("about:blank", "_blank");
      try {
        const authorization = await openAICodexAuthMutation.mutateAsync(
          providerId
            ? { provider_id: providerId }
            : registrationSelection === "new"
              ? { new_registration: true }
              : registrationSelection
                ? { registration_id: registrationSelection }
                : {},
        );
        if (desktopHost) {
          await desktopHost.openOpenAICodexAuthorization(authorization.authorization_url);
        } else if (popup) {
          popup.opener = null;
          popup.location.href = authorization.authorization_url;
        } else {
          throw new Error("Authorization popup was blocked");
        }
        setAuthorizationId(authorization.authorization_id);
        setCallbackUrl("");
        setCallbackError("");
        if (!isLocalBackend) setManualCallbackOpen(true);
      } catch {
        popup?.close();
        toast.error(t("connections.openaiCodexAuthFailed"));
      }
    },
    [openAICodexAuthMutation, isLocalBackend, registrationSelection, t],
  );

  const handleManualCallbackOpenChange = (open: boolean) => {
    if (isCallbackSubmitting) return;
    setManualCallbackOpen(open);
    setCallbackUrl("");
    setCallbackError("");
  };

  const handleFormOpenChange = (open: boolean) => {
    if (!open) {
      setCallbackUrl("");
      setCallbackError("");
    }
    setFormOpen(open);
  };

  const handleManualCallbackSubmit = async () => {
    if (!authorizationId || !callbackUrl.trim() || isAgentSettingsLocked) return;
    setIsCallbackSubmitting(true);
    setCallbackError("");
    try {
      await completeOpenAICodexAuth(authorizationId, callbackUrl.trim());
      setCallbackUrl("");
      await queryClient.invalidateQueries({ queryKey: ["openai-codex-auth", authorizationId] });
    } catch {
      setCallbackError(t("connections.openaiCodexCallbackFailed"));
    } finally {
      setIsCallbackSubmitting(false);
    }
  };

  // 打开编辑对话框
  const handleEdit = useCallback((connection: ModelProvider) => {
    setEditingConnection(connection);
    setFormOpen(true);
  }, []);

  // 提交表单
  const handleSubmit = useCallback(
    async (data: FormData) => {
      if (editingConnection) {
        await updateMutation.mutateAsync({
          id: editingConnection.id,
          data,
        });
      } else {
        await createMutation.mutateAsync(data);
      }
    },
    [editingConnection, createMutation, updateMutation],
  );

  // 确认删除
  const handleDelete = useCallback((connection: ModelProvider) => {
    setDeletingConnection(connection);
  }, []);

  // 执行删除
  const handleConfirmDelete = useCallback(async () => {
    if (deletingConnection) {
      await deleteMutation.mutateAsync(deletingConnection.id);
    }
  }, [deletingConnection, deleteMutation]);

  const isContentLoading =
    isConnectionsLoading ||
    isConnectionsFetching ||
    isCatalogProvidersLoading ||
    isAgentSettingsLockLoading;

  if (isContentLoading) {
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

  return (
    <Box>
      <AgentSettingsLockNotice isLocked={isAgentSettingsLocked} />
      <Flex
        direction="column"
        gap="4"
      >
        {/* 描述 */}
        <Text
          size="2"
          color="gray"
        >
          {t("connections.description")}
        </Text>

        {/* 新建按钮 */}
        <Flex
          gap="2"
          wrap="wrap"
        >
          <Button
            onClick={handleCreate}
            disabled={isAgentSettingsLocked}
          >
            <Plus size={16} />
            {t("connections.newConnection")}
          </Button>
        </Flex>

        {/* 连接列表 */}
        {externalConnections.length > 0 ? (
          <Flex direction="column">
            {externalConnections.map((connection, index) => (
              <Box
                key={connection.id}
                className="list-item-hover"
              >
                <Flex
                  align="center"
                  justify="between"
                  style={{ padding: "var(--space-4)" }}
                >
                  <Flex
                    align="center"
                    gap="3"
                    style={{ flex: 1 }}
                  >
                    {/* 图标 */}
                    <Box
                      style={{
                        width: 40,
                        height: 40,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        borderRadius: "var(--radius-2)",
                        background: "var(--gray-a3)",
                      }}
                    >
                      {connection.iconPath || connection.catalogMatch?.iconPath ? (
                        <ProviderIcon
                          iconPath={connection.iconPath || connection.catalogMatch?.iconPath}
                          size={24}
                        />
                      ) : isCustomProviderType(connection.providerType) ? (
                        <Component
                          size={24}
                          aria-hidden="true"
                        />
                      ) : null}
                    </Box>

                    {/* 信息 */}
                    <Flex
                      direction="column"
                      gap="1"
                      style={{ flex: 1 }}
                    >
                      <Flex
                        align="center"
                        gap="2"
                      >
                        <Text
                          size="3"
                          weight="medium"
                        >
                          {connection.providerType === "openai-codex"
                            ? connection.name ||
                              connection.accountEmail ||
                              getProviderDisplayName(connection.providerType)
                            : connection.name ||
                              (isCustomProviderType(connection.providerType)
                                ? connection.url
                                : null) ||
                              resolveProviderDisplayName(connection)}
                        </Text>
                      </Flex>
                      <Flex
                        align="center"
                        gap="2"
                      >
                        <Text
                          size="2"
                          color="gray"
                        >
                          {connection.catalogMatch?.displayName ||
                            getProviderDisplayName(connection.providerType)}
                          {connection.providerType === "openai-codex" &&
                            connection.accountConnected === false && (
                              <Text
                                size="2"
                                color="orange"
                              >
                                {t("connections.openaiCodexDisconnectedStatus")}
                              </Text>
                            )}
                          {connection.providerType === "openai-codex" &&
                            connection.accountConnected !== false &&
                            connection.openaiCodexAccessEnabled === false && (
                              <Text
                                size="2"
                                color="orange"
                              >
                                {t("connections.openaiCodexDisabledStatus")}
                              </Text>
                            )}
                        </Text>
                        {isCustomProviderType(connection.providerType) &&
                          !connection.catalogMatch && (
                            <>
                              <Text
                                size="2"
                                color="gray"
                              >
                                •
                              </Text>
                              <Text
                                size="2"
                                color="gray"
                              >
                                {connection.url}
                              </Text>
                            </>
                          )}
                      </Flex>
                    </Flex>
                  </Flex>

                  {/* 操作按钮 */}
                  <Flex gap="2">
                    <Tooltip content={t("connections.editConnection")}>
                      <IconButton
                        variant="ghost"
                        color="gray"
                        onClick={() => handleEdit(connection)}
                        disabled={
                          isAgentSettingsLocked ||
                          (connection.providerType === "openai-codex" &&
                            (openAICodexAuthMutation.isPending || authorizationId !== null))
                        }
                        aria-label={t("connections.editConnection")}
                      >
                        <Edit size={16} />
                      </IconButton>
                    </Tooltip>
                    <Tooltip content={t("connections.deleteConnection")}>
                      <IconButton
                        variant="ghost"
                        color="red"
                        onClick={() => handleDelete(connection)}
                        disabled={isAgentSettingsLocked}
                        aria-label={t("connections.deleteConnection")}
                      >
                        <Trash2 size={16} />
                      </IconButton>
                    </Tooltip>
                  </Flex>
                </Flex>
                {index < externalConnections.length - 1 && (
                  <Box
                    style={{
                      height: "1px",
                      background: "var(--gray-a4)",
                      marginLeft: "var(--space-4)",
                      marginRight: "var(--space-4)",
                    }}
                  />
                )}
              </Box>
            ))}
          </Flex>
        ) : (
          <Flex
            direction="column"
            align="center"
            justify="center"
            gap="3"
            style={{ height: 200 }}
          >
            <Text
              size="2"
              color="gray"
            >
              {t("connections.noConnections")}
            </Text>
          </Flex>
        )}
      </Flex>

      {/* 表单对话框 */}
      <ConnectionFormDialog
        open={formOpen}
        onOpenChange={handleFormOpenChange}
        connection={editingConnection || undefined}
        catalogProviders={catalogProviders}
        isCatalogLoading={isCatalogProvidersLoading}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
        isAgentSettingsLocked={isAgentSettingsLocked}
        isOAuthAuthenticating={
          openAICodexAuthMutation.isPending || authorizationId !== null || isCallbackSubmitting
        }
        defaultProviderType={defaultProviderType}
        oauthContent={
          <Flex
            direction="column"
            gap="3"
            data-slot="provider-oauth-authentication"
          >
            {editingConnection?.accountEmail && (
              <Text size="2">{editingConnection.accountEmail}</Text>
            )}
            {!editingConnection && registrations.length > 0 && (
              <Flex
                direction="column"
                gap="2"
              >
                <Text
                  as="label"
                  htmlFor="openai-codex-registration"
                  size="2"
                  weight="medium"
                >
                  {t("connections.openaiCodexSavedRegistration")}
                </Text>
                <Select.Root
                  value={registrationSelection}
                  onValueChange={setSelectedRegistration}
                  disabled={
                    isAgentSettingsLocked ||
                    authorizationId !== null ||
                    openAICodexAuthMutation.isPending
                  }
                >
                  <Select.Trigger
                    id="openai-codex-registration"
                    placeholder={t("connections.openaiCodexChooseRegistration")}
                  />
                  <Select.Content>
                    {registrations.map((registration) => (
                      <Select.Item
                        key={registration.client_id}
                        value={registration.client_id}
                      >
                        {registration.email || t("connections.openaiCodexPendingRegistration")} (
                        {registration.client_id.slice(-8)})
                      </Select.Item>
                    ))}
                    <Select.Item value="new">
                      {t("connections.openaiCodexNewRegistration")}
                    </Select.Item>
                  </Select.Content>
                </Select.Root>
              </Flex>
            )}
            {!editingConnection && registrationsError && (
              <Text
                size="2"
                color="red"
                role="alert"
              >
                {t("connections.openaiCodexRegistrationsFailed")}
              </Text>
            )}
            <Button
              type="button"
              onClick={() => void handleOpenAICodexAuth(editingConnection?.id)}
              disabled={
                isAgentSettingsLocked ||
                openAICodexAuthMutation.isPending ||
                authorizationId !== null ||
                (!editingConnection &&
                  (isRegistrationsLoading ||
                    Boolean(registrationsError) ||
                    (registrations.length > 1 && !registrationSelection)))
              }
            >
              {openAICodexAuthMutation.isPending ? <Spinner size={18} /> : <RefreshCw size={16} />}
              {t("connections.signInWithChatGPT")}
            </Button>
            {authorizationId && (
              <Text
                size="2"
                color="gray"
                role="status"
              >
                {t("connections.openaiCodexWaiting")}
              </Text>
            )}
            {authorizationId && !manualCallbackOpen && (
              <Button
                type="button"
                variant="soft"
                onClick={() => handleManualCallbackOpenChange(true)}
                disabled={isAgentSettingsLocked}
              >
                {t("connections.openaiCodexManualCallback")}
              </Button>
            )}
            {authorizationId && manualCallbackOpen && (
              <Flex
                direction="column"
                gap="3"
              >
                <Text
                  size="2"
                  color="gray"
                >
                  {t("connections.openaiCodexCallbackDescription")}
                </Text>
                <Text
                  as="label"
                  htmlFor="openai-codex-callback-url"
                  size="2"
                  weight="medium"
                >
                  {t("connections.openaiCodexCallbackLabel")}
                </Text>
                <TextArea
                  id="openai-codex-callback-url"
                  value={callbackUrl}
                  onChange={(event) => setCallbackUrl(event.target.value)}
                  placeholder="http://127.0.0.1:…/api/v1/openai-codex/auth/callback?…"
                  rows={4}
                  autoComplete="off"
                  spellCheck={false}
                  disabled={isCallbackSubmitting || isAgentSettingsLocked}
                  aria-invalid={Boolean(callbackError)}
                  aria-describedby={callbackError ? "openai-codex-callback-error" : undefined}
                />
                <Text
                  size="1"
                  color="gray"
                >
                  {t("connections.openaiCodexCallbackSensitive")}
                </Text>
                {callbackError && (
                  <Text
                    id="openai-codex-callback-error"
                    size="2"
                    color="red"
                    role="alert"
                  >
                    {callbackError}
                  </Text>
                )}
                <Button
                  type="button"
                  onClick={() => void handleManualCallbackSubmit()}
                  disabled={!callbackUrl.trim() || isCallbackSubmitting || isAgentSettingsLocked}
                >
                  {isCallbackSubmitting && <Spinner size={18} />}
                  {t("connections.openaiCodexCallbackSubmit")}
                </Button>
              </Flex>
            )}
            {!isLocalBackend && (
              <Text
                size="1"
                color="gray"
              >
                {t("connections.openaiCodexRemoteInstructions")}
              </Text>
            )}
          </Flex>
        }
      />

      {/* 删除确认对话框 */}
      <ConfirmDialog
        open={!!deletingConnection}
        onOpenChange={(open) => !open && setDeletingConnection(null)}
        title={t("connections.deleteConnection")}
        description={t(
          deletingConnection?.providerType === "openai-codex"
            ? "connections.openaiCodexDeleteConfirm"
            : "connections.deleteConfirm",
        )}
        onConfirm={handleConfirmDelete}
        confirmText={t("common.delete")}
        cancelText={t("common.cancel")}
        loading={deleteMutation.isPending}
      />
    </Box>
  );
}

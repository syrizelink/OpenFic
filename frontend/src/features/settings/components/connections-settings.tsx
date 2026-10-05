/**
 * Connections Settings Component
 *
 * 外部连接设置面板，管理模型服务提供商连接。
 */

import { Box, Flex, Text, Button, IconButton, Tooltip, TextArea } from "@radix-ui/themes";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Trash2,
  Edit,
  Component,
  RefreshCw,
  Square,
  ChevronRight,
  ChevronDown,
  Info,
} from "lucide-react";
import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";

import { LabeledSelect, Spinner } from "@/components";
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
  deleteOpenAICodexRegistration,
  cancelOpenAICodexAuth,
  type OpenAICodexRegistration,
  type OpenAICodexAuthorizationStatus,
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

interface OpenAICodexAuthAttempt {
  id: string | null;
  popup: Window | null;
  cancelRequested: boolean;
  cancelling: boolean;
}

export function ConnectionsSettings({
  isAgentSettingsLocked,
  isAgentSettingsLockLoading,
}: ConnectionsSettingsProps) {
  const { t, i18n } = useTranslation();
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
  const [deletingRegistration, setDeletingRegistration] = useState<OpenAICodexRegistration | null>(
    null,
  );
  const [isOAuthStarting, setIsOAuthStarting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [hasCancelError, setHasCancelError] = useState(false);
  const isOAuthAuthenticating =
    isOAuthStarting || authorizationId !== null || isCancelling || hasCancelError;
  const mountedRef = useRef(true);
  const authAttemptRef = useRef<OpenAICodexAuthAttempt | null>(null);
  const finishAuthAttempt = useCallback(
    (attempt: OpenAICodexAuthAttempt, status: OpenAICodexAuthorizationStatus) => {
      if (authAttemptRef.current !== attempt) return;
      authAttemptRef.current = null;
      attempt.popup?.close();
      queryClient.invalidateQueries({ queryKey: ["model-providers"] });
      queryClient.invalidateQueries({ queryKey: ["model-provider-models"] });
      queryClient.invalidateQueries({ queryKey: ["models"] });
      queryClient.invalidateQueries({ queryKey: ["openai-codex-registrations"] });
      if (status.status === "success") toast.success(i18n.t("connections.openaiCodexConnected"));
      if (!mountedRef.current) return;
      setAuthorizationId(null);
      setIsOAuthStarting(false);
      setIsCancelling(false);
      setHasCancelError(false);
      setManualCallbackOpen(false);
      setCallbackUrl("");
      setCallbackError("");
      setIsCallbackSubmitting(false);
      if (status.status === "success") {
        setSelectedRegistration(status.registration_id ?? "");
        setFormOpen(false);
        setEditingConnection(null);
      }
    },
    [queryClient, i18n],
  );
  const cancelAuthAttempt = useCallback(
    async (attempt = authAttemptRef.current) => {
      if (!attempt || attempt.cancelling) return;
      attempt.cancelRequested = true;
      attempt.popup?.close();
      if (mountedRef.current && authAttemptRef.current === attempt) {
        setIsCancelling(true);
        setHasCancelError(false);
        setManualCallbackOpen(false);
        setCallbackUrl("");
        setCallbackError("");
        setIsCallbackSubmitting(false);
      }
      // Keep the attempt until the start response supplies an id and DELETE confirms termination.
      if (!attempt.id) return;
      attempt.cancelling = true;
      try {
        const status = await cancelOpenAICodexAuth(attempt.id);
        if (status.status === "pending") throw new Error("Authorization cancellation unconfirmed");
        finishAuthAttempt(attempt, status);
      } catch {
        if (authAttemptRef.current !== attempt) return;
        if (mountedRef.current) {
          setAuthorizationId(attempt.id);
          setIsOAuthStarting(false);
          setHasCancelError(true);
        }
        toast.error(
          i18n.t(
            mountedRef.current
              ? "connections.openaiCodexCancelFailed"
              : "connections.openaiCodexCancelUnconfirmed",
          ),
        );
      } finally {
        attempt.cancelling = false;
        if (mountedRef.current && authAttemptRef.current === attempt) setIsCancelling(false);
      }
    },
    [finishAuthAttempt, i18n],
  );
  const handleCancelAuthorization = useCallback(() => {
    void cancelAuthAttempt();
  }, [cancelAuthAttempt]);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      void cancelAuthAttempt();
    };
  }, [cancelAuthAttempt]);
  const {
    data: registrations = [],
    isLoading: isRegistrationsLoading,
    error: registrationsError,
  } = useQuery({
    queryKey: ["openai-codex-registrations"],
    queryFn: fetchOpenAICodexRegistrations,
    enabled: formOpen && !editingConnection,
  });
  const registrationSelection = selectedRegistration;
  const backendHostname = new URL(getApiBaseUrl(), window.location.href).hostname;
  const isLocalBackend = ["localhost", "127.0.0.1"].includes(backendHostname);

  const { data: authorizationStatus, error: authorizationError } = useQuery({
    queryKey: ["openai-codex-auth", authorizationId],
    queryFn: () => fetchOpenAICodexAuthStatus(authorizationId!),
    enabled: authorizationId !== null && !isCancelling && !hasCancelError,
    retry: false,
    refetchInterval: (query) =>
      authAttemptRef.current?.id === authorizationId &&
      !authAttemptRef.current?.cancelRequested &&
      !query.state.error &&
      (!query.state.data || query.state.data.status === "pending")
        ? 1000
        : false,
  });

  useEffect(() => {
    if (!isAgentSettingsLocked) return;
    setFormOpen(false);
    if (!authAttemptRef.current) setEditingConnection(null);
    setDeletingConnection(null);
    setDeletingRegistration(null);
    handleCancelAuthorization();
  }, [isAgentSettingsLocked, handleCancelAuthorization]);

  useEffect(() => {
    const attempt = authAttemptRef.current;
    if (!authorizationId || attempt?.id !== authorizationId || attempt.cancelRequested) return;
    if (!authorizationError && (!authorizationStatus || authorizationStatus.status === "pending"))
      return;
    if (authorizationError) {
      handleCancelAuthorization();
    } else {
      finishAuthAttempt(attempt, authorizationStatus!);
    }
    if (
      authorizationError ||
      (authorizationStatus?.status !== "success" && authorizationStatus?.status !== "cancelled")
    ) {
      toast.error(t("connections.openaiCodexAuthFailed"));
    }
  }, [
    authorizationId,
    authorizationStatus,
    authorizationError,
    t,
    handleCancelAuthorization,
    finishAuthAttempt,
  ]);

  // 获取所有连接
  const { data: connections, isLoading: isConnectionsLoading } = useQuery({
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
      queryClient.invalidateQueries({ queryKey: ["model-provider-models"] });
      queryClient.invalidateQueries({ queryKey: ["models"] });
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

  const deleteRegistrationMutation = useMutation({
    mutationFn: deleteOpenAICodexRegistration,
    onSuccess: (revocationConfirmed) => {
      queryClient.invalidateQueries({ queryKey: ["model-providers"] });
      queryClient.invalidateQueries({ queryKey: ["model-provider-models"] });
      queryClient.invalidateQueries({ queryKey: ["models"] });
      queryClient.invalidateQueries({ queryKey: ["openai-codex-registrations"] });
      setSelectedRegistration("");
      setDeletingRegistration(null);
      if (revocationConfirmed) {
        toast.success(t("connections.deleteSuccess"));
      } else {
        toast.error(t("connections.openaiCodexRegistrationRevocationUnconfirmed"));
      }
    },
    onError: () => toast.error(t("connections.deleteFailed")),
  });

  // 打开创建对话框
  const handleCreate = useCallback(() => {
    if (authAttemptRef.current) {
      setDefaultProviderType("openai-codex");
    } else {
      setEditingConnection(null);
      setDefaultProviderType("");
      setSelectedRegistration("");
    }
    setFormOpen(true);
  }, []);

  const handleOpenAICodexAuth = useCallback(
    async (providerId?: string) => {
      if (authAttemptRef.current || isAgentSettingsLocked) return;
      setDefaultProviderType("openai-codex");
      const desktopHost = window.openficDesktopHost;
      const popup = desktopHost ? null : window.open("about:blank", "_blank");
      const attempt: OpenAICodexAuthAttempt = {
        id: null,
        popup,
        cancelRequested: false,
        cancelling: false,
      };
      authAttemptRef.current = attempt;
      setIsOAuthStarting(true);
      setCallbackUrl("");
      setCallbackError("");
      try {
        const authorization = await startOpenAICodexAuth(
          providerId
            ? { provider_id: providerId }
            : registrationSelection === "new"
              ? { new_registration: true }
              : registrationSelection
                ? { registration_id: registrationSelection }
                : {},
        );
        attempt.id = authorization.authorization_id;
        if (authAttemptRef.current !== attempt || attempt.cancelRequested || !mountedRef.current) {
          await cancelAuthAttempt(attempt);
          return;
        }
        if (desktopHost) {
          await desktopHost.openOpenAICodexAuthorization(authorization.authorization_url);
        } else if (popup && !popup.closed) {
          popup.opener = null;
          popup.location.href = authorization.authorization_url;
        } else {
          throw new Error("Authorization popup was blocked");
        }
        if (authAttemptRef.current !== attempt || attempt.cancelRequested || !mountedRef.current)
          return;
        setAuthorizationId(authorization.authorization_id);
        setCallbackUrl("");
        setCallbackError("");
        if (!isLocalBackend) setManualCallbackOpen(true);
      } catch {
        popup?.close();
        if (authAttemptRef.current !== attempt) return;
        if (attempt.id && attempt.cancelRequested) return;
        const wasCancelled = attempt.cancelRequested;
        if (attempt.id) {
          await cancelAuthAttempt(attempt);
        } else {
          authAttemptRef.current = null;
          if (mountedRef.current) {
            setIsOAuthStarting(false);
            setIsCancelling(false);
          }
        }
        if (!wasCancelled) toast.error(t("connections.openaiCodexAuthFailed"));
      } finally {
        if (authAttemptRef.current === attempt && mountedRef.current) setIsOAuthStarting(false);
      }
    },
    [isAgentSettingsLocked, isLocalBackend, registrationSelection, t, cancelAuthAttempt],
  );

  const handleManualCallbackOpenChange = (open: boolean) => {
    if (isCallbackSubmitting) return;
    setManualCallbackOpen(open);
  };

  const handleFormOpenChange = (open: boolean) => {
    if (!open) {
      handleCancelAuthorization();
      setDeletingRegistration(null);
    }
    setFormOpen(open);
  };

  const handleManualCallbackSubmit = async () => {
    const attempt = authAttemptRef.current;
    if (
      !authorizationId ||
      attempt?.id !== authorizationId ||
      attempt.cancelRequested ||
      !callbackUrl.trim() ||
      isAgentSettingsLocked ||
      isCallbackSubmitting
    )
      return;
    setIsCallbackSubmitting(true);
    setCallbackError("");
    try {
      await completeOpenAICodexAuth(authorizationId, callbackUrl.trim());
      if (authAttemptRef.current !== attempt || attempt.cancelRequested || !mountedRef.current)
        return;
      setCallbackUrl("");
      await queryClient.invalidateQueries({ queryKey: ["openai-codex-auth", authorizationId] });
    } catch {
      if (authAttemptRef.current !== attempt || attempt.cancelRequested || !mountedRef.current)
        return;
      setCallbackError(t("connections.openaiCodexCallbackFailed"));
    } finally {
      if (authAttemptRef.current === attempt && !attempt.cancelRequested && mountedRef.current)
        setIsCallbackSubmitting(false);
    }
  };

  // 打开编辑对话框
  const handleEdit = useCallback((connection: ModelProvider) => {
    if (authAttemptRef.current) return;
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
    isConnectionsLoading || isCatalogProvidersLoading || isAgentSettingsLockLoading;

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
                        disabled={isAgentSettingsLocked || isOAuthAuthenticating}
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
        isOAuthAuthenticating={isOAuthAuthenticating || isCallbackSubmitting}
        defaultProviderType={defaultProviderType}
        oauthContent={
          <Flex
            direction="column"
            gap="3"
            data-slot="provider-oauth-authentication"
          >
            {editingConnection?.accountEmail && (
              <Text size="2">
                {t("connections.openaiCodexCurrentAccount", {
                  account: editingConnection.accountEmail,
                })}
              </Text>
            )}
            {!editingConnection && registrations.length > 0 && (
              <LabeledSelect
                label={t("connections.openaiCodexSavedRegistration")}
                placeholder={t("connections.openaiCodexChooseRegistration")}
                value={registrationSelection}
                onChange={setSelectedRegistration}
                disabled={
                  isAgentSettingsLocked ||
                  isOAuthAuthenticating ||
                  deleteRegistrationMutation.isPending
                }
                options={[
                  ...registrations.map((registration) => ({
                    value: registration.client_id,
                    label: `${registration.email || t("connections.openaiCodexPendingRegistration")} (${registration.client_id.slice(-8)})`,
                    actions: (
                      <IconButton
                        type="button"
                        variant="ghost"
                        color="red"
                        aria-label={`${t("connections.openaiCodexDeleteRegistration")} ${registration.email || registration.client_id}`}
                        disabled={
                          isAgentSettingsLocked ||
                          isOAuthAuthenticating ||
                          deleteRegistrationMutation.isPending
                        }
                        onClick={() => setDeletingRegistration(registration)}
                      >
                        <Trash2 size={16} />
                      </IconButton>
                    ),
                  })),
                  { value: "new", label: t("connections.openaiCodexNewRegistration") },
                ]}
              />
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
              color={isOAuthAuthenticating ? "red" : undefined}
              onClick={
                isOAuthAuthenticating
                  ? handleCancelAuthorization
                  : () => void handleOpenAICodexAuth(editingConnection?.id)
              }
              disabled={
                isOAuthAuthenticating
                  ? isCancelling
                  : isAgentSettingsLocked ||
                    isOAuthAuthenticating ||
                    deleteRegistrationMutation.isPending ||
                    deletingRegistration !== null ||
                    (!editingConnection &&
                      (isRegistrationsLoading ||
                        Boolean(registrationsError) ||
                        (registrations.length > 0 && !registrationSelection)))
              }
            >
              {isOAuthAuthenticating ? (
                <Square
                  size={16}
                  fill="currentColor"
                />
              ) : (
                <RefreshCw size={16} />
              )}
              {t(
                isOAuthAuthenticating
                  ? "connections.openaiCodexCancelAuthorization"
                  : editingConnection
                    ? "connections.openaiCodexReauthorize"
                    : "connections.signInWithChatGPT",
              )}
            </Button>
            {hasCancelError && (
              <Text
                size="2"
                color="red"
                role="alert"
              >
                {t("connections.openaiCodexCancelFailed")}
              </Text>
            )}
            {authorizationId && !isCancelling && !hasCancelError && (
              <Text
                size="2"
                color="gray"
                role="status"
              >
                {t("connections.openaiCodexWaiting")}
              </Text>
            )}
            {authorizationId && !isCancelling && !hasCancelError && (
              <>
                <Button
                  type="button"
                  variant="ghost"
                  className="connection-form-dialog__callback-toggle"
                  onClick={() => handleManualCallbackOpenChange(!manualCallbackOpen)}
                  disabled={isAgentSettingsLocked || isCallbackSubmitting}
                  aria-expanded={manualCallbackOpen}
                  aria-controls="openai-codex-manual-callback"
                >
                  {manualCallbackOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                  {t("connections.openaiCodexManualCallback")}
                </Button>
                <Box id="openai-codex-manual-callback">
                  {manualCallbackOpen && (
                    <Flex
                      direction="column"
                      gap="3"
                    >
                      <Flex
                        align="center"
                        gap="1"
                      >
                        <Text
                          as="label"
                          htmlFor="openai-codex-callback-url"
                          size="2"
                          weight="medium"
                        >
                          {t("connections.openaiCodexCallbackLabel")}
                        </Text>
                        <Tooltip
                          content={
                            <Flex
                              direction="column"
                              gap="2"
                            >
                              {t("connections.openaiCodexCallbackHelp")
                                .split("\n")
                                .map((paragraph) => (
                                  <Text key={paragraph}>{paragraph}</Text>
                                ))}
                            </Flex>
                          }
                        >
                          <button
                            type="button"
                            className="advanced-settings-info-button"
                            aria-label={`${t("connections.openaiCodexCallbackLabel")} ${t("topbar.help")}`}
                          >
                            <Info size={14} />
                          </button>
                        </Tooltip>
                      </Flex>
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
                        disabled={
                          !callbackUrl.trim() || isCallbackSubmitting || isAgentSettingsLocked
                        }
                      >
                        {isCallbackSubmitting && <Spinner size={18} />}
                        {t("connections.openaiCodexCallbackSubmit")}
                      </Button>
                    </Flex>
                  )}
                </Box>
              </>
            )}
            <ConfirmDialog
              open={deletingRegistration !== null}
              onOpenChange={(open) => !open && setDeletingRegistration(null)}
              title={t("connections.openaiCodexDeleteRegistration")}
              description={t("connections.openaiCodexDeleteRegistrationConfirm", {
                account: deletingRegistration?.email || deletingRegistration?.client_id,
              })}
              onConfirm={() => {
                if (!deletingRegistration || isAgentSettingsLocked) return;
                deleteRegistrationMutation.mutate(deletingRegistration.client_id);
              }}
              confirmText={t("common.delete")}
              cancelText={t("common.cancel")}
              loading={deleteRegistrationMutation.isPending}
            />
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

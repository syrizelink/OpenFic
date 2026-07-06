/**
 * Connections Settings Component
 *
 * 外部连接设置面板，管理模型服务提供商连接。
 */

import { Box, Flex, Text, Button, IconButton } from "@radix-ui/themes";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Edit, RefreshCw } from "lucide-react";
import { useState, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { toast } from "@/components/toast";
import type { ModelProvider } from "@/lib/model.types";

import {
  fetchProviders,
  fetchModelProviderCatalogProviders,
  fetchModelProviderCatalogStatus,
  createProvider,
  updateProvider,
  deleteProvider,
  refreshModelProviderCatalog,
} from "../lib/model-api";
import { ProviderIcon } from "../lib/provider-icons";
import {
  getProviderDisplayName,
  resolveProviderBuiltinIconPath,
  resolveProviderDisplayName,
} from "../lib/provider-utils";
import { ConnectionFormDialog } from "./connection-form-dialog";

export function ConnectionsSettings() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();

  const [formOpen, setFormOpen] = useState(false);
  const [editingConnection, setEditingConnection] = useState<ModelProvider | null>(null);
  const [deletingConnection, setDeletingConnection] = useState<ModelProvider | null>(null);

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

  const {
    data: catalogStatus,
    isLoading: isCatalogStatusLoading,
    isFetching: isCatalogStatusFetching,
  } = useQuery({
    queryKey: ["model-provider-catalog", "status"],
    queryFn: fetchModelProviderCatalogStatus,
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["model-providers"] });
      setDeletingConnection(null);
      toast.success(t("connections.deleteSuccess"));
    },
    onError: () => {
      toast.error(t("connections.deleteFailed"));
    },
  });

  const refreshCatalogMutation = useMutation({
    mutationFn: refreshModelProviderCatalog,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["model-provider-catalog"] });
      const refreshSucceeded =
        result.lastRefreshedAt !== catalogStatus?.lastRefreshedAt ||
        (catalogStatus?.source !== "cache" && result.source === "cache");

      if (refreshSucceeded) {
        toast.success(t("connections.catalogRefreshSuccess"));
      } else {
        toast.error(t("connections.catalogRefreshFailed"));
      }
    },
    onError: () => {
      toast.error(t("connections.catalogRefreshFailed"));
    },
  });

  // 打开创建对话框
  const handleCreate = useCallback(() => {
    setEditingConnection(null);
    setFormOpen(true);
  }, []);

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

  const formattedLastRefreshedAt = catalogStatus?.lastRefreshedAt
    ? new Intl.DateTimeFormat(i18n.language === "en" ? "en-US" : "zh-CN", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(catalogStatus.lastRefreshedAt))
    : null;
  const isContentLoading =
    isConnectionsLoading ||
    isConnectionsFetching ||
    isCatalogStatusLoading ||
    isCatalogStatusFetching;

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

        <Box
          style={{
            border: "1px solid var(--gray-a4)",
            borderRadius: "var(--radius-3)",
            padding: "var(--space-4)",
          }}
        >
          <Flex
            align="start"
            justify="between"
            gap="3"
          >
            <Flex
              direction="column"
              gap="1"
            >
              <Text
                size="2"
                weight="medium"
              >
                {t("connections.catalogTitle")}
              </Text>
              <Text
                size="1"
                color="gray"
              >
                {t("connections.catalogStatus", {
                  source: catalogStatus?.source || t("connections.catalogUnknownSource"),
                  refreshedAt: formattedLastRefreshedAt || t("connections.catalogNeverRefreshed"),
                })}
              </Text>
              {catalogStatus && (
                <Text
                  size="1"
                  color="gray"
                >
                  {t("connections.catalogCounts", {
                    providerCount: catalogStatus.providerCount,
                    modelCount: catalogStatus.modelCount,
                  })}
                </Text>
              )}
            </Flex>

            <Box display={{ initial: "none", md: "block" }}>
              <Button
                variant="soft"
                onClick={() => refreshCatalogMutation.mutate()}
                disabled={refreshCatalogMutation.isPending}
              >
                {refreshCatalogMutation.isPending ? <Spinner size={18} /> : <RefreshCw size={16} />}
                {t("connections.refreshCatalog")}
              </Button>
            </Box>

            <Box display={{ initial: "block", md: "none" }}>
              <IconButton
                variant="soft"
                color="gray"
                aria-label={t("connections.refreshCatalog")}
                onClick={() => refreshCatalogMutation.mutate()}
                disabled={refreshCatalogMutation.isPending}
              >
                {refreshCatalogMutation.isPending ? <Spinner size={18} /> : <RefreshCw size={16} />}
              </IconButton>
            </Box>
          </Flex>
        </Box>

        {/* 新建按钮 */}
        <Flex>
          <Button onClick={handleCreate}>
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
                        background: "#ffffff",
                      }}
                    >
                      <ProviderIcon
                        providerType={connection.providerType}
                        uploadedIconPath={connection.iconPath}
                        catalogIconPath={resolveProviderBuiltinIconPath(connection)}
                        size={24}
                      />
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
                          {connection.name ||
                            (connection.providerType === "openai-compatible"
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
                        </Text>
                        {/* 只在 OpenAI 兼容模式下显示 URL */}
                        {connection.providerType === "openai-compatible" && (
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
                    <IconButton
                      variant="ghost"
                      color="gray"
                      onClick={() => handleEdit(connection)}
                    >
                      <Edit size={16} />
                    </IconButton>
                    <IconButton
                      variant="ghost"
                      color="red"
                      onClick={() => handleDelete(connection)}
                    >
                      <Trash2 size={16} />
                    </IconButton>
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
        onOpenChange={setFormOpen}
        connection={editingConnection || undefined}
        catalogProviders={catalogProviders}
        isCatalogLoading={isCatalogProvidersLoading}
        onSubmit={handleSubmit}
        isSubmitting={createMutation.isPending || updateMutation.isPending}
      />

      {/* 删除确认对话框 */}
      <ConfirmDialog
        open={!!deletingConnection}
        onOpenChange={(open) => !open && setDeletingConnection(null)}
        title={t("connections.deleteConnection")}
        description={t("connections.deleteConfirm")}
        onConfirm={handleConfirmDelete}
        confirmText={t("common.delete")}
        cancelText={t("common.cancel")}
        loading={deleteMutation.isPending}
      />
    </Box>
  );
}

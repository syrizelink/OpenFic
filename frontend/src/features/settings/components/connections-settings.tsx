/**
 * Connections Settings Component
 *
 * 外部连接设置面板，管理模型服务提供商连接。
 */

import { Box, Flex, Text, Button, IconButton } from "@radix-ui/themes";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Edit } from "lucide-react";
import { useState, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { toast } from "@/components/toast";
import type { ModelProvider } from "@/lib/model.types";

import {
  fetchProviders,
  fetchModelProviderCatalogProviders,
  createProvider,
  updateProvider,
  deleteProvider,
} from "../lib/model-api";
import { ProviderIcon } from "../lib/provider-icons";
import { getProviderDisplayName, resolveProviderDisplayName } from "../lib/provider-utils";
import { ConnectionFormDialog } from "./connection-form-dialog";

export function ConnectionsSettings() {
  const { t } = useTranslation();
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

  const isContentLoading =
    isConnectionsLoading || isConnectionsFetching || isCatalogProvidersLoading;

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
                        background: "var(--gray-a3)",
                      }}
                    >
                      <ProviderIcon
                        iconPath={connection.iconPath}
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
                        {/* 仅未匹配目录的 OpenAI Compatible 连接显示自定义 URL。 */}
                        {connection.providerType === "openai-compatible" &&
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

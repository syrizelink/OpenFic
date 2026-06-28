/**
 * All Tasks Page
 *
 * 查看全部任务页面组件。
 */

import { useEffect, useState } from "react";
import {
  Box,
  Flex,
  Text,
  IconButton,
  Tooltip,
  TextField,
  Spinner,
} from "@radix-ui/themes";
import { ArrowLeft, Copy, Star, Trash2, Search, ListX } from "lucide-react";
import { useTranslation } from "react-i18next";
import { formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale";

import type { TaskListItem } from "@/lib/task.types";
import { useTasks, useUpdateTask, useDeleteTask, useDeleteAllTasks } from "../../hooks/use-tasks";
import { toast, ConfirmDialog } from "@/components";

interface AllTasksPageProps {
  projectId: string;
  onBack: () => void;
  onTaskClick: (task: TaskListItem) => void;
}

export function AllTasksPage({
  projectId,
  onBack,
  onTaskClick,
}: AllTasksPageProps) {
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingTask, setDeletingTask] = useState<TaskListItem | null>(null);
  const [deleteAllDialogOpen, setDeleteAllDialogOpen] = useState(false);

  // 获取任务列表
  const { data, isLoading, refetch } = useTasks(projectId, {
    search: searchQuery || undefined,
  });
  const { data: allTasksData } = useTasks(projectId);

  useEffect(() => {
    void refetch();
  }, [refetch]);

  const updateMutation = useUpdateTask();
  const deleteMutation = useDeleteTask(projectId);
  const deleteAllMutation = useDeleteAllTasks(projectId);

  // 格式化时间
  const formatTime = (dateString: string) => {
    try {
      return formatDistanceToNow(new Date(dateString), {
        addSuffix: true,
        locale: zhCN,
      });
    } catch {
      return dateString;
    }
  };

  // 复制任务内容
  const handleCopy = (task: TaskListItem, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(task.title);
    toast.success(t("common.copied"));
  };

  // 切换收藏
  const handleToggleFavorite = (task: TaskListItem, e: React.MouseEvent) => {
    e.stopPropagation();
    updateMutation.mutate({
      taskId: task.id,
      data: { is_favorited: !task.isFavorited },
    });
  };

  // 打开删除对话框
  const handleOpenDelete = (task: TaskListItem, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeletingTask(task);
    setDeleteDialogOpen(true);
  };

  // 确认删除
  const handleConfirmDelete = async () => {
    if (!deletingTask) return;
    await deleteMutation.mutateAsync(deletingTask.id);
    setDeleteDialogOpen(false);
    setDeletingTask(null);
  };

  // 确认删除全部
  const handleConfirmDeleteAll = async () => {
    await deleteAllMutation.mutateAsync();
    setDeleteAllDialogOpen(false);
  };

  const tasks = data?.items ?? [];
  const allTasks = allTasksData?.items ?? [];
  const hasAnyTasks = allTasks.length > 0;
  const runningTaskCount = allTasks.filter((task) => task.isRunning).length;
  const deleteAllDescription = runningTaskCount > 0
    ? t("writing.aiSidebar.deleteAllTasksConfirmWithRunning", { count: runningTaskCount })
    : t("writing.aiSidebar.deleteAllTasksConfirm");
  const runningLabel = t("writing.aiSidebar.taskRunning");

  return (
    <Box
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "var(--color-panel)",
      }}
    >
      {/* 顶部栏 */}
      <Flex
        px="3"
        py="3"
        align="center"
        gap="2"
        style={{ borderBottom: "1px solid var(--gray-a4)" }}
      >
        <IconButton variant="ghost" size="2" onClick={onBack}>
          <ArrowLeft size={18} />
        </IconButton>
        <Text size="3" weight="medium">
          {t("writing.aiSidebar.allTasks")}
        </Text>
      </Flex>

      {/* 搜索栏 */}
      <Flex px="3" py="2" gap="2" align="center">
        <TextField.Root
          placeholder={t("writing.aiSidebar.searchTasks")}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          size="2"
          style={{ flex: 1 }}
        >
          <TextField.Slot>
            <Search size={16} />
          </TextField.Slot>
        </TextField.Root>
        {hasAnyTasks && (
          <Tooltip content={t("writing.aiSidebar.deleteAllTasks")}>
            <IconButton
              variant="ghost"
              size="2"
              onClick={() => setDeleteAllDialogOpen(true)}
              style={{ color: "var(--red-9)" }}
            >
              <ListX size={18} />
            </IconButton>
          </Tooltip>
        )}
      </Flex>

      {/* 任务列表 */}
      <Box
        style={{
          flex: 1,
          overflow: "auto",
          padding: "8px 12px",
        }}
      >
        {isLoading ? (
          <Flex align="center" justify="center" style={{ padding: "32px" }}>
            <Spinner size="3" />
          </Flex>
        ) : tasks.length === 0 ? (
          <Flex
            align="center"
            justify="center"
            style={{ padding: "32px", color: "var(--gray-9)" }}
          >
            <Text size="2">
              {searchQuery
                ? t("writing.aiSidebar.noSearchResults")
                : t("writing.aiSidebar.noTasks")}
            </Text>
          </Flex>
        ) : (
          tasks.map((task) => (
            <Box
              key={task.id}
              className="task-list-item"
              onClick={() => onTaskClick(task)}
            >
              <Flex align="center" gap="2" style={{ marginBottom: "8px" }}>
                <Text
                  size="2"
                  weight="medium"
                  style={{
                    flex: 1,
                    minWidth: 0,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {task.title}
                </Text>
                {task.isRunning && (
                  <span
                    aria-label={runningLabel}
                    className="task-running-dot"
                    title={runningLabel}
                  />
                )}
              </Flex>

              {/* 底部栏 */}
              <Flex justify="between" align="center">
                {/* 左侧：时间 */}
                <Text size="1" style={{ color: "var(--gray-10)" }}>
                  {formatTime(task.updatedAt)}
                </Text>

                {/* 右侧：操作按钮 */}
                <Flex align="center" gap="1">
                  <Tooltip content={t("common.copy")}>
                    <IconButton
                      variant="ghost"
                      size="1"
                      onClick={(e) => handleCopy(task, e)}
                      style={{ width: "24px", height: "24px" }}
                    >
                      <Copy size={14} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip
                    content={
                      task.isFavorited
                        ? t("writing.aiSidebar.unfavorite")
                        : t("writing.aiSidebar.favorite")
                    }
                  >
                    <IconButton
                      variant="ghost"
                      size="1"
                      onClick={(e) => handleToggleFavorite(task, e)}
                      style={{
                        width: "24px",
                        height: "24px",
                        color: task.isFavorited
                          ? "var(--amber-9)"
                          : "var(--gray-9)",
                      }}
                    >
                      <Star
                        size={14}
                        fill={task.isFavorited ? "currentColor" : "none"}
                      />
                    </IconButton>
                  </Tooltip>
                  {!task.isRunning && (
                    <Tooltip content={t("common.delete")}>
                      <IconButton
                        variant="ghost"
                        size="1"
                        onClick={(e) => handleOpenDelete(task, e)}
                        style={{
                          width: "24px",
                          height: "24px",
                          color: "var(--red-9)",
                        }}
                      >
                        <Trash2 size={14} />
                      </IconButton>
                    </Tooltip>
                  )}
                </Flex>
              </Flex>
            </Box>
          ))
        )}
      </Box>

      {/* 删除确认对话框 */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={handleConfirmDelete}
        title={t("writing.aiSidebar.deleteTask")}
        description={t("writing.aiSidebar.deleteTaskConfirm", {
          title: deletingTask?.title ?? "",
        })}
        confirmText={t("common.delete")}
        confirmColor="red"
        loading={deleteMutation.isPending}
      />

      {/* 删除全部确认对话框 */}
      <ConfirmDialog
        open={deleteAllDialogOpen}
        onOpenChange={setDeleteAllDialogOpen}
        onConfirm={handleConfirmDeleteAll}
        title={t("writing.aiSidebar.deleteAllTasks")}
        description={deleteAllDescription}
        confirmText={t("common.delete")}
        confirmColor="red"
        loading={deleteAllMutation.isPending}
      />
    </Box>
  );
}


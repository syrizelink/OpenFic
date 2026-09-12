/**
 * All Tasks Page
 *
 * Komponen halaman untuk melihat seluruh tugas.
 */

import { Box, Flex, Text, IconButton, Tooltip, TextField } from "@radix-ui/themes";
import { formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale";
import { ArrowLeft, Pencil, Star, Trash2, Search, ListX } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { ConfirmDialog, Spinner } from "@/components";
import type { TaskListItem } from "@/lib/task.types";

import { useTasks, useUpdateTask, useDeleteTask, useDeleteAllTasks } from "../../hooks/use-tasks";
import { TaskRenameInput } from "./task-rename-input";

interface AllTasksPageProps {
  projectId: string;
  onBack: () => void;
  onTaskClick: (task: TaskListItem) => void;
}

export function AllTasksPage({ projectId, onBack, onTaskClick }: AllTasksPageProps) {
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = useState("");
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingTask, setDeletingTask] = useState<TaskListItem | null>(null);
  const [deleteAllDialogOpen, setDeleteAllDialogOpen] = useState(false);
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [savingTaskId, setSavingTaskId] = useState<string | null>(null);

  // Mengambil daftar tugas
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

  // Memformat waktu
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

  const handleStartEdit = (task: TaskListItem, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingTaskId(task.id);
  };

  const handleCancelEdit = () => {
    setEditingTaskId(null);
  };

  const handleCommitEdit = async (taskId: string, originalTitle: string, nextTitle: string) => {
    const trimmedTitle = nextTitle.trim();
    if (!trimmedTitle || trimmedTitle === originalTitle) {
      handleCancelEdit();
      return;
    }

    setSavingTaskId(taskId);
    try {
      await updateMutation.mutateAsync({
        taskId,
        data: { title: trimmedTitle },
      });
      handleCancelEdit();
    } finally {
      setSavingTaskId(null);
    }
  };

  const handleToggleFavorite = (task: TaskListItem, e: React.MouseEvent) => {
    e.stopPropagation();
    updateMutation.mutate({
      taskId: task.id,
      data: { is_favorited: !task.isFavorited },
    });
  };

  const handleOpenDelete = (task: TaskListItem, e: React.MouseEvent) => {
    e.stopPropagation();
    setDeletingTask(task);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!deletingTask) return;
    await deleteMutation.mutateAsync(deletingTask.id);
    setDeleteDialogOpen(false);
    setDeletingTask(null);
  };

  const handleConfirmDeleteAll = async () => {
    await deleteAllMutation.mutateAsync();
    setDeleteAllDialogOpen(false);
  };

  const tasks = data?.items ?? [];
  const allTasks = allTasksData?.items ?? [];
  const hasAnyTasks = allTasks.length > 0;
  const runningTaskCount = allTasks.filter((task) => task.isRunning).length;
  const deleteAllDescription =
    runningTaskCount > 0
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
      {/* Bilah atas */}
      <Flex
        px="3"
        py="3"
        align="center"
        gap="2"
        style={{ borderBottom: "1px solid var(--gray-a4)" }}
      >
        <IconButton
          variant="ghost"
          size="2"
          onClick={onBack}
        >
          <ArrowLeft size={18} />
        </IconButton>
        <Text
          size="3"
          weight="medium"
        >
          {t("writing.aiSidebar.allTasks")}
        </Text>
      </Flex>

      {/* Bilah pencarian */}
      <Flex
        px="3"
        py="2"
        gap="2"
        align="center"
      >
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

      {/* Daftar tugas */}
      <Box
        style={{
          flex: 1,
          overflow: "auto",
          padding: "8px 12px",
        }}
      >
        {isLoading ? (
          <Flex
            align="center"
            justify="center"
            style={{ padding: "32px" }}
          >
            <Spinner size={18} />
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
              onClick={() => {
                if (editingTaskId !== task.id) onTaskClick(task);
              }}
            >
              <Flex
                align="center"
                gap="2"
                style={{ marginBottom: "8px" }}
              >
                {editingTaskId === task.id ? (
                  <Box style={{ flex: 1, minWidth: 0, height: "20px" }}>
                    <TaskRenameInput
                      key={task.id}
                      initialValue={task.title}
                      disabled={savingTaskId === task.id}
                      onConfirm={(newTitle) => handleCommitEdit(task.id, task.title, newTitle)}
                      onCancel={handleCancelEdit}
                    />
                  </Box>
                ) : (
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
                )}
                {task.isRunning && (
                  <span
                    aria-label={runningLabel}
                    className="task-running-dot"
                    title={runningLabel}
                  />
                )}
              </Flex>

              {/* Bilah bawah */}
              <Flex
                justify="between"
                align="center"
              >
                {/* Kiri: waktu */}
                <Text
                  size="1"
                  style={{ color: "var(--gray-10)" }}
                >
                  {formatTime(task.updatedAt)}
                </Text>

                {/* Kanan: tombol tindakan */}
                <Flex
                  align="center"
                  gap="1"
                >
                  <Tooltip content={t("common.edit")}>
                    <IconButton
                      variant="ghost"
                      size="1"
                      onClick={(e) => handleStartEdit(task, e)}
                      disabled={savingTaskId === task.id}
                      style={{ width: "24px", height: "24px" }}
                    >
                      <Pencil size={14} />
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
                        color: task.isFavorited ? "var(--amber-9)" : "var(--gray-9)",
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

      {/* Dialog konfirmasi penghapusan */}
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

      {/* Dialog konfirmasi penghapusan seluruhnya */}
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

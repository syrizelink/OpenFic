/**
 * Task List
 *
 * 任务列表组件，显示最近的任务。
 */

import { Box, Flex, Text, IconButton, Tooltip } from "@radix-ui/themes";
import { Copy, Star, Clock } from "lucide-react";
import { useTranslation } from "react-i18next";
import { formatDistanceToNow } from "date-fns";
import { zhCN } from "date-fns/locale";

import type { TaskListItem } from "@/lib/task.types";
import { toast } from "@/components";

interface TaskListProps {
  tasks: TaskListItem[];
  onTaskClick: (task: TaskListItem) => void;
  onToggleFavorite: (taskId: string, isFavorited: boolean) => void;
}

export function TaskList({
  tasks,
  onTaskClick,
  onToggleFavorite,
}: TaskListProps) {
  const { t } = useTranslation();
  const runningLabel = t("writing.aiSidebar.taskRunning");

  // 复制任务内容
  const handleCopy = (task: TaskListItem, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(task.title);
    toast.success(t("common.copied"));
  };

  // 切换收藏
  const handleToggleFavorite = (task: TaskListItem, e: React.MouseEvent) => {
    e.stopPropagation();
    onToggleFavorite(task.id, !task.isFavorited);
  };

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

  if (tasks.length === 0) {
    return (
      <Flex
        align="center"
        justify="center"
        style={{ padding: "32px 16px", color: "var(--gray-9)" }}
      >
        <Text size="2">{t("writing.aiSidebar.noTasks")}</Text>
      </Flex>
    );
  }

  return (
    <Box>
      {tasks.map((task) => (
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
            <Flex align="center" gap="1" style={{ color: "var(--gray-10)" }}>
              <Clock size={12} />
              <Text size="1">{formatTime(task.updatedAt)}</Text>
            </Flex>

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
                  <Star size={14} fill={task.isFavorited ? "currentColor" : "none"} />
                </IconButton>
              </Tooltip>
            </Flex>
          </Flex>
        </Box>
      ))}
    </Box>
  );
}


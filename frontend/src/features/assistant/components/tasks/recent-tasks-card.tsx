/**
 * Recent Tasks Card
 *
 * 悬浮的最近任务卡片组件
 */

import { Box, Flex, Text } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";

import type { TaskListItem } from "@/lib/task.types";

import { TaskList } from "./task-list";

interface RecentTasksCardProps {
  tasks: TaskListItem[];
  hasRecentTasks: boolean;
  onTaskClick: (task: TaskListItem) => void;
  onToggleFavorite: (taskId: string, isFavorited: boolean) => void;
  onRenameTask: (taskId: string, title: string) => Promise<void>;
  onViewAll: () => void;
}

export function RecentTasksCard({
  tasks,
  hasRecentTasks,
  onTaskClick,
  onToggleFavorite,
  onRenameTask,
  onViewAll,
}: RecentTasksCardProps) {
  const { t } = useTranslation();

  return (
    <Flex
      align="center"
      justify="center"
      style={{ height: "100%", position: "relative" }}
    >
      {/* 悬浮的最近任务卡片 */}
      <Box
        style={{
          width: "90%",
          maxWidth: "320px",
        }}
      >
        {hasRecentTasks ? (
          <>
            {/* 标题栏 */}
            <Flex
              justify="between"
              align="center"
              mb="3"
            >
              <Text
                size="2"
                weight="medium"
              >
                {t("writing.aiSidebar.recentTasks")}
              </Text>
              <Text
                size="1"
                style={{ color: "var(--accent-11)", cursor: "pointer" }}
                onClick={onViewAll}
              >
                {t("writing.aiSidebar.viewAll")}
              </Text>
            </Flex>

            {/* 任务列表 */}
            <TaskList
              tasks={tasks}
              onTaskClick={onTaskClick}
              onToggleFavorite={onToggleFavorite}
              onRenameTask={onRenameTask}
            />
          </>
        ) : (
          // 无任务提示
          <Flex
            align="center"
            justify="center"
            direction="column"
            gap="2"
            style={{ padding: "20px 0", color: "var(--gray-9)" }}
          >
            <Text size="2">{t("writing.aiSidebar.noTasks")}</Text>
          </Flex>
        )}
      </Box>
    </Flex>
  );
}

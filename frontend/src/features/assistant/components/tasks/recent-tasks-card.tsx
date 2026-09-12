/**
 * Recent Tasks Card
 *
 * Komponen kartu tugas terbaru yang mengapung
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
      {/* Kartu tugas terbaru yang mengapung */}
      <Box
        style={{
          width: "90%",
          maxWidth: "320px",
        }}
      >
        {hasRecentTasks ? (
          <>
            {/* Bilah judul */}
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

            {/* Daftar tugas */}
            <TaskList
              tasks={tasks}
              onTaskClick={onTaskClick}
              onToggleFavorite={onToggleFavorite}
              onRenameTask={onRenameTask}
            />
          </>
        ) : (
          // Petunjuk saat tidak ada tugas
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

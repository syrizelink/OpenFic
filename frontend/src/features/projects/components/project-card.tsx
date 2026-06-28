/**
 * ProjectCard Component
 *
 * Grid 视图下的项目卡片组件。
 */

import { Box, Card, Flex, Text, IconButton, Tooltip } from "@radix-ui/themes";
import { Edit2, Trash2, BookOpen } from "lucide-react";
import { motion } from "motion/react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { formatRelativeTime } from "@/lib/time-utils";
import type { Project } from "@/lib/project.types";

const MotionCard = motion.create(Card);

interface ProjectCardProps {
  project: Project;
  onEdit: (project: Project) => void;
  onDelete: (project: Project) => void;
}

export function ProjectCard({ project, onEdit, onDelete }: ProjectCardProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const handleClick = () => {
    navigate(`/projects/${project.id}`);
  };

  return (
    <MotionCard
      size="2"
      variant="ghost"
      style={{
        cursor: "pointer",
        overflow: "hidden",
        padding: "var(--space-3)",
        borderRadius: "var(--radius-3)",
      }}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4, backgroundColor: "var(--gray-a3)" }}
      transition={{ duration: 0.2 }}
      onClick={handleClick}
    >
      {/* 封面图 */}
      <Box
        style={{
          width: "100%",
          aspectRatio: "2 / 3",
          overflow: "hidden",
          background: project.coverUrl ? "transparent" : "var(--gray-a3)",
          borderRadius: "var(--radius-2)",
          marginBottom: "12px",
          boxShadow:
            "0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.06)",
        }}
      >
        {project.coverUrl ? (
          <img
            src={project.coverUrl}
            alt={project.title}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        ) : (
          <Flex align="center" justify="center" style={{ height: "100%" }}>
            <BookOpen size={48} style={{ color: "var(--gray-a9)" }} />
          </Flex>
        )}
      </Box>

      {/* 项目信息 */}
      <Box>
        <Flex justify="between" align="start" mb="1">
          <Text size="3" weight="bold" style={{ flex: 1 }} truncate>
            {project.title}
          </Text>
          <Flex gap="3" ml="2">
            <Tooltip content={t("common.edit")}>
              <IconButton
                size="1"
                variant="ghost"
                onClick={(e) => {
                  e.stopPropagation();
                  onEdit(project);
                }}
              >
                <Edit2 size={14} />
              </IconButton>
            </Tooltip>
            <Tooltip content={t("common.delete")}>
              <IconButton
                size="1"
                variant="ghost"
                color="red"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(project);
                }}
              >
                <Trash2 size={14} />
              </IconButton>
            </Tooltip>
          </Flex>
        </Flex>

        <Flex gap="2" align="center">
          <Text size="1" color="gray">
            {project.wordCount.toLocaleString()} {t("projects.words")}
          </Text>
          <Text size="1" color="gray">
            ·
          </Text>
          <Text size="1" color="gray">
            {project.chapterCount} {t("projects.chapters")}
          </Text>
        </Flex>

        <Text size="1" color="gray" mt="1">
          {formatRelativeTime(project.updatedAt)}
        </Text>
      </Box>
    </MotionCard>
  );
}

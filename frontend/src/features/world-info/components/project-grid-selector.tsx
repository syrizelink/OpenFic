/**
 * Project Grid Selector Component
 *
 * 项目网格选择器，以图书封面+标题的形式展示和选择项目。
 */

import { Box, Flex, Text, ScrollArea } from "@radix-ui/themes";
import { BookOpen, X } from "lucide-react";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";

import type { Project } from "@/lib/project.types";

const MotionBox = motion.create(Box);

interface ProjectGridSelectorProps {
  /** 可选的项目列表 */
  projects: Project[];
  /** 当前选中的项目 ID（空字符串表示无绑定） */
  value: string;
  /** 选择项目时的回调（空字符串表示无绑定） */
  onChange: (projectId: string) => void;
  /** 是否禁用 */
  disabled?: boolean;
  /** 是否显示"无绑定"选项 */
  showNoneOption?: boolean;
}

export function ProjectGridSelector({
  projects,
  value,
  onChange,
  disabled = false,
  showNoneOption = true,
}: ProjectGridSelectorProps) {
  const { t } = useTranslation();

  const handleSelect = (projectId: string) => {
    if (disabled) return;
    onChange(projectId);
  };

  // 计算两行的高度：每个项目约 100px 宽，高度约 150px（2/3比例），加上标题和间距约 178px，两行约 356px + gap
  const maxHeight = 380; // 两行的高度限制

  return (
    <ScrollArea style={{ maxHeight: `${maxHeight}px` }}>
      <Box>
        <Flex
          wrap="wrap"
          gap="3"
        >
          {/* 无绑定选项 */}
          {showNoneOption && (
            <MotionBox
              style={{
                width: "100px",
                flexShrink: 0,
                cursor: disabled ? "not-allowed" : "pointer",
                opacity: disabled ? 0.5 : 1,
              }}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              whileHover={disabled ? {} : { scale: 1.05 }}
              transition={{ duration: 0.2 }}
              onClick={() => handleSelect("")}
            >
              <Box
                style={{
                  width: "100%",
                  aspectRatio: "2 / 3",
                  overflow: "hidden",
                  background: "var(--gray-a3)",
                  borderRadius: "var(--radius-2)",
                  marginBottom: "8px",
                  border: value === "" ? "2px solid var(--accent-9)" : "2px solid transparent",
                  boxShadow:
                    value === ""
                      ? "0 0 0 2px var(--accent-a3)"
                      : "0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.06)",
                  transition: "all 0.2s",
                }}
              >
                <Flex
                  align="center"
                  justify="center"
                  style={{ height: "100%", flexDirection: "column", gap: "8px" }}
                >
                  <X
                    size={24}
                    style={{ color: "var(--gray-a9)" }}
                  />
                </Flex>
              </Box>
              <Text
                size="1"
                weight="medium"
                align="center"
                style={{ display: "block" }}
                truncate
              >
                {t("worldInfo.noBinding")}
              </Text>
            </MotionBox>
          )}

          {/* 项目选项 */}
          {projects.map((project) => {
            const isSelected = value === project.id;
            return (
              <MotionBox
                key={project.id}
                style={{
                  width: "100px",
                  flexShrink: 0,
                  cursor: disabled ? "not-allowed" : "pointer",
                  opacity: disabled ? 0.5 : 1,
                }}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                whileHover={disabled ? {} : { scale: 1.05 }}
                transition={{ duration: 0.2 }}
                onClick={() => handleSelect(project.id)}
              >
                <Box
                  style={{
                    width: "100%",
                    aspectRatio: "2 / 3",
                    overflow: "hidden",
                    background: project.coverUrl ? "transparent" : "var(--gray-a3)",
                    borderRadius: "var(--radius-2)",
                    marginBottom: "8px",
                    border: isSelected ? "2px solid var(--accent-9)" : "2px solid transparent",
                    boxShadow: isSelected
                      ? "0 0 0 2px var(--accent-a3)"
                      : "0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.06)",
                    transition: "all 0.2s",
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
                    <Flex
                      align="center"
                      justify="center"
                      style={{ height: "100%" }}
                    >
                      <BookOpen
                        size={24}
                        style={{ color: "var(--gray-a9)" }}
                      />
                    </Flex>
                  )}
                </Box>
                <Text
                  size="1"
                  weight="medium"
                  align="center"
                  style={{ display: "block" }}
                  truncate
                >
                  {project.title}
                </Text>
              </MotionBox>
            );
          })}
        </Flex>
      </Box>
    </ScrollArea>
  );
}

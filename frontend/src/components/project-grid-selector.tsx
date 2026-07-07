/**
 * Project Grid Selector Component
 *
 * 项目网格选择器，以图书封面+标题的形式展示和选择项目。
 */

import { Box, Flex, Text, ScrollArea } from "@radix-ui/themes";
import { BookOpen, X } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { Project } from "@/lib/project.types";

import "./project-grid-selector.css";

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

interface ProjectCardProps {
  selected: boolean;
  disabled: boolean;
  label: string;
  onSelect: () => void;
  children: ReactNode;
}

function ProjectCard({ selected, disabled, label, onSelect, children }: ProjectCardProps) {
  return (
    <Box
      className="project-grid-selector__card"
      data-disabled={disabled ? "true" : "false"}
      onClick={onSelect}
    >
      <Box
        className="project-grid-selector__cover"
        data-state={selected ? "selected" : "unselected"}
      >
        {children}
      </Box>
      <Text
        as="p"
        size="1"
        weight="medium"
        className="project-grid-selector__title"
      >
        {label}
      </Text>
    </Box>
  );
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

  return (
    <ScrollArea style={{ maxHeight: 380 }}>
      <Flex
        wrap="wrap"
        gap="3"
        py="2"
      >
        {showNoneOption && (
          <ProjectCard
            selected={value === ""}
            disabled={disabled}
            label={t("projectSelect.noBinding")}
            onSelect={() => handleSelect("")}
          >
            <Flex
              align="center"
              justify="center"
              className="project-grid-selector__cover-placeholder"
            >
              <X size={24} />
            </Flex>
          </ProjectCard>
        )}

        {projects.map((project) => {
          const isSelected = value === project.id;
          return (
            <ProjectCard
              key={project.id}
              selected={isSelected}
              disabled={disabled}
              label={project.title}
              onSelect={() => handleSelect(project.id)}
            >
              {project.coverUrl ? (
                <img
                  src={project.coverUrl}
                  alt={project.title}
                  className="project-grid-selector__cover-img"
                />
              ) : (
                <Flex
                  align="center"
                  justify="center"
                  className="project-grid-selector__cover-placeholder"
                >
                  <BookOpen size={24} />
                </Flex>
              )}
            </ProjectCard>
          );
        })}
      </Flex>
    </ScrollArea>
  );
}

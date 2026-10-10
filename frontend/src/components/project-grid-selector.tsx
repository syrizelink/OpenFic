/**
 * Project Grid Selector Component
 *
 * 项目网格选择器，以图书封面+标题的形式展示和选择项目。
 */

import { Box, Flex, ScrollArea, Text } from "@radix-ui/themes";
import { BookOpen, Check, X } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { useAppShell } from "@/features/app-shell/components/app-shell-context";
import type { Project } from "@/lib/project.types";
import { formatRelativeTime } from "@/lib/time-utils";

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

interface ProjectListCardProps extends ProjectCardProps {
  project: Project | null;
}

function ProjectListCard({
  project,
  selected,
  disabled,
  label,
  onSelect,
  children,
}: ProjectListCardProps) {
  const { t } = useTranslation();

  return (
    <button
      type="button"
      className="project-grid-selector__list-card"
      data-disabled={disabled ? "true" : "false"}
      data-state={selected ? "selected" : "unselected"}
      disabled={disabled}
      onClick={onSelect}
    >
      <Box className="project-grid-selector__list-cover">{children}</Box>
      <Box className="project-grid-selector__list-info">
        <Text
          size="3"
          weight="bold"
          truncate
          className="project-grid-selector__list-title"
        >
          {label}
        </Text>
        {project?.description ? (
          <Text
            size="2"
            color="gray"
            className="project-grid-selector__list-description"
          >
            {project.description}
          </Text>
        ) : null}
        {project ? (
          <Flex
            gap="3"
            mt="1"
            align="center"
            wrap="wrap"
            className="project-grid-selector__list-meta"
          >
            <Text
              size="1"
              color="gray"
            >
              {project.wordCount.toLocaleString()} {t("projects.words")}
            </Text>
            <Text
              size="1"
              color="gray"
            >
              {project.chapterCount} {t("projects.chapters")}
            </Text>
            <Text
              size="1"
              color="gray"
            >
              {formatRelativeTime(project.updatedAt)}
            </Text>
          </Flex>
        ) : null}
      </Box>
      {selected ? (
        <Check
          size={18}
          aria-hidden="true"
          className="project-grid-selector__list-check"
        />
      ) : null}
    </button>
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
  const { isMobile } = useAppShell();

  const handleSelect = (projectId: string) => {
    if (disabled) return;
    onChange(projectId);
  };

  const selectionOptions = [
    ...(showNoneOption
      ? [
          {
            id: "",
            label: t("projectSelect.noBinding"),
            project: null,
          },
        ]
      : []),
    ...projects.map((project) => ({
      id: project.id,
      label: project.title,
      project,
    })),
  ];

  return (
    <ScrollArea
      className="project-grid-selector__scroll"
      style={{ maxHeight: isMobile ? "min(64dvh, 520px)" : 380 }}
    >
      {isMobile ? (
        <Flex
          direction="column"
          gap="2"
          py="2"
        >
          {selectionOptions.map((option) => (
            <ProjectListCard
              key={option.id || "none"}
              project={option.project}
              selected={value === option.id}
              disabled={disabled}
              label={option.label}
              onSelect={() => handleSelect(option.id)}
            >
              {option.project?.coverUrl ? (
                <img
                  src={option.project.coverUrl}
                  alt={option.project.title}
                  className="project-grid-selector__list-cover-img"
                />
              ) : (
                <Flex
                  align="center"
                  justify="center"
                  className="project-grid-selector__list-cover-placeholder"
                >
                  {option.project ? <BookOpen size={24} /> : <X size={24} />}
                </Flex>
              )}
            </ProjectListCard>
          ))}
        </Flex>
      ) : (
        <Flex
          wrap="wrap"
          gap="3"
          py="2"
        >
          {selectionOptions.map((option) => (
            <ProjectCard
              key={option.id || "none"}
              selected={value === option.id}
              disabled={disabled}
              label={option.label}
              onSelect={() => handleSelect(option.id)}
            >
              {option.project?.coverUrl ? (
                <img
                  src={option.project.coverUrl}
                  alt={option.project.title}
                  className="project-grid-selector__cover-img"
                />
              ) : (
                <Flex
                  align="center"
                  justify="center"
                  className="project-grid-selector__cover-placeholder"
                >
                  {option.project ? <BookOpen size={24} /> : <X size={24} />}
                </Flex>
              )}
            </ProjectCard>
          ))}
        </Flex>
      )}
    </ScrollArea>
  );
}

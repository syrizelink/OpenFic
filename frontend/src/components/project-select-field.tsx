/**
 * Project Select Field Component
 *
 * 项目选择字段，使用展开面板显示项目网格选择器。
 */

import { Box, TextField, Popover, Text } from "@radix-ui/themes";
import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useAppShell } from "@/features/app-shell/components/app-shell-context";
import type { Project } from "@/lib/project.types";

import { MobileSelectSheet } from "./mobile-select-sheet";
import { ProjectGridSelector } from "./project-grid-selector";

import "./project-select-field.css";

export interface ProjectSelectFieldProps {
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
  /** 占位符文本 */
  placeholder?: string;
  /** 标签文本 */
  label?: string;
}

export function ProjectSelectField({
  projects,
  value,
  onChange,
  disabled = false,
  showNoneOption = true,
  placeholder,
  label,
}: ProjectSelectFieldProps) {
  const { t } = useTranslation();
  const { isMobile } = useAppShell();
  const [open, setOpen] = useState(false);

  // 获取当前选中的项目
  const selectedProject = value ? projects.find((p) => p.id === value) : null;

  // 显示文本（如果选中了项目显示标题，如果没选中且显示无绑定选项则显示"无绑定"，否则为空字符串以显示占位符）
  const displayText = selectedProject
    ? selectedProject.title
    : value === "" && showNoneOption
      ? t("projectSelect.noBinding")
      : "";

  // 处理选择
  const handleSelect = (projectId: string) => {
    onChange(projectId);
    setOpen(false);
  };

  // 处理输入框点击
  const handleInputClick = () => {
    if (!disabled) {
      setOpen(true);
    }
  };

  const trigger = (
    <Box
      className="project-select-field__trigger"
      data-disabled={disabled ? "true" : "false"}
    >
      <TextField.Root
        value={displayText}
        placeholder={placeholder ?? t("projectSelect.placeholder")}
        disabled={disabled}
        readOnly
        onClick={isMobile ? undefined : handleInputClick}
        className="project-select-field__input"
      />
      <Box className="project-select-field__chevron">
        <ChevronDown size={16} />
      </Box>
    </Box>
  );

  const selectorContent = (
    <ProjectGridSelector
      projects={projects}
      value={value}
      onChange={handleSelect}
      disabled={disabled}
      showNoneOption={showNoneOption}
    />
  );

  const desktopControl = (
    <Popover.Root
      open={open}
      onOpenChange={setOpen}
    >
      <Popover.Trigger>{trigger}</Popover.Trigger>
      <Popover.Content
        className="project-select-field__content"
        align="start"
        side="bottom"
      >
        {selectorContent}
      </Popover.Content>
    </Popover.Root>
  );

  const mobileControl = (
    <MobileSelectSheet
      open={open}
      onOpenChange={setOpen}
      title={label ?? placeholder ?? t("projectSelect.placeholder")}
      trigger={trigger}
    >
      {selectorContent}
    </MobileSelectSheet>
  );

  return (
    <Box>
      {label && (
        <Text
          as="label"
          size="2"
          weight="medium"
          mb="1"
          className="project-select-field__label"
        >
          {label}
        </Text>
      )}
      {isMobile ? mobileControl : desktopControl}
    </Box>
  );
}

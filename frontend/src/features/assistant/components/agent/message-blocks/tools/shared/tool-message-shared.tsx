import { Box, Text } from "@radix-ui/themes";
import type { ReactNode } from "react";

import i18n from "@/i18n";

import "./tool-message-shared.css";

function joinClassNames(...classNames: Array<string | undefined>) {
  return classNames.filter(Boolean).join(" ");
}

interface ToolBodyProps {
  children: ReactNode;
}

interface ToolGroupProps {
  label: string;
  children: ReactNode;
  className?: string;
}

interface ToolTextBlockProps {
  label: string;
  value?: string | null;
}

interface ToolListBlockProps {
  label: string;
  values: string[];
}

interface ToolStackProps {
  children: ReactNode;
  className?: string;
}

interface ToolPanelProps {
  title: string;
  children: ReactNode;
  className?: string;
}

interface ToolNoticeProps {
  children: ReactNode;
  title?: string;
  tone?: "neutral" | "warning" | "error";
}

export function ToolBody({ children }: ToolBodyProps) {
  return (
    <Box className="agent-tool-body">
      <Box className="agent-tool-block-content agent-tool-content-body">{children}</Box>
    </Box>
  );
}

export function ToolGroup({ label, children, className }: ToolGroupProps) {
  return (
    <Box className={joinClassNames("agent-tool-content-block", className)}>
      <Text
        size="1"
        weight="medium"
        color="gray"
        className="agent-tool-content-label"
      >
        {label}
      </Text>
      {children}
    </Box>
  );
}

export function ToolTextBlock({ label, value }: ToolTextBlockProps) {
  if (!value) return null;
  return (
    <Box className="agent-tool-content-block">
      <Text
        size="1"
        weight="medium"
        color="gray"
        className="agent-tool-content-label"
      >
        {label}
      </Text>
      <Box className="agent-tool-content-value agent-tool-content-plain-text">{value}</Box>
    </Box>
  );
}

export function ToolListBlock({ label, values }: ToolListBlockProps) {
  if (values.length === 0) return null;
  return (
    <ToolGroup label={label}>
      <ul className="agent-tool-content-list">
        {values.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </ToolGroup>
  );
}

export function ToolStack({ children, className }: ToolStackProps) {
  return <Box className={joinClassNames("agent-tool-content-stack", className)}>{children}</Box>;
}

export function ToolPanel({ title, children, className }: ToolPanelProps) {
  return (
    <Box className={joinClassNames("agent-tool-content-panel", className)}>
      <Text
        size="2"
        weight="medium"
        className="agent-tool-content-panel-title"
      >
        {title}
      </Text>
      {children}
    </Box>
  );
}

export function ToolNotice({
  children,
  title = i18n.t("assistant.tools.noContentToDisplay"),
  tone = "neutral",
}: ToolNoticeProps) {
  return (
    <Box
      className="agent-tool-notice"
      data-tone={tone}
    >
      <Text
        size="2"
        weight="medium"
        className="agent-tool-notice-title"
      >
        {title}
      </Text>
      <Box className="agent-tool-notice-body agent-tool-content-plain-text">{children}</Box>
    </Box>
  );
}

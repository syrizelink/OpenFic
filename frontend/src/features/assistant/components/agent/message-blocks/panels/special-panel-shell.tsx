import { Box, Flex, Text } from "@radix-ui/themes";
import type { ReactNode } from "react";

interface SpecialPanelShellProps {
  actions?: ReactNode;
  className?: string;
  content?: ReactNode;
  headingAction?: ReactNode;
  icon: ReactNode;
  isCollapsed?: boolean;
  kind: "approval" | "question";
  summary?: ReactNode;
  title: string;
  progress?: string;
}

export function SpecialPanelShell({
  actions,
  className,
  content,
  headingAction,
  icon,
  isCollapsed = false,
  kind,
  summary,
  title,
  progress,
}: SpecialPanelShellProps) {
  const panelClassName = ["agent-special-panel", `agent-special-panel-${kind}`, className]
    .filter(Boolean)
    .join(" ");

  return (
    <Box
      className={panelClassName}
      data-collapsed={isCollapsed ? "true" : undefined}
      data-panel-kind={kind}
    >
      <Flex
        align="center"
        gap="2"
        className="agent-special-panel-heading"
      >
        <Flex
          align="center"
          gap="2"
          className="agent-special-panel-title"
        >
          {icon}
          <Text
            size="2"
            weight="medium"
          >
            {title}
          </Text>
          {progress ? (
            <Text
              size="1"
              color="gray"
            >
              {progress}
            </Text>
          ) : null}
        </Flex>
        {headingAction ? (
          <Box className="agent-special-panel-heading-action">{headingAction}</Box>
        ) : null}
      </Flex>
      {summary ? (
        <Text
          size="2"
          className="agent-special-panel-summary"
        >
          {summary}
        </Text>
      ) : null}
      {!isCollapsed && content ? (
        <Box className="agent-special-panel-content">{content}</Box>
      ) : null}
      {!isCollapsed && actions ? (
        <Flex
          gap="2"
          justify="end"
          className="agent-special-panel-actions"
        >
          {actions}
        </Flex>
      ) : null}
    </Box>
  );
}

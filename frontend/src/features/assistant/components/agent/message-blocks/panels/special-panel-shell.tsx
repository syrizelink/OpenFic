import { Box, Flex, Text } from "@radix-ui/themes";
import type { ReactNode } from "react";

interface SpecialPanelShellProps {
  actions?: ReactNode;
  className?: string;
  content?: ReactNode;
  icon: ReactNode;
  kind: "approval" | "question";
  summary?: ReactNode;
  title: string;
}

export function SpecialPanelShell({
  actions,
  className,
  content,
  icon,
  kind,
  summary,
  title,
}: SpecialPanelShellProps) {
  const panelClassName = ["agent-special-panel", `agent-special-panel-${kind}`, className]
    .filter(Boolean)
    .join(" ");

  return (
    <Box
      className={panelClassName}
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
        </Flex>
      </Flex>
      {summary ? (
        <Text
          size="2"
          className="agent-special-panel-summary"
        >
          {summary}
        </Text>
      ) : null}
      {content ? <Box>{content}</Box> : null}
      {actions ? (
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

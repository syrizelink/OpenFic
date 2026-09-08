import { Flex, Text, Tooltip } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";

import type { AgentMessageNavigationItem } from "./agent-message-navigation";

interface AgentMessageNavigatorProps {
  items: AgentMessageNavigationItem[];
  activeId: string | null;
  viewportHeight: number;
  onNavigate: (item: AgentMessageNavigationItem) => void;
}

export function AgentMessageNavigator({
  items,
  activeId,
  viewportHeight,
  onNavigate,
}: AgentMessageNavigatorProps) {
  const { t, i18n } = useTranslation();

  if (items.length < 2 || viewportHeight <= 0) return null;

  return (
    <nav
      className="agent-message-navigator"
      aria-label={t("assistant.messageNavigatorLabel")}
      style={{ height: Math.max(0, viewportHeight - 16) }}
    >
      {items.map((item, index) => {
        const timestamp =
          item.timestamp === undefined
            ? null
            : new Intl.DateTimeFormat(i18n.language, {
                dateStyle: "short",
                timeStyle: "short",
              }).format(new Date(item.timestamp));

        return (
          <Tooltip
            key={item.id}
            content={
              <Flex
                direction="column"
                gap="1"
                className="agent-message-navigator-preview"
              >
                {timestamp ? (
                  <Text
                    size="1"
                    color="gray"
                  >
                    {timestamp}
                  </Text>
                ) : null}
                <Text size="2">{item.preview}</Text>
              </Flex>
            }
          >
            <button
              type="button"
              className="agent-message-navigator-marker"
              data-active={item.id === activeId ? "true" : undefined}
              aria-label={t("assistant.messageNavigatorItem", {
                index: index + 1,
                preview: item.preview,
              })}
              onClick={() => onNavigate(item)}
            />
          </Tooltip>
        );
      })}
    </nav>
  );
}

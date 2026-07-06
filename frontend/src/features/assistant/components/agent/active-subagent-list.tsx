import { Box, Text } from "@radix-ui/themes";
import { Bot, ChevronRight } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { formatSubagentDisplayLabel } from "@/features/assistant/lib/subagent-display";
import type { ActiveSubagentState } from "@/lib/agent.types";

import "./active-subagent-list.css";

interface ActiveSubagentListProps {
  items: ActiveSubagentState[];
  title: string;
  onOpen: (item: ActiveSubagentState) => void;
}

function getStatusTone(status: ActiveSubagentState["status"]) {
  if (status === "error" || status === "cancelled") return "danger";
  if (status === "waiting_user") return "waiting";
  if (status === "completed") return "success";
  return "running";
}

function getStatusLabel(
  status: ActiveSubagentState["status"],
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  if (status === "queued") return t("writing.aiSidebar.subagentStatusQueued");
  if (status === "running") return t("writing.aiSidebar.subagentStatusRunning");
  if (status === "waiting_user") return t("writing.aiSidebar.subagentStatusWaitingUser");
  if (status === "completed") return t("writing.aiSidebar.subagentStatusCompleted");
  if (status === "error") return t("writing.aiSidebar.subagentStatusError");
  if (status === "cancelled") return t("writing.aiSidebar.subagentStatusCancelled");
  return status;
}

export function ActiveSubagentList({ items, title, onOpen }: ActiveSubagentListProps) {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState(false);

  if (items.length === 0) return null;

  return (
    <Box
      className="active-subagent-panel"
      aria-label={title}
    >
      <AnimatePresence initial={false}>
        {!collapsed ? (
          <motion.ul
            key="subagent-list"
            className="active-subagent-panel-list"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeInOut" }}
          >
            {items.map((item) => (
              <li
                key={item.childRunId}
                className="active-subagent-panel-list-item"
              >
                <button
                  type="button"
                  onClick={() => onOpen(item)}
                  className="active-subagent-row"
                  data-status={getStatusTone(item.status)}
                >
                  <span className="active-subagent-row-main">
                    <span
                      className="active-subagent-row-indicator"
                      aria-hidden="true"
                    />
                    <Text
                      as="span"
                      size="1"
                      weight="medium"
                      className="active-subagent-row-agent"
                    >
                      {formatSubagentDisplayLabel(item.agentKey, item.agentNumber)}
                    </Text>
                  </span>
                  <span className="active-subagent-row-meta">
                    {item.queuedMessages > 0 ? (
                      <Text
                        as="span"
                        size="1"
                        className="active-subagent-row-queue"
                      >
                        +{item.queuedMessages}
                      </Text>
                    ) : null}
                    <Text
                      as="span"
                      size="1"
                      className="active-subagent-row-status"
                    >
                      {getStatusLabel(item.status, t)}
                    </Text>
                  </span>
                </button>
              </li>
            ))}
          </motion.ul>
        ) : null}
      </AnimatePresence>

      <button
        type="button"
        className="active-subagent-panel-toggle"
        aria-expanded={!collapsed}
        onClick={() => setCollapsed((current) => !current)}
      >
        <span className="active-subagent-panel-title-group">
          <span
            className="active-subagent-panel-icon-wrap"
            aria-hidden="true"
          >
            <Bot size={14} />
          </span>
          <Text
            as="span"
            size="1"
            className="active-subagent-panel-title"
          >
            {t("writing.aiSidebar.activeSubagentsCount", { count: items.length })}
          </Text>
        </span>
        <motion.span
          className="active-subagent-panel-chevron"
          aria-hidden="true"
          animate={{ rotate: collapsed ? 0 : 90 }}
          transition={{ duration: 0.2, ease: "easeInOut" }}
        >
          <ChevronRight size={14} />
        </motion.span>
      </button>
    </Box>
  );
}

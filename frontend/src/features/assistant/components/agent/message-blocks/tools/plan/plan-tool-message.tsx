import { Box, Text, Tooltip } from "@radix-ui/themes";
import { ChevronUp, ChevronsUp, Minus } from "lucide-react";

import i18n from "@/i18n";
import type { AgentMessage } from "@/lib/agent.types";

import "./plan-tool-message.css";

import { ToolBody, ToolNotice } from "../shared/tool-message-shared";
import { getPlanTodos, getToolResultMessage } from "../shared/tool-message-utils";
import { getPlanTodoMarker } from "./plan-tool-message.utils";

interface PlanToolMessageProps {
  message: AgentMessage;
}

function getPlanMarkerGlyph(marker: string): string {
  if (marker === "[*]") return "";
  if (marker === "[✓]") return "✓";
  return "";
}

function PlanPriorityIcon({ priority }: { priority: "low" | "medium" | "high" }) {
  if (priority === "high")
    return (
      <ChevronsUp
        size={14}
        aria-hidden="true"
      />
    );
  if (priority === "medium")
    return (
      <ChevronUp
        size={14}
        aria-hidden="true"
      />
    );
  return (
    <Minus
      size={14}
      aria-hidden="true"
    />
  );
}

export function PlanToolMessage({ message }: PlanToolMessageProps) {
  const todos = getPlanTodos(message);

  if (todos.length === 0) {
    return (
      <ToolBody>
        <ToolNotice title={i18n.t("assistant.tools.noPlanContent")}>
          {getToolResultMessage(message) ?? i18n.t("assistant.tools.noPlanContentDescription")}
        </ToolNotice>
      </ToolBody>
    );
  }

  return (
    <ToolBody>
      <Box className="agent-plan-panel">
        <ul className="agent-plan-list">
          {todos.map((todo, index) => (
            <li
              key={`${todo.content}-${index}`}
              className="agent-plan-row agent-plan-item"
              data-kind="todo"
              data-status={todo.status}
            >
              <span
                className="agent-plan-marker"
                data-status={todo.status}
                aria-hidden="true"
              >
                <span className="agent-plan-marker-glyph">
                  {getPlanMarkerGlyph(getPlanTodoMarker(todo.status))}
                </span>
              </span>
              <Box className="agent-plan-item-main">
                <Box className="agent-plan-item-title-row">
                  <Text className="agent-plan-item-title agent-tool-content-plain-text">
                    {todo.content}
                  </Text>
                  <Tooltip content={i18n.t(`assistant.tools.planPriority.${todo.priority}`)}>
                    <span
                      role="img"
                      className="agent-plan-priority agent-tool-content-plain-text"
                      data-priority={todo.priority}
                      aria-label={i18n.t(`assistant.tools.planPriority.${todo.priority}`)}
                    >
                      <PlanPriorityIcon priority={todo.priority} />
                    </span>
                  </Tooltip>
                </Box>
              </Box>
            </li>
          ))}
        </ul>
      </Box>
    </ToolBody>
  );
}

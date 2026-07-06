import { Box, Text } from "@radix-ui/themes";
import { ChevronDown, EllipsisVertical } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type ReactNode } from "react";

import i18n from "@/i18n";
import type { AgentMessage } from "@/lib/agent.types";

import "./plan-tool-message.css";

import { ToolBody, ToolNotice } from "../shared/tool-message-shared";
import {
  getPlanPayload,
  getToolResultMessage,
  type PlanPayload,
} from "../shared/tool-message-utils";
import {
  buildPlanChecklistItems,
  buildUpdatePlanDisplayRows,
  getPlanCardTopic,
  getPlanTodoToggleLabel,
  type PlanChecklistItem,
  type PlanDisplayRow,
} from "./plan-tool-message.utils";

interface PlanToolMessageProps {
  message: AgentMessage;
}

function getPlanMarkerGlyph(marker: string): string {
  if (marker === "[*]") return "*";
  if (marker === "[✓]") return "✓";
  return "";
}

function PlanCardFrame({
  plan,
  description,
  topRowSuffix,
  children,
}: {
  plan: PlanPayload;
  description?: ReactNode;
  topRowSuffix?: ReactNode;
  children: ReactNode;
}) {
  const topic = getPlanCardTopic(plan);
  return (
    <Box className="agent-plan-panel">
      {topic ? (
        <Box className="agent-plan-top-row">
          <Text className="agent-plan-topic-label">{i18n.t("assistant.tools.topic")}</Text>
          <Text className="agent-plan-topic-value agent-tool-content-plain-text">{topic}</Text>
          {topRowSuffix}
        </Box>
      ) : null}
      {description}
      {children}
    </Box>
  );
}

function PlanTodoRow({
  item,
  expanded,
  onToggle,
}: {
  item: PlanChecklistItem;
  expanded: boolean;
  onToggle: () => void;
}) {
  const showContent = expanded && item.content.trim().length > 0;

  return (
    <li
      className="agent-plan-row agent-plan-item"
      data-kind="todo"
    >
      <span
        className="agent-plan-marker"
        data-status={item.status}
        aria-hidden="true"
      >
        <span className="agent-plan-marker-glyph">{getPlanMarkerGlyph(item.marker)}</span>
      </span>
      <Box className="agent-plan-item-main">
        <Box className="agent-plan-item-title-row">
          <Text className="agent-plan-item-title agent-tool-content-plain-text">{item.title}</Text>
          <button
            type="button"
            className="agent-plan-item-toggle"
            data-expanded={expanded ? "true" : "false"}
            aria-expanded={expanded}
            aria-label={getPlanTodoToggleLabel(expanded)}
            onClick={(event) => {
              event.stopPropagation();
              onToggle();
            }}
          >
            <ChevronDown
              size={14}
              aria-hidden="true"
            />
          </button>
        </Box>
        <AnimatePresence initial={false}>
          {showContent ? (
            <motion.div
              key={`${item.id}-content`}
              className="agent-plan-item-content-shell"
              initial={{ height: 0, opacity: 0, marginTop: 0 }}
              animate={{ height: "auto", opacity: 1, marginTop: 4 }}
              exit={{ height: 0, opacity: 0, marginTop: 0 }}
              transition={{
                height: { duration: 0.18, ease: [0.22, 1, 0.36, 1] },
                opacity: { duration: 0.12, ease: "easeOut" },
                marginTop: { duration: 0.18, ease: [0.22, 1, 0.36, 1] },
              }}
            >
              <Box className="agent-plan-item-content agent-tool-content-plain-text">
                {item.content}
              </Box>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </Box>
    </li>
  );
}

function PlanSummaryRow({ row }: { row: Extract<PlanDisplayRow, { kind: "summary" }> }) {
  return (
    <li
      className="agent-plan-row agent-plan-summary"
      data-kind="summary"
    >
      <span
        className="agent-plan-marker"
        data-summary="true"
        aria-hidden="true"
      >
        <EllipsisVertical
          size={12}
          aria-hidden="true"
        />
      </span>
      <Box className="agent-plan-summary-main">
        <Text className="agent-plan-summary-label agent-tool-content-plain-text">{row.label}</Text>
      </Box>
    </li>
  );
}

function PlanCreateCard({ plan }: { plan: PlanPayload }) {
  const checklistItems = buildPlanChecklistItems(plan);
  const description = plan.description?.trim() ? (
    <Box className="agent-plan-description agent-tool-content-plain-text">{plan.description}</Box>
  ) : null;

  return (
    <PlanCardFrame
      plan={plan}
      description={description}
    >
      {checklistItems.length > 0 ? (
        <ul className="agent-plan-list">
          {checklistItems.map((item) => {
            const showContent = item.content !== item.title;

            return (
              <li
                key={item.id}
                className="agent-plan-row agent-plan-item"
                data-kind="todo"
              >
                <span
                  className="agent-plan-marker"
                  data-status={item.status}
                  aria-hidden="true"
                >
                  <span className="agent-plan-marker-glyph">{getPlanMarkerGlyph(item.marker)}</span>
                </span>
                <Box className="agent-plan-item-main">
                  <Text className="agent-plan-item-title">{item.title}</Text>
                  {showContent ? (
                    <Box className="agent-plan-item-content agent-tool-content-plain-text">
                      {item.content}
                    </Box>
                  ) : null}
                </Box>
              </li>
            );
          })}
        </ul>
      ) : (
        <Box className="agent-plan-empty agent-tool-content-plain-text">
          {i18n.t("assistant.tools.noPlanSteps")}
        </Box>
      )}
    </PlanCardFrame>
  );
}

function PlanUpdateCard({ plan }: { plan: PlanPayload }) {
  const rows = buildUpdatePlanDisplayRows(plan);
  const [expandedTodoIds, setExpandedTodoIds] = useState<Record<string, boolean>>({});
  const [descriptionExpanded, setDescriptionExpanded] = useState(false);
  const description = plan.description?.trim() ? (
    <AnimatePresence initial={false}>
      {descriptionExpanded ? (
        <motion.div
          key="plan-description"
          className="agent-plan-description-shell"
          initial={{ height: 0, opacity: 0, marginTop: 0 }}
          animate={{ height: "auto", opacity: 1, marginTop: 4 }}
          exit={{ height: 0, opacity: 0, marginTop: 0 }}
          transition={{
            height: { duration: 0.18, ease: [0.22, 1, 0.36, 1] },
            opacity: { duration: 0.12, ease: "easeOut" },
            marginTop: { duration: 0.18, ease: [0.22, 1, 0.36, 1] },
          }}
        >
          <Box className="agent-plan-description agent-tool-content-plain-text">
            {plan.description}
          </Box>
        </motion.div>
      ) : null}
    </AnimatePresence>
  ) : null;
  const descriptionToggle = plan.description?.trim() ? (
    <button
      type="button"
      className="agent-plan-item-toggle"
      data-expanded={descriptionExpanded ? "true" : "false"}
      aria-expanded={descriptionExpanded}
      aria-label={
        descriptionExpanded
          ? i18n.t("assistant.tools.collapsePlanDescription")
          : i18n.t("assistant.tools.expandPlanDescription")
      }
      onClick={() => {
        setDescriptionExpanded((current) => !current);
      }}
    >
      <ChevronDown
        size={14}
        aria-hidden="true"
      />
    </button>
  ) : null;

  return (
    <PlanCardFrame
      plan={plan}
      description={description}
      topRowSuffix={descriptionToggle}
    >
      {rows.length > 0 ? (
        <ul className="agent-plan-list">
          {rows.map((row) => {
            if (row.kind === "summary") {
              return (
                <PlanSummaryRow
                  key={row.id}
                  row={row}
                />
              );
            }

            return (
              <PlanTodoRow
                key={row.id}
                item={row.item}
                expanded={Boolean(expandedTodoIds[row.id])}
                onToggle={() => {
                  setExpandedTodoIds((current) => ({
                    ...current,
                    [row.id]: !current[row.id],
                  }));
                }}
              />
            );
          })}
        </ul>
      ) : (
        <Box className="agent-plan-empty agent-tool-content-plain-text">
          {i18n.t("assistant.tools.noPlanSteps")}
        </Box>
      )}
    </PlanCardFrame>
  );
}

export function PlanToolMessage({ message }: PlanToolMessageProps) {
  const singlePlan = getPlanPayload(message);
  const shouldRenderBody = message.toolName === "create_plan" || message.toolName === "update_plan";

  if (shouldRenderBody && singlePlan) {
    return (
      <ToolBody>
        {message.toolName === "update_plan" ? (
          <PlanUpdateCard plan={singlePlan} />
        ) : (
          <PlanCreateCard plan={singlePlan} />
        )}
      </ToolBody>
    );
  }

  if (!shouldRenderBody) return null;

  return (
    <ToolBody>
      <ToolNotice title={i18n.t("assistant.tools.noPlanContent")}>
        {getToolResultMessage(message) ?? i18n.t("assistant.tools.noPlanContentDescription")}
      </ToolNotice>
    </ToolBody>
  );
}

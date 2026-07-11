import { Badge, Box, Flex, IconButton, Text, Tooltip } from "@radix-ui/themes";
import { ChevronRight, RefreshCw, Square } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getIndexStatusColor,
  useStartProjectIndex,
  useStopProjectIndex,
  type ProjectIndexStatus,
} from "@/lib/index-status";

import { IndexSettingsSectionHeader } from "./index-settings-section-header";

export interface IndexUnitStatus {
  id: string;
  labelKey: string;
  status: ProjectIndexStatus["status"];
  total: number;
  indexed: number;
  pending: number;
}

export interface ProjectIndexGroup {
  projectId: string;
  title: string;
  enabled: boolean;
  status: ProjectIndexStatus["status"];
  units: IndexUnitStatus[];
}

interface ProjectIndexListProps {
  groups: ProjectIndexGroup[];
}

const EXPAND_TRANSITION = {
  height: { duration: 0.22, ease: [0.22, 1, 0.36, 1] },
  opacity: { duration: 0.18, ease: "easeOut" },
} as const;

export function ProjectIndexList({ groups }: ProjectIndexListProps) {
  const { t } = useTranslation();

  return (
    <Box className="index-settings-card">
      <Flex
        direction="column"
        gap="3"
      >
        <IndexSettingsSectionHeader title={t("index.objects")} />
        {groups.length > 0 ? (
          <Flex
            direction="column"
            gap="2"
          >
            {groups.map((group) => (
              <ProjectIndexAccordionItem
                key={group.projectId}
                group={group}
              />
            ))}
          </Flex>
        ) : (
          <Text
            size="2"
            color="gray"
          >
            {t("index.infoEmpty")}
          </Text>
        )}
      </Flex>
    </Box>
  );
}

function ProjectIndexAccordionItem({ group }: { group: ProjectIndexGroup }) {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);
  const bodyId = useId();
  const indexed = group.units.reduce((sum, unit) => sum + unit.indexed, 0);
  const total = group.units.reduce((sum, unit) => sum + unit.total, 0);
  const progressText =
    total === 0 ? t("index.status.no_chapters") : t("index.progress", { indexed, total });
  const color = getIndexStatusColor(group.status);

  return (
    <Box className="project-index-list-item">
      <button
        type="button"
        className="project-index-list-header"
        aria-expanded={isExpanded}
        aria-controls={bodyId}
        onClick={() => setIsExpanded((expanded) => !expanded)}
      >
        <span className="project-index-list-header-main">
          <motion.span
            className="project-index-list-expand-icon"
            initial={false}
            animate={{ rotate: isExpanded ? 90 : 0 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
          >
            <ChevronRight size={15} />
          </motion.span>
          <Text
            as="span"
            size="2"
            weight="medium"
            className="project-index-list-header-title"
          >
            {group.title || t("index.untitledProject")}
          </Text>
          <Text
            as="span"
            size="1"
            color="gray"
          >
            {progressText}
          </Text>
        </span>
        <IndexStatusBadge
          status={group.status}
          color={color}
        />
      </button>

      <AnimatePresence initial={false}>
        {isExpanded ? (
          <motion.div
            id={bodyId}
            className="project-index-list-body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={EXPAND_TRANSITION}
          >
            {group.units.map((unit) => (
              <IndexUnitRow
                key={unit.id}
                projectId={group.projectId}
                enabled={group.enabled}
                unit={unit}
              />
            ))}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </Box>
  );
}

function IndexUnitRow({
  projectId,
  enabled,
  unit,
}: {
  projectId: string;
  enabled: boolean;
  unit: IndexUnitStatus;
}) {
  const { t } = useTranslation();
  const startMutation = useStartProjectIndex(projectId);
  const stopMutation = useStopProjectIndex(projectId);
  const shouldReduceMotion = useReducedMotion();
  const color = getIndexStatusColor(unit.status);
  const progress =
    unit.total > 0 ? Math.min(100, Math.max(0, (unit.indexed / unit.total) * 100)) : 0;
  const progressText =
    unit.total === 0
      ? t("index.status.no_chapters")
      : t("index.progress", { indexed: unit.indexed, total: unit.total });
  const canStart =
    enabled &&
    unit.status !== "indexing" &&
    unit.status !== "disabled" &&
    unit.status !== "not_configured" &&
    unit.status !== "no_chapters" &&
    unit.pending > 0;
  const isIndexing = unit.status === "indexing";
  const isSubmitting = startMutation.isPending || stopMutation.isPending;

  return (
    <div className="project-index-list-unit">
      <span className="project-index-list-unit-main">
        <Tooltip content={isIndexing ? t("index.stopIndex") : t("index.startIndex")}>
          <IconButton
            size="1"
            variant="ghost"
            color="gray"
            aria-label={isIndexing ? t("index.stopIndex") : t("index.startIndex")}
            onClick={() => {
              if (isIndexing) {
                stopMutation.mutate();
                return;
              }
              startMutation.mutate();
            }}
            disabled={isIndexing ? isSubmitting : !canStart || isSubmitting}
          >
            {isIndexing ? (
              <Square
                size={12}
                fill="currentColor"
              />
            ) : (
              <RefreshCw size={14} />
            )}
          </IconButton>
        </Tooltip>
        <Text
          as="span"
          size="2"
          weight="medium"
          className="project-index-list-unit-title"
        >
          {t(unit.labelKey)}
        </Text>
        <Text
          as="span"
          size="1"
          color="gray"
          className="project-index-list-progress"
        >
          {progressText}
        </Text>
        {unit.total > 0 ? (
          <span
            className="project-index-list-progress-track"
            role="progressbar"
            aria-label={progressText}
            aria-valuemin={0}
            aria-valuemax={unit.total}
            aria-valuenow={Math.min(unit.total, Math.max(0, unit.indexed))}
            aria-valuetext={progressText}
          >
            <motion.span
              className="project-index-list-progress-indicator"
              initial={false}
              animate={{ width: `${progress}%` }}
              transition={
                shouldReduceMotion ? { duration: 0 } : { duration: 0.35, ease: [0.22, 1, 0.36, 1] }
              }
            />
          </span>
        ) : null}
      </span>
      <IndexStatusBadge
        status={unit.status}
        color={color}
      />
    </div>
  );
}

function IndexStatusBadge({
  status,
  color,
}: {
  status: ProjectIndexStatus["status"];
  color: string;
}) {
  const { t } = useTranslation();

  return (
    <Badge
      size="1"
      variant="soft"
      style={{ color }}
    >
      {t(`index.status.${status}` as const)}
    </Badge>
  );
}

import { Box, Dialog, Flex, IconButton, Text, Tooltip } from "@radix-ui/themes";
import type { TFunction } from "i18next";
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  Columns2,
  ChevronsDownUp,
  ChevronsUpDown,
  ExternalLink,
  FileDiff,
  Globe,
  Notebook,
  Rows3,
  TextAlignJustify,
  UserRound,
  WrapText,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  type AgentChangeItem,
  type AgentChangeLine,
  type AgentChangeSummary,
  type AgentSessionChanges,
} from "@/lib/agent.types";

import "./agent-changes.css";

const SUMMARY_VISIBLE_ITEM_COUNT = 3;

const CHANGE_KIND_ICONS: Record<AgentChangeItem["kind"], LucideIcon> = {
  chapter: BookOpen,
  note: Notebook,
  world_entry: Globe,
  character: UserRound,
};

interface AgentChangeSummaryCardProps {
  summary: AgentChangeSummary;
  onOpenChanges?: () => void;
}

interface AgentChangeItemDiffProps {
  item: AgentChangeItem;
  isExpanded: boolean;
  isSplitView: boolean;
  isWrapEnabled: boolean;
  onToggle: () => void;
}

interface AgentSessionChangesDialogProps {
  changes: AgentSessionChanges | null;
  summaryOverride?: AgentChangeSummary | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

interface SplitDiffRow {
  before: AgentChangeLine | null;
  after: AgentChangeLine | null;
}

const EMPTY_CHANGE_SUMMARY: AgentChangeSummary = {
  itemCount: 0,
  added: 0,
  removed: 0,
  items: [],
};

function getLinePrefix(type: AgentChangeLine["type"]): string {
  if (type === "added") return "+";
  if (type === "removed") return "-";
  return " ";
}

function getItemKey(item: AgentChangeItem): string {
  return `${item.key}:${item.source}:${item.childRunId ?? "primary"}:${item.requestId ?? "current"}`;
}

function ChangeKindIcon({ item, size = 15 }: { item: AgentChangeItem; size?: number }) {
  const Icon = CHANGE_KIND_ICONS[item.kind];
  return (
    <span
      className="agent-change-kind-icon"
      aria-hidden="true"
    >
      <Icon size={size} />
    </span>
  );
}

function ChangeItemName({ item }: { item: AgentChangeItem }) {
  const path = item.path.filter((part) => part.trim().length > 0);
  return (
    <span className="agent-change-item-name">
      {path.length > 0 ? <span className="agent-change-item-path">{path.join("/")}/</span> : null}
      <span className="agent-change-item-label">{item.title}</span>
    </span>
  );
}

function getSummaryDetails(summary: AgentChangeSummary, t: TFunction, language: string): string {
  const counts = new Map<AgentChangeItem["kind"], number>();
  for (const item of summary.items) {
    counts.set(item.kind, (counts.get(item.kind) ?? 0) + 1);
  }
  const kindOrder: AgentChangeItem["kind"][] = ["chapter", "note", "world_entry", "character"];
  const parts = kindOrder.flatMap((kind) => {
    const count = counts.get(kind) ?? 0;
    return count > 0
      ? [t(`assistant.sessionChanges.kindCount.${kind}.${count === 1 ? "one" : "many"}`, { count })]
      : [];
  });
  const formatted = new Intl.ListFormat(language, { style: "long", type: "conjunction" }).format(
    parts,
  );
  return language.toLowerCase().startsWith("zh")
    ? formatted.replace(/和(?=\S)/g, "和 ")
    : formatted;
}

function ChangeSummaryTitle({
  summary,
  className,
}: {
  summary: AgentChangeSummary;
  className: string;
}) {
  const { t, i18n } = useTranslation();
  const item = summary.items.length === 1 ? summary.items[0] : null;
  return (
    <Text
      size="2"
      weight="medium"
      className={className}
    >
      {item ? (
        <span className="agent-change-summary-single-title">
          <span>{t("assistant.sessionChanges.edited")}</span>
          <ChangeKindIcon
            item={item}
            size={14}
          />
          <ChangeItemName item={item} />
        </span>
      ) : summary.items.length > 1 ? (
        t("assistant.sessionChanges.editedSummary", {
          details: getSummaryDetails(summary, t, i18n.language),
        })
      ) : (
        t("assistant.sessionChanges.title")
      )}
    </Text>
  );
}

function ChangeStats({ added, removed }: Pick<AgentChangeItem, "added" | "removed">) {
  return (
    <Flex
      align="center"
      gap="2"
      className="agent-change-stats"
      aria-label={`+${added} -${removed}`}
    >
      <Text
        size="1"
        className="agent-change-stat"
        data-change="added"
      >
        +{added}
      </Text>
      <Text
        size="1"
        className="agent-change-stat"
        data-change="removed"
      >
        -{removed}
      </Text>
    </Flex>
  );
}

function ChangeLine({ line }: { line: AgentChangeLine }) {
  return (
    <div
      className="agent-change-diff-line"
      data-type={line.type}
    >
      <span className="agent-change-diff-prefix">{getLinePrefix(line.type)}</span>
      <span className="agent-change-diff-gutter">
        {line.afterLineNumber ?? line.beforeLineNumber ?? ""}
      </span>
      <span className="agent-change-diff-text">{line.text || " "}</span>
    </div>
  );
}

function buildSplitDiffRows(lines: AgentChangeLine[]): SplitDiffRow[] {
  const rows: SplitDiffRow[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (line.type === "context") {
      rows.push({ before: line, after: line });
      index += 1;
      continue;
    }

    const changedLines: AgentChangeLine[] = [];
    while (index < lines.length && lines[index].type !== "context") {
      changedLines.push(lines[index]);
      index += 1;
    }
    const removedLines = changedLines.filter((changedLine) => changedLine.type === "removed");
    const addedLines = changedLines.filter((changedLine) => changedLine.type === "added");
    const rowCount = Math.max(removedLines.length, addedLines.length);
    for (let rowIndex = 0; rowIndex < rowCount; rowIndex += 1) {
      rows.push({
        before: removedLines[rowIndex] ?? null,
        after: addedLines[rowIndex] ?? null,
      });
    }
  }
  return rows;
}

function SplitChangeCell({
  line,
  side,
}: {
  line: AgentChangeLine | null;
  side: "before" | "after";
}) {
  const lineType = line?.type ?? "empty";
  const lineNumber = side === "before" ? line?.beforeLineNumber : line?.afterLineNumber;
  return (
    <div
      className="agent-change-split-cell"
      data-side={side}
      data-type={lineType}
    >
      <span className="agent-change-diff-prefix">{line ? getLinePrefix(line.type) : ""}</span>
      <span className="agent-change-diff-gutter">{lineNumber ?? ""}</span>
      <span className="agent-change-diff-text">{line?.text || " "}</span>
    </div>
  );
}

function SplitChangeRows({
  lines,
  isWrapEnabled,
}: {
  lines: AgentChangeLine[];
  isWrapEnabled: boolean;
}) {
  const rows = buildSplitDiffRows(lines);
  const beforeRowRefs = useRef<(HTMLDivElement | null)[]>([]);
  const afterRowRefs = useRef<(HTMLDivElement | null)[]>([]);

  useLayoutEffect(() => {
    for (const row of [...beforeRowRefs.current, ...afterRowRefs.current]) {
      row?.style.removeProperty("--agent-change-split-row-height");
    }
    if (!isWrapEnabled) return;

    const syncRowHeights = () => {
      rows.forEach((_, index) => {
        const beforeRow = beforeRowRefs.current[index];
        const afterRow = afterRowRefs.current[index];
        if (!beforeRow || !afterRow) return;
        const rowHeight = Math.max(beforeRow.scrollHeight, afterRow.scrollHeight);
        beforeRow.style.setProperty("--agent-change-split-row-height", `${rowHeight}px`);
        afterRow.style.setProperty("--agent-change-split-row-height", `${rowHeight}px`);
      });
    };

    syncRowHeights();
    const observer = new ResizeObserver(syncRowHeights);
    for (const row of [...beforeRowRefs.current, ...afterRowRefs.current]) {
      if (row) observer.observe(row);
    }
    return () => observer.disconnect();
  }, [isWrapEnabled, rows]);

  return (
    <div
      className="agent-change-split-scroll"
      data-wrap={isWrapEnabled ? "true" : "false"}
    >
      <div className="agent-change-split-panes">
        <div
          className="agent-change-split-pane"
          data-side="before"
        >
          <div className="agent-change-split-pane-content">
            {rows.map((row, index) => (
              <div
                key={`${index}-${row.before?.beforeLineNumber ?? "n"}`}
                ref={(element) => {
                  beforeRowRefs.current[index] = element;
                }}
                className="agent-change-split-row"
              >
                <SplitChangeCell
                  line={row.before}
                  side="before"
                />
              </div>
            ))}
          </div>
        </div>
        <div
          className="agent-change-split-pane"
          data-side="after"
        >
          <div className="agent-change-split-pane-content">
            {rows.map((row, index) => (
              <div
                key={`${index}-${row.after?.afterLineNumber ?? "n"}`}
                ref={(element) => {
                  afterRowRefs.current[index] = element;
                }}
                className="agent-change-split-row"
              >
                <SplitChangeCell
                  line={row.after}
                  side="after"
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function TitleChange({ before, after }: { before: string; after: string }) {
  return (
    <div className="agent-change-title-change">
      <span>{before}</span>
      <span aria-hidden="true">→</span>
      <span>{after}</span>
    </div>
  );
}

function AgentChangeItemDiff({
  item,
  isExpanded,
  isSplitView,
  isWrapEnabled,
  onToggle,
}: AgentChangeItemDiffProps) {
  const { t } = useTranslation();
  const lines = item.sections.flatMap((section) => section.lines);
  const hasTitleChange = Boolean(item.titleBefore && item.titleAfter);
  return (
    <Box
      className="agent-change-item"
      data-kind={item.kind}
      data-expanded={isExpanded ? "true" : "false"}
    >
      <button
        type="button"
        className="agent-change-item-header"
        aria-expanded={isExpanded}
        onClick={onToggle}
      >
        <span className="agent-change-item-leading">
          <span className="agent-change-item-title-row">
            <ChangeKindIcon item={item} />
            <Text
              size="1"
              weight="medium"
              className="agent-change-item-title"
            >
              <ChangeItemName item={item} />
            </Text>
          </span>
          <ChangeStats
            added={item.added}
            removed={item.removed}
          />
        </span>
        <span
          className="agent-change-item-disclosure-icon"
          aria-hidden="true"
        >
          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
      </button>
      {isExpanded ? (
        <Box className="agent-change-item-body">
          {lines.length > 0 ? (
            isSplitView ? (
              <SplitChangeRows
                lines={lines}
                isWrapEnabled={isWrapEnabled}
              />
            ) : (
              <div
                className="agent-change-diff-lines"
                data-wrap={isWrapEnabled ? "true" : "false"}
              >
                {lines.map((line, index) => (
                  <ChangeLine
                    key={`${index}-${line.beforeLineNumber ?? "n"}-${line.afterLineNumber ?? "n"}`}
                    line={line}
                  />
                ))}
              </div>
            )
          ) : hasTitleChange ? (
            <TitleChange
              before={item.titleBefore!}
              after={item.titleAfter!}
            />
          ) : (
            <Text
              size="1"
              className="agent-change-diff-empty"
            >
              {t("assistant.sessionChanges.noLines")}
            </Text>
          )}
        </Box>
      ) : null}
    </Box>
  );
}

export function AgentChangeSummaryCard({ summary, onOpenChanges }: AgentChangeSummaryCardProps) {
  const { t } = useTranslation();
  const [isItemsExpanded, setIsItemsExpanded] = useState(false);
  const [isListVisible, setIsListVisible] = useState(true);
  const hasMultipleItems = summary.items.length > 1;
  const visibleItems = isItemsExpanded
    ? summary.items
    : summary.items.slice(0, SUMMARY_VISIBLE_ITEM_COUNT);
  const remainingCount = hasMultipleItems
    ? Math.max(0, summary.items.length - SUMMARY_VISIBLE_ITEM_COUNT)
    : 0;
  const handleHeaderClick = () => {
    if (hasMultipleItems) setIsListVisible((visible) => !visible);
  };
  const handleHeaderKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!hasMultipleItems || (event.key !== "Enter" && event.key !== " ")) return;
    event.preventDefault();
    handleHeaderClick();
  };
  const stats = (
    <ChangeStats
      added={summary.added}
      removed={summary.removed}
    />
  );
  const statsRow = onOpenChanges ? (
    <button
      type="button"
      className="agent-change-summary-stats-row agent-change-summary-open-button"
      data-actionable="true"
      aria-label={t("assistant.sessionChanges.open")}
      onClick={(event) => {
        event.stopPropagation();
        onOpenChanges();
      }}
      onKeyDown={(event) => event.stopPropagation()}
    >
      {stats}
      <ExternalLink
        size={14}
        aria-hidden="true"
      />
    </button>
  ) : (
    stats
  );

  return (
    <Box className="agent-change-summary-spacing">
      <Box
        asChild
        className="agent-change-summary-card"
      >
        <section aria-label={t("assistant.sessionChanges.turnSummary")}>
          <Flex
            align="center"
            gap="3"
            className="agent-change-summary-header"
            data-collapsible={hasMultipleItems ? "true" : undefined}
            data-expanded={isListVisible ? "true" : "false"}
            role={hasMultipleItems ? "button" : undefined}
            tabIndex={hasMultipleItems ? 0 : undefined}
            aria-expanded={hasMultipleItems ? isListVisible : undefined}
            onClick={hasMultipleItems ? handleHeaderClick : undefined}
            onKeyDown={hasMultipleItems ? handleHeaderKeyDown : undefined}
          >
            <span
              className="agent-change-summary-icon"
              aria-hidden="true"
            >
              <FileDiff size={17} />
            </span>
            <Box className="agent-change-summary-heading">
              <Flex
                align="center"
                gap="1"
                className="agent-change-summary-title-row"
              >
                <ChangeSummaryTitle
                  summary={summary}
                  className="agent-change-summary-title"
                />
                {hasMultipleItems ? (
                  <span
                    className="agent-change-summary-toggle"
                    aria-hidden="true"
                  >
                    {isListVisible ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                  </span>
                ) : null}
              </Flex>
              {onOpenChanges ? (
                <Tooltip content={t("assistant.sessionChanges.open")}>{statsRow}</Tooltip>
              ) : (
                statsRow
              )}
            </Box>
          </Flex>
          {hasMultipleItems && isListVisible ? (
            <Box className="agent-change-summary-list-wrap">
              <ul className="agent-change-summary-list">
                {visibleItems.map((item) => (
                  <li
                    key={getItemKey(item)}
                    className="agent-change-summary-item"
                  >
                    <ChangeKindIcon
                      item={item}
                      size={14}
                    />
                    <Box className="agent-change-summary-item-heading">
                      <Text
                        size="1"
                        className="agent-change-summary-item-title"
                      >
                        <ChangeItemName item={item} />
                      </Text>
                    </Box>
                    <ChangeStats
                      added={item.added}
                      removed={item.removed}
                    />
                  </li>
                ))}
              </ul>
              {remainingCount > 0 ? (
                <button
                  type="button"
                  className="agent-change-summary-more"
                  onClick={() => setIsItemsExpanded((value) => !value)}
                  aria-expanded={isItemsExpanded}
                >
                  {isItemsExpanded
                    ? t("assistant.sessionChanges.showLess")
                    : t("assistant.sessionChanges.showMore", { count: remainingCount })}
                </button>
              ) : null}
            </Box>
          ) : null}
        </section>
      </Box>
    </Box>
  );
}

export function AgentSessionChangesDialog({
  changes,
  summaryOverride,
  open,
  onOpenChange,
}: AgentSessionChangesDialogProps) {
  const { t } = useTranslation();
  const summary = summaryOverride ?? changes?.sessionChanges ?? EMPTY_CHANGE_SUMMARY;
  const [collapsedItemKeys, setCollapsedItemKeys] = useState<Set<string>>(() => new Set());
  const [isSplitView, setIsSplitView] = useState(false);
  const [isWrapEnabled, setIsWrapEnabled] = useState(false);
  const areItemsExpanded = summary.items.every((item) => !collapsedItemKeys.has(getItemKey(item)));
  const expandActionLabel = areItemsExpanded
    ? t("assistant.sessionChanges.collapseAll")
    : t("assistant.sessionChanges.expandAll");
  const viewActionLabel = isSplitView
    ? t("assistant.sessionChanges.unifiedView")
    : t("assistant.sessionChanges.splitView");
  const wrapActionLabel = isWrapEnabled
    ? t("assistant.sessionChanges.disableWrap")
    : t("assistant.sessionChanges.enableWrap");
  const handleToggleAll = () => {
    setCollapsedItemKeys(
      areItemsExpanded ? new Set(summary.items.map((item) => getItemKey(item))) : new Set(),
    );
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={onOpenChange}
    >
      <Dialog.Content
        className="agent-session-changes-dialog"
        maxWidth="none"
      >
        <Dialog.Title className="agent-session-changes-visually-hidden">
          {t("assistant.sessionChanges.overviewTitle")}
        </Dialog.Title>
        <Dialog.Description className="agent-session-changes-visually-hidden">
          {t("assistant.sessionChanges.dialogDescription")}
        </Dialog.Description>
        <Flex
          direction="column"
          className="agent-session-changes-view"
        >
          <Flex
            align="center"
            justify="between"
            className="agent-session-changes-header"
          >
            <Flex
              align="center"
              gap="2"
              className="agent-session-changes-header-leading"
            >
              <Dialog.Close>
                <IconButton
                  variant="ghost"
                  color="gray"
                  size="1"
                  aria-label={t("common.close")}
                >
                  <X size={16} />
                </IconButton>
              </Dialog.Close>
              <Text
                size="2"
                weight="medium"
                className="agent-session-changes-header-title"
              >
                {t("assistant.sessionChanges.overviewTitle")}
              </Text>
              <ChangeStats
                added={summary.added}
                removed={summary.removed}
              />
            </Flex>
            <Flex
              align="center"
              gap="1"
              className="agent-session-changes-actions"
            >
              <Tooltip content={expandActionLabel}>
                <IconButton
                  variant="ghost"
                  color="gray"
                  size="1"
                  aria-label={expandActionLabel}
                  aria-pressed={areItemsExpanded}
                  onClick={handleToggleAll}
                >
                  {areItemsExpanded ? <ChevronsDownUp size={16} /> : <ChevronsUpDown size={16} />}
                </IconButton>
              </Tooltip>
              <Tooltip content={viewActionLabel}>
                <IconButton
                  variant="ghost"
                  color="gray"
                  size="1"
                  aria-label={viewActionLabel}
                  aria-pressed={isSplitView}
                  onClick={() => setIsSplitView((split) => !split)}
                >
                  {isSplitView ? <Rows3 size={16} /> : <Columns2 size={16} />}
                </IconButton>
              </Tooltip>
              <Tooltip content={wrapActionLabel}>
                <IconButton
                  variant="ghost"
                  color="gray"
                  size="1"
                  aria-label={wrapActionLabel}
                  aria-pressed={isWrapEnabled}
                  onClick={() => setIsWrapEnabled((wrap) => !wrap)}
                >
                  {isWrapEnabled ? <TextAlignJustify size={16} /> : <WrapText size={16} />}
                </IconButton>
              </Tooltip>
            </Flex>
          </Flex>
          <Box className="agent-session-changes-content">
            {summary.items.length > 0 ? (
              <Box className="agent-session-changes-list">
                {summary.items.map((item) => (
                  <AgentChangeItemDiff
                    key={getItemKey(item)}
                    item={item}
                    isExpanded={!collapsedItemKeys.has(getItemKey(item))}
                    isSplitView={isSplitView}
                    isWrapEnabled={isWrapEnabled}
                    onToggle={() => {
                      setCollapsedItemKeys((current) => {
                        const next = new Set(current);
                        const key = getItemKey(item);
                        if (next.has(key)) next.delete(key);
                        else next.add(key);
                        return next;
                      });
                    }}
                  />
                ))}
              </Box>
            ) : (
              <Text
                size="2"
                className="agent-session-changes-empty"
              >
                {t("assistant.sessionChanges.noChanges")}
              </Text>
            )}
          </Box>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

import {
  AtSign,
  BookOpen,
  FileText,
  Image as ImageIcon,
  NotebookText,
  Package,
  Paperclip,
  ScrollText,
} from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, ReactNode, RefObject } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";
import type { AgentComposerItems, AssistantCommandCandidate } from "@/lib/command.types";
import type { AssistantMentionCandidate } from "@/lib/mention.types";

import "./agent-composer-add-menu.css";

type AgentComposerItem = AssistantCommandCandidate | AssistantMentionCandidate;
type AgentComposerTrigger = "/" | "@";
type AgentComposerMenuStatus = "loading" | "ready" | "error";
type AgentComposerReferenceAction = "image" | "file" | "skillTrigger" | "contentTrigger";

interface AgentComposerReferenceSelection {
  key: string;
  type: "reference";
  action: AgentComposerReferenceAction;
}

interface AgentComposerItemSelection {
  key: string;
  type: "item";
  item: AgentComposerItem;
}

type AgentComposerSelection = AgentComposerReferenceSelection | AgentComposerItemSelection;

const EMPTY_AGENT_COMPOSER_ITEMS: AgentComposerItems = {
  skills: [],
  chapters: [],
  notes: [],
  worldInfoEntries: [],
};

const REFERENCE_SELECTIONS: AgentComposerReferenceSelection[] = [
  { key: "reference-image", type: "reference", action: "image" },
  { key: "reference-file", type: "reference", action: "file" },
  { key: "reference-skill", type: "reference", action: "skillTrigger" },
  { key: "reference-content", type: "reference", action: "contentTrigger" },
];

interface AgentComposerAddMenuProps {
  clearanceHeight: number;
  visible: boolean;
  triggerRef: RefObject<HTMLButtonElement | null>;
  items: AgentComposerItems | null;
  status: AgentComposerMenuStatus;
  errorMessage: string;
  onClose: () => void;
  onPickFile: (kind: "image" | "file") => void;
  onInsertTrigger: (trigger: AgentComposerTrigger) => void;
  onSelectItem: (item: AgentComposerItem) => void;
}

function getMentionIcon(kind: AssistantMentionCandidate["kind"]): ReactNode {
  if (kind === "chapter") return <BookOpen size={14} />;
  if (kind === "note") return <NotebookText size={14} />;
  if (kind === "world_info_entry") return <ScrollText size={14} />;
  return <FileText size={14} />;
}

interface MenuSectionProps {
  title: string;
  children: ReactNode;
}

function MenuSection({ title, children }: MenuSectionProps) {
  return (
    <section className="agent-composer-add-section">
      <div className="agent-composer-add-list">
        <div className="agent-composer-add-header">{title}</div>
        {children}
      </div>
    </section>
  );
}

interface ReferenceActionProps {
  icon: ReactNode;
  label: string;
  selected: boolean;
  selectionIndex: number;
  onMouseEnter: (index: number) => void;
  onClick: () => void;
}

function ReferenceAction({
  icon,
  label,
  selected,
  selectionIndex,
  onMouseEnter,
  onClick,
}: ReferenceActionProps) {
  return (
    <button
      type="button"
      className="agent-composer-add-item"
      data-composer-add-index={selectionIndex}
      data-selected={selected}
      onMouseEnter={() => onMouseEnter(selectionIndex)}
      onClick={onClick}
    >
      <span
        className="agent-composer-add-item-icon"
        aria-hidden="true"
      >
        {icon}
      </span>
      <span className="agent-composer-add-item-copy">
        <span className="agent-composer-add-item-title">{label}</span>
      </span>
    </button>
  );
}

function getItemMeta(
  item: AgentComposerItem,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  if (item.kind === "skill") return item.description;

  const base =
    item.kind === "note"
      ? t("assistant.mentionKind.note")
      : item.kind === "world_info_entry"
        ? t("assistant.mentionKind.worldInfoEntry")
        : t("assistant.mentionKind.chapter");
  return item.description
    ? t("assistant.mentionMetaFormat", { base, description: item.description })
    : base;
}

interface ComposerItemListProps {
  items: AgentComposerItem[];
  t: (key: string, options?: Record<string, unknown>) => string;
  selectedIndex: number;
  getSelectionIndex: (item: AgentComposerItem) => number;
  onMouseEnter: (index: number) => void;
  onSelectItem: (item: AgentComposerItem) => void;
}

function ComposerItemList({
  items,
  t,
  selectedIndex,
  getSelectionIndex,
  onMouseEnter,
  onSelectItem,
}: ComposerItemListProps) {
  return (
    <>
      {items.map((item) => {
        const selectionIndex = getSelectionIndex(item);
        return (
          <button
            key={`${item.kind}-${item.id}`}
            type="button"
            className="agent-composer-add-item"
            data-composer-add-index={selectionIndex}
            data-selected={selectionIndex === selectedIndex}
            onMouseEnter={() => onMouseEnter(selectionIndex)}
            onClick={() => onSelectItem(item)}
          >
            <span
              className="agent-composer-add-item-icon"
              aria-hidden="true"
            >
              {item.kind === "skill" ? <Package size={14} /> : getMentionIcon(item.kind)}
            </span>
            <span
              className="agent-composer-add-item-copy"
              data-item-kind={item.kind}
            >
              <span className="agent-composer-add-item-title">
                {item.kind === "skill" ? item.name : item.title}
              </span>
              <span className="agent-composer-add-item-kind">{getItemMeta(item, t)}</span>
            </span>
          </button>
        );
      })}
    </>
  );
}

export function AgentComposerAddMenu({
  clearanceHeight,
  visible,
  triggerRef,
  items,
  status,
  errorMessage,
  onClose,
  onPickFile,
  onInsertTrigger,
  onSelectItem,
}: AgentComposerAddMenuProps) {
  const { t } = useTranslation();
  const panelRef = useRef<HTMLDivElement>(null);
  const normalizedClearanceHeight = Math.max(clearanceHeight, 0);
  const style = {
    "--agent-composer-add-clearance-height": `${normalizedClearanceHeight}px`,
  } as CSSProperties;
  const resolvedItems = items ?? EMPTY_AGENT_COMPOSER_ITEMS;
  const [selectedIndex, setSelectedIndex] = useState(0);
  const shouldScrollSelectionRef = useRef(false);
  const selectableItems = useMemo<AgentComposerSelection[]>(
    () => [
      ...REFERENCE_SELECTIONS,
      ...(status === "ready"
        ? [
            ...resolvedItems.skills,
            ...resolvedItems.chapters,
            ...resolvedItems.notes,
            ...resolvedItems.worldInfoEntries,
          ].map((item) => ({
            key: `${item.kind}-${item.id}`,
            type: "item" as const,
            item,
          }))
        : []),
    ],
    [
      resolvedItems.chapters,
      resolvedItems.notes,
      resolvedItems.skills,
      resolvedItems.worldInfoEntries,
      status,
    ],
  );
  const selectionIndexByKey = useMemo(
    () => new Map(selectableItems.map((selection, index) => [selection.key, index])),
    [selectableItems],
  );

  const getSelectionIndex = (item: AgentComposerItem) =>
    selectionIndexByKey.get(`${item.kind}-${item.id}`) ?? -1;

  const handleMouseEnter = useCallback((index: number) => {
    shouldScrollSelectionRef.current = false;
    setSelectedIndex(index);
  }, []);

  const handleActivate = useCallback(
    (selection: AgentComposerSelection) => {
      if (selection.type === "item") {
        onSelectItem(selection.item);
        return;
      }
      if (selection.action === "image" || selection.action === "file") {
        onPickFile(selection.action);
        return;
      }
      onInsertTrigger(selection.action === "skillTrigger" ? "/" : "@");
    },
    [onInsertTrigger, onPickFile, onSelectItem],
  );

  useEffect(() => {
    if (!visible) return;
    setSelectedIndex(0);
  }, [visible]);

  useEffect(() => {
    setSelectedIndex((current) => Math.min(current, Math.max(selectableItems.length - 1, 0)));
  }, [selectableItems.length]);

  useEffect(() => {
    if (!visible || !shouldScrollSelectionRef.current) return;
    const element = panelRef.current?.querySelector<HTMLElement>(
      `[data-composer-add-index="${selectedIndex}"]`,
    );
    element?.scrollIntoView({ block: "nearest" });
    shouldScrollSelectionRef.current = false;
  }, [selectedIndex, visible]);

  useEffect(() => {
    if (!visible) return undefined;

    const focusFrame = window.requestAnimationFrame(() => panelRef.current?.focus());

    const handleKeyDown = (event: KeyboardEvent) => {
      const hasSelectableItems = selectableItems.length > 0;
      switch (event.key) {
        case "ArrowDown":
          if (!hasSelectableItems) break;
          event.preventDefault();
          event.stopPropagation();
          shouldScrollSelectionRef.current = true;
          setSelectedIndex((current) => (current + 1) % selectableItems.length);
          break;
        case "ArrowUp":
          if (!hasSelectableItems) break;
          event.preventDefault();
          event.stopPropagation();
          shouldScrollSelectionRef.current = true;
          setSelectedIndex(
            (current) => (current - 1 + selectableItems.length) % selectableItems.length,
          );
          break;
        case "Enter":
        case "Tab":
          if (!hasSelectableItems || selectedIndex < 0 || !selectableItems[selectedIndex]) break;
          event.preventDefault();
          event.stopPropagation();
          handleActivate(selectableItems[selectedIndex]);
          break;
        case "Escape":
          event.preventDefault();
          event.stopPropagation();
          triggerRef.current?.focus();
          onClose();
          break;
      }
    };

    const handlePointerDown = (event: PointerEvent) => {
      if (!(event.target instanceof Node)) return;
      if (panelRef.current?.contains(event.target) || triggerRef.current?.contains(event.target)) {
        return;
      }
      onClose();
    };

    const handleFocusIn = (event: FocusEvent) => {
      if (!(event.target instanceof Node)) return;
      if (panelRef.current?.contains(event.target) || triggerRef.current?.contains(event.target)) {
        return;
      }
      onClose();
    };

    document.addEventListener("keydown", handleKeyDown, true);
    document.addEventListener("pointerdown", handlePointerDown, true);
    document.addEventListener("focusin", handleFocusIn, true);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      document.removeEventListener("keydown", handleKeyDown, true);
      document.removeEventListener("pointerdown", handlePointerDown, true);
      document.removeEventListener("focusin", handleFocusIn, true);
    };
  }, [handleActivate, onClose, selectableItems, selectedIndex, triggerRef, visible]);

  if (!visible) return null;

  return (
    <div
      className="agent-composer-add-shell"
      style={style}
    >
      <div className="agent-composer-add-card-stack">
        <div className="agent-composer-add-card">
          <motion.div
            ref={panelRef}
            className="agent-composer-add-card-body agent-composer-add-menu"
            tabIndex={-1}
            role="dialog"
            aria-label={t("assistant.composerMenu.open")}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
          >
            <MenuSection title={t("assistant.composerMenu.reference")}>
              <ReferenceAction
                icon={<ImageIcon size={14} />}
                label={t("assistant.composerMenu.image")}
                selected={selectedIndex === 0}
                selectionIndex={0}
                onMouseEnter={handleMouseEnter}
                onClick={() => onPickFile("image")}
              />
              <ReferenceAction
                icon={<Paperclip size={14} />}
                label={t("assistant.composerMenu.file")}
                selected={selectedIndex === 1}
                selectionIndex={1}
                onMouseEnter={handleMouseEnter}
                onClick={() => onPickFile("file")}
              />
              <ReferenceAction
                icon={<Package size={14} />}
                label={t("assistant.composerMenu.skillTrigger")}
                selected={selectedIndex === 2}
                selectionIndex={2}
                onMouseEnter={handleMouseEnter}
                onClick={() => onInsertTrigger("/")}
              />
              <ReferenceAction
                icon={<AtSign size={14} />}
                label={t("assistant.composerMenu.contentTrigger")}
                selected={selectedIndex === 3}
                selectionIndex={3}
                onMouseEnter={handleMouseEnter}
                onClick={() => onInsertTrigger("@")}
              />
            </MenuSection>

            {status === "loading" ? (
              <div
                className="agent-composer-add-state"
                role="status"
              >
                <Spinner size={12} />
                <span>{t("common.loading")}</span>
              </div>
            ) : status === "error" ? (
              <div
                className="agent-composer-add-state agent-composer-add-state--error"
                role="alert"
              >
                {errorMessage}
              </div>
            ) : (
              <>
                {resolvedItems.skills.length > 0 ? (
                  <MenuSection title={t("assistant.composerMenu.skills")}>
                    <ComposerItemList
                      items={resolvedItems.skills}
                      t={t}
                      selectedIndex={selectedIndex}
                      getSelectionIndex={getSelectionIndex}
                      onMouseEnter={handleMouseEnter}
                      onSelectItem={onSelectItem}
                    />
                  </MenuSection>
                ) : null}
                {resolvedItems.chapters.length > 0 ? (
                  <MenuSection title={t("assistant.composerMenu.chapters")}>
                    <ComposerItemList
                      items={resolvedItems.chapters}
                      t={t}
                      selectedIndex={selectedIndex}
                      getSelectionIndex={getSelectionIndex}
                      onMouseEnter={handleMouseEnter}
                      onSelectItem={onSelectItem}
                    />
                  </MenuSection>
                ) : null}
                {resolvedItems.notes.length > 0 ? (
                  <MenuSection title={t("assistant.composerMenu.notes")}>
                    <ComposerItemList
                      items={resolvedItems.notes}
                      t={t}
                      selectedIndex={selectedIndex}
                      getSelectionIndex={getSelectionIndex}
                      onMouseEnter={handleMouseEnter}
                      onSelectItem={onSelectItem}
                    />
                  </MenuSection>
                ) : null}
                {resolvedItems.worldInfoEntries.length > 0 ? (
                  <MenuSection title={t("assistant.composerMenu.worldInfoEntries")}>
                    <ComposerItemList
                      items={resolvedItems.worldInfoEntries}
                      t={t}
                      selectedIndex={selectedIndex}
                      getSelectionIndex={getSelectionIndex}
                      onMouseEnter={handleMouseEnter}
                      onSelectItem={onSelectItem}
                    />
                  </MenuSection>
                ) : null}
              </>
            )}
          </motion.div>
          <div
            aria-hidden="true"
            className="agent-composer-add-card-clearance"
          />
        </div>
      </div>
    </div>
  );
}

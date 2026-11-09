import {
  closestCenter,
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { restrictToFirstScrollableAncestor, restrictToHorizontalAxis } from "@dnd-kit/modifiers";
import {
  horizontalListSortingStrategy,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import { Tooltip } from "@radix-ui/themes";
import {
  BookOpen,
  Bot,
  FileText,
  PanelRightClose,
  Plus,
  UserRound,
  X,
  XCircle,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type MouseEvent,
} from "react";
import { useTranslation } from "react-i18next";

import { ContextMenu, SimpleSelect, type ContextMenuItem } from "@/components";

import type { SidebarEntityKind } from "./right-sidebar-entity-editor";

export interface SidebarTab {
  id: string;
  kind: "agent" | SidebarEntityKind;
  entityId?: string;
  title: string;
}

interface RightSidebarTabsProps {
  tabs: SidebarTab[];
  activeId: string;
  prefix: string;
  runningTabIds: string[];
  onActivate: (tab: SidebarTab) => void;
  onClose: (ids: string[]) => void;
  onReorder: (activeId: string, overId: string) => void;
  onNewAgent: () => void;
  onSelectKind: (kind: SidebarEntityKind) => void;
  onCollapse: () => void;
}

const TAB_ICONS = {
  agent: Bot,
  chapter: FileText,
  character: UserRound,
  world_info_entry: BookOpen,
};
const ENTITY_KINDS: SidebarEntityKind[] = ["chapter", "character", "world_info_entry"];

export function RightSidebarTabs(props: RightSidebarTabsProps) {
  const { t } = useTranslation();
  const listRef = useRef<HTMLDivElement>(null);
  const [draggedTab, setDraggedTab] = useState<SidebarTab | null>(null);
  const [contextMenu, setContextMenu] = useState<{ tabId: string; x: number; y: number } | null>(
    null,
  );
  const handleCloseContextMenu = useCallback(() => setContextMenu(null), []);
  const DragIcon = draggedTab ? TAB_ICONS[draggedTab.kind] : null;
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const targetTab = props.tabs.find((tab) => tab.id === contextMenu?.tabId);
  const closableIds = props.tabs
    .filter((tab) => !props.runningTabIds.includes(tab.id))
    .map((tab) => tab.id);
  const otherIds = closableIds.filter((id) => id !== targetTab?.id);
  const rightIds = targetTab
    ? props.tabs
        .slice(props.tabs.indexOf(targetTab) + 1)
        .filter((tab) => !props.runningTabIds.includes(tab.id))
        .map((tab) => tab.id)
    : [];
  const contextMenuItems: ContextMenuItem[] = targetTab
    ? [
        {
          id: "close",
          label: t("tabs.close"),
          icon: X,
          disabled: props.runningTabIds.includes(targetTab.id),
          onClick: () => props.onClose([targetTab.id]),
        },
        {
          id: "closeOthers",
          label: t("tabs.closeOthers"),
          icon: XCircle,
          disabled: otherIds.length === 0,
          onClick: () => props.onClose(otherIds),
        },
        {
          id: "closeRight",
          label: t("rightSidebar.closeRight"),
          icon: XCircle,
          disabled: rightIds.length === 0,
          onClick: () => props.onClose(rightIds),
        },
        {
          id: "closeAll",
          label: t("tabs.closeAll"),
          icon: XCircle,
          disabled: closableIds.length === 0,
          onClick: () => props.onClose(closableIds),
        },
      ]
    : [];

  useEffect(() => {
    listRef.current
      ?.querySelector('[aria-selected="true"]')
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [props.activeId]);

  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const updateOverflow = () => {
      list.toggleAttribute("data-overflow-left", list.scrollLeft > 1);
      list.toggleAttribute(
        "data-overflow-right",
        list.scrollLeft < list.scrollWidth - list.clientWidth - 1,
      );
    };
    const observer = new ResizeObserver(updateOverflow);
    observer.observe(list);
    for (const tab of list.children) observer.observe(tab);
    list.addEventListener("scroll", updateOverflow, { passive: true });
    updateOverflow();
    return () => {
      observer.disconnect();
      list.removeEventListener("scroll", updateOverflow);
    };
  }, [props.tabs]);

  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const handleWheel = (event: WheelEvent) => {
      if (event.ctrlKey || list.scrollWidth <= list.clientWidth) return;
      const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
      const scale = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? list.clientWidth : 1;
      event.preventDefault();
      list.scrollLeft += delta * scale;
    };
    list.addEventListener("wheel", handleWheel, { passive: false });
    return () => list.removeEventListener("wheel", handleWheel);
  }, []);

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let nextIndex: number;
    if (event.key === "ArrowRight") nextIndex = (index + 1) % props.tabs.length;
    else if (event.key === "ArrowLeft")
      nextIndex = (index + props.tabs.length - 1) % props.tabs.length;
    else if (event.key === "Home") nextIndex = 0;
    else if (event.key === "End") nextIndex = props.tabs.length - 1;
    else if (event.key === "Delete") {
      event.preventDefault();
      props.onClose([props.tabs[index].id]);
      return;
    } else return;
    event.preventDefault();
    const tab = props.tabs[nextIndex];
    props.onActivate(tab);
    document.getElementById(`${props.prefix}-tab-${tab.id}`)?.focus();
  }

  return (
    <div
      className="right-sidebar-toolbar"
      data-dragging={draggedTab !== null}
    >
      <div className="right-sidebar-tab-strip">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          modifiers={[restrictToHorizontalAxis, restrictToFirstScrollableAncestor]}
          onDragStart={({ active }) =>
            setDraggedTab(props.tabs.find((tab) => tab.id === active.id) ?? null)
          }
          onDragCancel={() => setDraggedTab(null)}
          onDragEnd={({ active, over }) => {
            if (over && active.id !== over.id) props.onReorder(String(active.id), String(over.id));
            setDraggedTab(null);
          }}
        >
          <div
            ref={listRef}
            className="right-sidebar-tabs"
            role="tablist"
            aria-label={t("rightSidebar.tabs")}
          >
            <SortableContext
              items={props.tabs.map((tab) => tab.id)}
              strategy={horizontalListSortingStrategy}
            >
              {props.tabs.map((tab, index) => (
                <SortableSidebarTab
                  key={tab.id}
                  tab={tab}
                  index={index}
                  {...props}
                  onNavigate={handleTabKeyDown}
                  onContextMenu={(event) => {
                    event.preventDefault();
                    setContextMenu({ tabId: tab.id, x: event.clientX, y: event.clientY });
                  }}
                />
              ))}
            </SortableContext>
          </div>
          <DragOverlay
            dropAnimation={{ duration: 180, easing: "ease-out" }}
            zIndex={70}
          >
            {draggedTab && DragIcon && (
              <div
                className="right-sidebar-tab right-sidebar-tab-overlay"
                data-active={props.activeId === draggedTab.id}
                aria-hidden="true"
              >
                <span className="right-sidebar-tab-select">
                  <DragIcon size={14} />
                  <span className="right-sidebar-tab-title">
                    {draggedTab.title || t(`rightSidebar.${draggedTab.kind}`)}
                  </span>
                  {props.runningTabIds.includes(draggedTab.id) && (
                    <span className="right-sidebar-running" />
                  )}
                </span>
                <span className="right-sidebar-tab-close">
                  <X size={12} />
                </span>
              </div>
            )}
          </DragOverlay>
        </DndContext>
        <SimpleSelect
          value="new-tab"
          options={[
            {
              value: "agent",
              label: t("rightSidebar.agent"),
              prefix: <Bot size={14} />,
            },
            ...ENTITY_KINDS.map((kind) => {
              const Icon = TAB_ICONS[kind];
              return {
                value: kind,
                label: t(
                  `assistant.mentionKind.${kind === "world_info_entry" ? "worldInfoEntry" : kind}`,
                ),
                prefix: <Icon size={14} />,
              };
            }),
          ]}
          onChange={(value) => {
            if (value === "agent") props.onNewAgent();
            else if (ENTITY_KINDS.includes(value as SidebarEntityKind))
              props.onSelectKind(value as SidebarEntityKind);
          }}
          variant="icon"
          triggerPrefix={<Plus size={16} />}
          triggerClassName="right-sidebar-new-tab-trigger"
          triggerAriaLabel={t("rightSidebar.newTab")}
          size="1"
        />
      </div>
      <Tooltip content={t("rightSidebar.collapse")}>
        <button
          type="button"
          className="right-sidebar-toolbar-button"
          aria-label={t("rightSidebar.collapse")}
          onClick={props.onCollapse}
        >
          <PanelRightClose size={15} />
        </button>
      </Tooltip>
      <ContextMenu
        position={contextMenu}
        items={contextMenuItems}
        onClose={handleCloseContextMenu}
      />
    </div>
  );
}

interface SortableSidebarTabProps extends RightSidebarTabsProps {
  tab: SidebarTab;
  index: number;
  onNavigate: (event: KeyboardEvent<HTMLButtonElement>, index: number) => void;
  onContextMenu: (event: MouseEvent<HTMLDivElement>) => void;
}

function SortableSidebarTab({
  tab,
  index,
  prefix,
  activeId,
  runningTabIds,
  onActivate,
  onClose,
  onNavigate,
  onContextMenu,
}: SortableSidebarTabProps) {
  const { t } = useTranslation();
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
    isSorting,
  } = useSortable({ id: tab.id });
  const title = tab.title || t(`rightSidebar.${tab.kind}`);
  const Icon = TAB_ICONS[tab.kind];
  const isRunning = runningTabIds.includes(tab.id);

  return (
    <div
      ref={setNodeRef}
      className="right-sidebar-tab"
      data-active={activeId === tab.id}
      data-dragging={isDragging}
      onContextMenu={onContextMenu}
      style={{
        transform: transform ? `translate3d(${transform.x}px, 0, 0)` : undefined,
        transition,
      }}
      onMouseDown={(event) => {
        if (event.button === 1) event.preventDefault();
      }}
      onAuxClick={(event) => {
        if (event.button === 1) {
          event.preventDefault();
          onClose([tab.id]);
        }
      }}
    >
      <button
        ref={setActivatorNodeRef}
        {...attributes}
        {...listeners}
        type="button"
        role="tab"
        id={`${prefix}-tab-${tab.id}`}
        aria-controls={`${prefix}-panel-${tab.id}`}
        aria-selected={activeId === tab.id}
        tabIndex={activeId === tab.id ? 0 : -1}
        title={title}
        className="right-sidebar-tab-select"
        onClick={() => onActivate(tab)}
        onKeyDown={(event) => {
          listeners?.onKeyDown?.(event);
          if (!isSorting && event.code !== "Space") onNavigate(event, index);
        }}
      >
        <Icon
          size={14}
          aria-hidden="true"
        />
        <span className="right-sidebar-tab-title">{title}</span>
        {isRunning && <span className="right-sidebar-running" />}
      </button>
      <button
        type="button"
        className="right-sidebar-tab-close"
        aria-label={t("rightSidebar.closeTab", { title })}
        disabled={isRunning}
        title={isRunning ? t("rightSidebar.runningTab") : t("common.close")}
        onPointerDown={(event) => event.stopPropagation()}
        onClick={() => onClose([tab.id])}
      >
        <X size={12} />
      </button>
    </div>
  );
}

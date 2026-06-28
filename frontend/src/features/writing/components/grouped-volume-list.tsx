import {
  forwardRef,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ForwardedRef,
} from "react";
import { Box, Text } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import {
  restrictToParentElement,
  restrictToVerticalAxis,
} from "@dnd-kit/modifiers";
import {
  GroupedVirtuoso,
  type GroupedVirtuosoHandle,
  type ScrollerProps,
} from "react-virtuoso";
import { useShallow } from "zustand/react/shallow";
import { AtSign, Copy, ExternalLink, MoveRight, Pencil, Trash2 } from "lucide-react";

import "./grouped-volume-list.css";
import { ChapterListItem, SortableChapterListItem } from "./chapter-list-item";
import { VolumeHeader } from "./volume-header";
import {
  resolveInitialCurrentChapterNavigation,
  resolveGroupedVolumeListScrollRequest,
  type GroupedVolumeListScrollRequest,
  type GroupedVolumeListScrollTarget,
} from "./grouped-volume-list-focus";
import {
  type BottomAnchoredScrollAdjustment,
  getBottomAnchoredScrollAdjustmentForShrink,
  type GroupedVolumeListViewportMetrics,
} from "./grouped-volume-list-scroll";
import {
  buildGroupedVolumeListModel,
  getCollapseScrollGroupIndex,
  getGroupedVolumeListStructureSignature,
  getSortedVolumeChapters,
  shouldAnchorCollapsedGroupScroll,
  type GroupedVolumeListItem,
} from "./grouped-volume-list-model";
import { ContextMenu, type ContextMenuItem } from "@/components";
import { buildChapterMentionTag } from "@/features/assistant/lib/mention-text";
import { useWritingStore } from "../store/use-writing-store";
import type { ChapterListItem as ChapterListItemData, VolumeWithChapters } from "@/lib/chapter.types";
import type { SummaryStatusItem } from "@/lib/api-client";

const SCROLLBAR_HIDE_DELAY = 5000;
const SCROLLBAR_HOT_ZONE_WIDTH = 20;
const SCROLLBAR_MIN_THUMB_HEIGHT = 28;
const SCROLLBAR_REFRESH_EVENT = "grouped-volume-list-scrollbar-refresh";
const EMPTY_DRAG_ORDER_MAP: Readonly<Record<string, number>> = Object.freeze({});
const VIRTUOSO_FALLBACK_MEASURE_HEIGHT = 1;

function assignForwardedRef<T>(ref: ForwardedRef<T>, value: T | null) {
  if (typeof ref === "function") {
    ref(value);
    return;
  }
  if (ref) {
    ref.current = value;
  }
}

const GroupedVolumeListScroller = forwardRef<HTMLDivElement, ScrollerProps>(
  function GroupedVolumeListScroller({ children, style, ...props }, forwardedRef) {
    const scrollerRef = useRef<HTMLDivElement | null>(null);
    const thumbRef = useRef<HTMLDivElement | null>(null);

    const setScrollerRef = useCallback(
      (node: HTMLDivElement | null) => {
        scrollerRef.current = node;
        assignForwardedRef(forwardedRef, node);
      },
      [forwardedRef]
    );

    useEffect(() => {
      const scroller = scrollerRef.current;
      const thumb = thumbRef.current;
      if (!scroller || !thumb) {
        return;
      }

      let hideTimer: ReturnType<typeof setTimeout> | null = null;
      let animationFrame: number | null = null;
      let isHoveringScrollbarZone = false;
      let dragState: {
        startY: number;
        startScrollTop: number;
        maxScrollTop: number;
        trackTravel: number;
      } | null = null;

      const clearHideTimer = () => {
        if (hideTimer) {
          clearTimeout(hideTimer);
          hideTimer = null;
        }
      };

      const updateThumb = () => {
        const maxScrollTop = scroller.scrollHeight - scroller.clientHeight;
        if (scroller.clientHeight <= 0 || maxScrollTop <= 1) {
          thumb.classList.remove("is-scrollable", "is-visible");
          thumb.style.height = "0px";
          thumb.style.transform = "translate3d(0, 0, 0)";
          return;
        }

        const thumbHeight = Math.max(
          SCROLLBAR_MIN_THUMB_HEIGHT,
          Math.round((scroller.clientHeight / scroller.scrollHeight) * scroller.clientHeight)
        );
        const trackTravel = Math.max(1, scroller.clientHeight - thumbHeight);
        const thumbTop = (scroller.scrollTop / maxScrollTop) * trackTravel;

        thumb.classList.add("is-scrollable");
        thumb.style.height = `${thumbHeight}px`;
        thumb.style.transform = `translate3d(0, ${scroller.scrollTop + thumbTop}px, 0)`;
      };

      const scheduleThumbUpdate = () => {
        if (animationFrame !== null) {
          return;
        }
        animationFrame = window.requestAnimationFrame(() => {
          animationFrame = null;
          updateThumb();
        });
      };

      const observeMeasuredElements = () => {
        const measuredElements = scroller.querySelectorAll(
          '[data-testid="virtuoso-item-list"], [data-testid="virtuoso-top-item-list"], [data-viewport-type]'
        );
        measuredElements.forEach((element) => resizeObserver.observe(element));
      };

      const showScrollbar = () => {
        thumb.classList.add("is-visible");
        scheduleThumbUpdate();
      };

      const scheduleHideScrollbar = () => {
        clearHideTimer();
        hideTimer = setTimeout(() => {
          if (!isHoveringScrollbarZone && !dragState) {
            thumb.classList.remove("is-visible");
          }
        }, SCROLLBAR_HIDE_DELAY);
      };

      const handleScroll = () => {
        showScrollbar();
        scheduleHideScrollbar();
      };

      const handleScrollbarRefresh = () => {
        observeMeasuredElements();
        updateThumb();
        scheduleThumbUpdate();
      };

      const handleMouseMove = (event: MouseEvent) => {
        const rect = scroller.getBoundingClientRect();
        const isInScrollbarZone = event.clientX >= rect.right - SCROLLBAR_HOT_ZONE_WIDTH;

        if (isInScrollbarZone) {
          isHoveringScrollbarZone = true;
          showScrollbar();
          clearHideTimer();
          return;
        }

        if (isHoveringScrollbarZone) {
          isHoveringScrollbarZone = false;
          scheduleHideScrollbar();
        }
      };

      const handleMouseLeave = () => {
        isHoveringScrollbarZone = false;
        scheduleHideScrollbar();
      };

      const handlePointerDown = (event: PointerEvent) => {
        if (!thumb.classList.contains("is-scrollable")) {
          return;
        }

        event.preventDefault();
        const maxScrollTop = scroller.scrollHeight - scroller.clientHeight;
        dragState = {
          startY: event.clientY,
          startScrollTop: scroller.scrollTop,
          maxScrollTop,
          trackTravel: Math.max(1, scroller.clientHeight - thumb.offsetHeight),
        };
        thumb.setPointerCapture(event.pointerId);
        showScrollbar();
        clearHideTimer();
      };

      const handlePointerMove = (event: PointerEvent) => {
        if (!dragState) {
          return;
        }

        event.preventDefault();
        const scrollDelta =
          ((event.clientY - dragState.startY) / dragState.trackTravel) *
          dragState.maxScrollTop;
        scroller.scrollTop = Math.min(
          dragState.maxScrollTop,
          Math.max(0, dragState.startScrollTop + scrollDelta)
        );
        showScrollbar();
      };

      const handlePointerUp = (event: PointerEvent) => {
        if (!dragState) {
          return;
        }

        dragState = null;
        if (thumb.hasPointerCapture(event.pointerId)) {
          thumb.releasePointerCapture(event.pointerId);
        }
        scheduleHideScrollbar();
      };

      const resizeObserver = new ResizeObserver(scheduleThumbUpdate);
      resizeObserver.observe(scroller);
      const mutationObserver = new MutationObserver((mutations) => {
        if (mutations.every((mutation) => mutation.target === thumb)) {
          return;
        }
        handleScrollbarRefresh();
      });
      mutationObserver.observe(scroller, {
        attributes: true,
        attributeFilter: ["style", "class"],
        childList: true,
        subtree: true,
      });
      observeMeasuredElements();

      updateThumb();
      scroller.addEventListener("scroll", handleScroll, { passive: true });
      scroller.addEventListener(SCROLLBAR_REFRESH_EVENT, handleScrollbarRefresh);
      scroller.addEventListener("mousemove", handleMouseMove);
      scroller.addEventListener("mouseleave", handleMouseLeave);
      thumb.addEventListener("pointerdown", handlePointerDown);
      thumb.addEventListener("pointermove", handlePointerMove);
      thumb.addEventListener("pointerup", handlePointerUp);
      thumb.addEventListener("pointercancel", handlePointerUp);

      return () => {
        clearHideTimer();
        if (animationFrame !== null) {
          window.cancelAnimationFrame(animationFrame);
        }
        mutationObserver.disconnect();
        resizeObserver.disconnect();
        scroller.removeEventListener("scroll", handleScroll);
        scroller.removeEventListener(SCROLLBAR_REFRESH_EVENT, handleScrollbarRefresh);
        scroller.removeEventListener("mousemove", handleMouseMove);
        scroller.removeEventListener("mouseleave", handleMouseLeave);
        thumb.removeEventListener("pointerdown", handlePointerDown);
        thumb.removeEventListener("pointermove", handlePointerMove);
        thumb.removeEventListener("pointerup", handlePointerUp);
        thumb.removeEventListener("pointercancel", handlePointerUp);
      };
    }, []);

    return (
      <div
        {...props}
        ref={setScrollerRef}
        className="grouped-volume-list-scroller"
        style={style}
      >
        {children}
        <div ref={thumbRef} className="grouped-volume-list-scrollbar-thumb" />
      </div>
    );
  }
);

const GROUPED_VOLUME_LIST_COMPONENTS = {
  Scroller: GroupedVolumeListScroller,
};

function VirtuosoFallbackMeasuredItem() {
  return (
    <Box
      aria-hidden="true"
      style={{
        minHeight: VIRTUOSO_FALLBACK_MEASURE_HEIGHT,
        visibility: "hidden",
      }}
    />
  );
}

interface GroupedVolumeListProps {
  projectId: string;
  volumes: VolumeWithChapters[];
  scrollRequest?: GroupedVolumeListScrollRequest | null;
  expandedVolumeIds: Set<string>;
  renamingVolumeId: string | null;
  isAgentLocked?: boolean;
  compact?: boolean;
  initialCurrentChapterNavigationKey?: string | null;
  summaryStatusMap?: Record<string, SummaryStatusItem>;
  onToggleVolume: (volumeId: string) => void;
  onStartRenameVolume: (volumeId: string) => void;
  onRenameVolume: (volumeId: string, title: string) => void;
  onCancelRenameVolume: () => void;
  onEditVolumeDescription: (volume: VolumeWithChapters) => void;
  onCreateChapterInVolume: (volumeId: string) => void;
  onMoveVolumeUp: (volume: VolumeWithChapters) => void;
  onMoveVolumeDown: (volume: VolumeWithChapters) => void;
  onDeleteVolume: (volume: VolumeWithChapters) => void;
  onChapterSelect: (chapterId: string) => void;
  onOpenInNewTab: (chapterId: string, title: string) => void;
  onDuplicate: (chapterId: string, title: string) => void;
  onRenameChapter: (chapterId: string, title: string) => void;
  onMoveChapterToVolume: (chapter: ChapterListItemData) => void;
  onDeleteChapter: (chapter: ChapterListItemData) => void;
  onAddToConversation?: (markup: string) => void;
  onLockedAction?: () => void;
}

export function GroupedVolumeList({
  projectId,
  volumes,
  scrollRequest = null,
  expandedVolumeIds,
  renamingVolumeId,
  isAgentLocked = false,
  compact = false,
  initialCurrentChapterNavigationKey = null,
  summaryStatusMap = {},
  onToggleVolume,
  onStartRenameVolume,
  onRenameVolume,
  onCancelRenameVolume,
  onEditVolumeDescription,
  onCreateChapterInVolume,
  onMoveVolumeUp,
  onMoveVolumeDown,
  onDeleteVolume,
  onChapterSelect,
  onOpenInNewTab,
  onDuplicate,
  onRenameChapter,
  onMoveChapterToVolume,
  onDeleteChapter,
  onAddToConversation,
  onLockedAction,
}: GroupedVolumeListProps) {
  const { t } = useTranslation();
  const { currentChapterId, isDragMode, dragOrderMap, reorderChapters } = useWritingStore(
    useShallow((state) => ({
      currentChapterId: state.currentChapterId,
      isDragMode: state.isDragMode,
      dragOrderMap: state.isDragMode ? state.dragOrderMap : EMPTY_DRAG_ORDER_MAP,
      reorderChapters: state.reorderChapters,
    }))
  );

  const virtuosoRef = useRef<GroupedVirtuosoHandle>(null);
  const scrollerElementRef = useRef<HTMLElement | null>(null);
  const pendingCollapseScrollGroupIndexRef = useRef<number | null>(null);
  const isAtBottomRef = useRef(false);
  const previousViewportMetricsRef = useRef<GroupedVolumeListViewportMetrics | null>(null);
  const lastHandledScrollRequestKeyRef = useRef<string | null>(null);
  const lastAutoScrolledChapterKeyRef = useRef<string | null>(null);
  const lastHandledInitialCurrentChapterNavigationKeyRef = useRef<string | null>(null);
  const [measuredProjectId, setMeasuredProjectId] = useState<string | null>(null);
  const [contextMenuPos, setContextMenuPos] = useState<{ x: number; y: number } | null>(null);
  const [contextMenuChapterId, setContextMenuChapterId] = useState<string | null>(null);
  const [contextMenuChapterTitle, setContextMenuChapterTitle] = useState<string | null>(null);
  const [renamingChapterId, setRenamingChapterId] = useState<string | null>(null);

  const listModel = useMemo(
    () => buildGroupedVolumeListModel({ volumes, expandedVolumeIds }),
    [expandedVolumeIds, volumes]
  );
  const structureSignature = useMemo(
    () => getGroupedVolumeListStructureSignature(volumes, expandedVolumeIds),
    [expandedVolumeIds, volumes]
  );
  const viewportMetrics = useMemo<GroupedVolumeListViewportMetrics>(
    () => ({
      groupCount: volumes.length,
      itemCount: listModel.items.length,
      visibleRowCount: volumes.length + listModel.items.length,
    }),
    [listModel.items.length, volumes.length]
  );
  const groupCountsSignature = listModel.groupCounts.join(",");
  const previousStructureSignatureRef = useRef<string | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleScrollerRef = useCallback((ref: HTMLElement | Window | null) => {
    scrollerElementRef.current = ref instanceof HTMLElement ? ref : null;
  }, []);

  const refreshScrollbar = useCallback(() => {
    const scroller = scrollerElementRef.current;
    if (!scroller) {
      return;
    }

    scroller.dispatchEvent(new Event(SCROLLBAR_REFRESH_EVENT));
    window.requestAnimationFrame(() => {
      scroller.dispatchEvent(new Event(SCROLLBAR_REFRESH_EVENT));
    });
  }, []);

  const handleAtBottomStateChange = useCallback((atBottom: boolean) => {
    isAtBottomRef.current = atBottom;
  }, []);

  const markListMeasured = useCallback(() => {
    refreshScrollbar();
    setMeasuredProjectId((current) => (current === projectId ? current : projectId));
  }, [projectId, refreshScrollbar]);

  const applyScrollTarget = useCallback(
    (target: GroupedVolumeListScrollTarget | BottomAnchoredScrollAdjustment) => {
      if (target.type === "chapter") {
        const align = "align" in target ? target.align : "end";
        const behavior = "behavior" in target ? target.behavior : "auto";
        virtuosoRef.current?.scrollToIndex({
          index: target.index,
          align,
          behavior,
        });
        return;
      }

      if (target.type === "group") {
        const align = "align" in target ? target.align : "end";
        const behavior = "behavior" in target ? target.behavior : "auto";
        virtuosoRef.current?.scrollToIndex({
          groupIndex: target.groupIndex,
          align,
          behavior,
        });
        return;
      }

      virtuosoRef.current?.scrollTo({ top: 0, behavior: "auto" });
      if (scrollerElementRef.current) {
        scrollerElementRef.current.scrollTop = 0;
      }
    },
    []
  );

  const getStickyGroupIndex = useCallback(() => {
    const stickyGroup = scrollerElementRef.current?.querySelector<HTMLElement>(
      '[data-testid="virtuoso-top-item-list"] [data-item-index]'
    );
    const rawIndex = stickyGroup?.dataset.itemIndex;
    if (!rawIndex) {
      return undefined;
    }

    const index = Number.parseInt(rawIndex, 10);
    return Number.isNaN(index) ? undefined : index;
  }, []);

  const getRegularGroupTop = useCallback((groupIndex: number) => {
    return scrollerElementRef.current
      ?.querySelector<HTMLElement>(
        `[data-testid="virtuoso-item-list"] [data-item-index="${groupIndex}"]:not([data-item-group-index])`
      )
      ?.getBoundingClientRect().top;
  }, []);

  const scrollCollapsedGroupIntoView = useCallback((groupIndex: number) => {
    if (groupIndex <= 0) {
      virtuosoRef.current?.scrollTo({ top: 0, behavior: "auto" });
      if (scrollerElementRef.current) {
        scrollerElementRef.current.scrollTop = 0;
      }
      return true;
    }

    const scroller = scrollerElementRef.current;
    const groupElement = scroller?.querySelector<HTMLElement>(
      `[data-testid="virtuoso-item-list"] [data-item-index="${groupIndex}"]:not([data-item-group-index])`
    );

    if (scroller && groupElement) {
      const scrollerRect = scroller.getBoundingClientRect();
      const groupRect = groupElement.getBoundingClientRect();
      scroller.scrollTo({
        top: Math.max(0, scroller.scrollTop + groupRect.top - scrollerRect.top),
        behavior: "auto",
      });
      return true;
    }

    return false;
  }, []);

  const currentChapterScrollKey = useMemo(() => {
    if (!projectId || !currentChapterId) {
      return null;
    }

    return `${projectId}:${currentChapterId}`;
  }, [currentChapterId, projectId]);

  useEffect(() => {
    if (measuredProjectId !== projectId) {
      return;
    }

    if (!currentChapterScrollKey || !initialCurrentChapterNavigationKey) {
      return;
    }

    if (
      lastHandledInitialCurrentChapterNavigationKeyRef.current ===
      initialCurrentChapterNavigationKey
    ) {
      return;
    }

    if (
      scrollRequest?.type === "chapter" &&
      scrollRequest.chapterId === currentChapterId &&
      lastHandledScrollRequestKeyRef.current !== scrollRequest.key
    ) {
      return;
    }

    const navigation = resolveInitialCurrentChapterNavigation({
      initialNavigationKey: initialCurrentChapterNavigationKey,
      volumes,
      expandedVolumeIds,
      currentChapterId,
      getChapterScrollIndex: listModel.getChapterScrollIndex,
    });

    if (!navigation || navigation.type === "expand-volume") {
      return;
    }

    const frameIds: number[] = [];
    frameIds.push(
      window.requestAnimationFrame(() => {
        applyScrollTarget(navigation);
        refreshScrollbar();
        frameIds.push(window.requestAnimationFrame(refreshScrollbar));
        lastAutoScrolledChapterKeyRef.current = currentChapterScrollKey;
        lastHandledInitialCurrentChapterNavigationKeyRef.current =
          initialCurrentChapterNavigationKey;
      })
    );

    return () => {
      for (const frameId of frameIds) {
        window.cancelAnimationFrame(frameId);
      }
    };
  }, [
    applyScrollTarget,
    currentChapterId,
    currentChapterScrollKey,
    expandedVolumeIds,
    initialCurrentChapterNavigationKey,
    listModel,
    measuredProjectId,
    projectId,
    refreshScrollbar,
    scrollRequest,
    volumes,
  ]);

  useLayoutEffect(() => {
    if (measuredProjectId !== projectId) {
      return;
    }

    if (!scrollRequest || lastHandledScrollRequestKeyRef.current === scrollRequest.key) {
      return;
    }

    const target = resolveGroupedVolumeListScrollRequest({
      request: scrollRequest,
      volumes,
      getChapterScrollIndex: listModel.getChapterScrollIndex,
    });
    if (!target) {
      return;
    }

    const frameIds: number[] = [];
    frameIds.push(
      window.requestAnimationFrame(() => {
        applyScrollTarget(target);
        refreshScrollbar();
        frameIds.push(window.requestAnimationFrame(refreshScrollbar));
        lastHandledScrollRequestKeyRef.current = scrollRequest.key;
        if (scrollRequest.type === "chapter" && currentChapterScrollKey) {
          lastAutoScrolledChapterKeyRef.current = currentChapterScrollKey;
        }
      })
    );

    return () => {
      for (const frameId of frameIds) {
        window.cancelAnimationFrame(frameId);
      }
    };
  }, [
    applyScrollTarget,
    currentChapterScrollKey,
    listModel,
    measuredProjectId,
    projectId,
    refreshScrollbar,
    scrollRequest,
    volumes,
  ]);

  useLayoutEffect(() => {
    const previousSignature = previousStructureSignatureRef.current;
    const previousViewportMetrics = previousViewportMetricsRef.current;
    previousStructureSignatureRef.current = structureSignature;
    previousViewportMetricsRef.current = viewportMetrics;

    if (!previousSignature || previousSignature === structureSignature) {
      return;
    }

    refreshScrollbar();
    const adjustment = getBottomAnchoredScrollAdjustmentForShrink({
      previousMetrics: previousViewportMetrics,
      nextMetrics: viewportMetrics,
      wasAtBottom: isAtBottomRef.current,
    });
    if (!adjustment) {
      return;
    }

    const frameIds: number[] = [];
    frameIds.push(
      window.requestAnimationFrame(() => {
        applyScrollTarget(adjustment);
        refreshScrollbar();
        frameIds.push(window.requestAnimationFrame(refreshScrollbar));
      })
    );

    return () => {
      for (const frameId of frameIds) {
        window.cancelAnimationFrame(frameId);
      }
    };
  }, [applyScrollTarget, refreshScrollbar, structureSignature, viewportMetrics]);

  useLayoutEffect(() => {
    const groupIndex = pendingCollapseScrollGroupIndexRef.current;
    if (groupIndex === null) {
      return;
    }

    const frameIds: number[] = [];
    let attempts = 0;

    const run = () => {
      attempts += 1;
      const completed = scrollCollapsedGroupIntoView(groupIndex);
      if (completed || attempts >= 3) {
        pendingCollapseScrollGroupIndexRef.current = null;
      }
    };

    run();
    frameIds.push(
      window.requestAnimationFrame(() => {
        run();
        frameIds.push(window.requestAnimationFrame(run));
      })
    );

    return () => {
      for (const frameId of frameIds) {
        window.cancelAnimationFrame(frameId);
      }
    };
  }, [groupCountsSignature, scrollCollapsedGroupIntoView]);

  const handleToggleVolume = useCallback(
    (volumeId: string) => {
      const groupIndex = getCollapseScrollGroupIndex({
        volumes,
        expandedVolumeIds,
        volumeId,
      });

      if (typeof groupIndex === "number") {
        const scroller = scrollerElementRef.current;
        const shouldAnchor = shouldAnchorCollapsedGroupScroll({
          groupIndex,
          stickyGroupIndex: getStickyGroupIndex(),
          groupTop: getRegularGroupTop(groupIndex),
          viewportTop: scroller?.getBoundingClientRect().top ?? 0,
        });
        pendingCollapseScrollGroupIndexRef.current = shouldAnchor ? groupIndex : null;
      }

      onToggleVolume(volumeId);
    },
    [expandedVolumeIds, getRegularGroupTop, getStickyGroupIndex, onToggleVolume, volumes]
  );

  const handleSortableDragEnd = useCallback(
    (event: DragEndEvent, chapterIds: string[]) => {
      if (isAgentLocked) {
        onLockedAction?.();
        return;
      }

      const { active, over } = event;
      if (!over || active.id === over.id) {
        return;
      }

      const oldIndex = chapterIds.indexOf(active.id as string);
      const newIndex = chapterIds.indexOf(over.id as string);
      if (oldIndex === -1 || newIndex === -1) {
        return;
      }

      reorderChapters(oldIndex, newIndex, chapterIds);
    },
    [isAgentLocked, onLockedAction, reorderChapters]
  );

  const handleRequestContextMenu = useCallback(
    (chapterId: string, chapterTitle: string, position: { x: number; y: number }) => {
      if (isAgentLocked) {
        onLockedAction?.();
        return;
      }
      setContextMenuPos(position);
      setContextMenuChapterId(chapterId);
      setContextMenuChapterTitle(chapterTitle);
    },
    [isAgentLocked, onLockedAction]
  );

  const handleLongPressStart = useCallback(() => {
    window.getSelection()?.removeAllRanges();
    setContextMenuPos(null);
    setContextMenuChapterId(null);
    setContextMenuChapterTitle(null);
  }, []);

  const handleCloseContextMenu = useCallback(() => {
    setContextMenuPos(null);
    setContextMenuChapterId(null);
    setContextMenuChapterTitle(null);
  }, []);

  const handleOpenInNewTab = useCallback(
    (chapterId: string, title: string) => {
      if (isAgentLocked) {
        onLockedAction?.();
        return;
      }
      onOpenInNewTab(chapterId, title);
    },
    [isAgentLocked, onLockedAction, onOpenInNewTab]
  );

  const handleDuplicate = useCallback(
    (chapterId: string, title: string) => {
      if (isAgentLocked) {
        onLockedAction?.();
        return;
      }
      onDuplicate(chapterId, title);
    },
    [isAgentLocked, onDuplicate, onLockedAction]
  );

  const handleStartRename = useCallback(
    (chapterId: string) => {
      if (isAgentLocked) {
        onLockedAction?.();
        return;
      }
      setRenamingChapterId(chapterId);
    },
    [isAgentLocked, onLockedAction]
  );

  const handleRenameConfirm = useCallback(
    (chapterId: string, newTitle: string) => {
      onRenameChapter(chapterId, newTitle);
      setRenamingChapterId(null);
    },
    [onRenameChapter]
  );

  const handleRenameCancel = useCallback(() => {
    setRenamingChapterId(null);
  }, []);

  const handleDelete = useCallback(
    (chapterId: string) => {
      if (isAgentLocked) {
        onLockedAction?.();
        return;
      }
      const chapter = listModel.chapterById.get(chapterId);
      if (chapter) {
        onDeleteChapter(chapter);
      }
    },
    [isAgentLocked, listModel, onDeleteChapter, onLockedAction]
  );

  const handleMoveToVolume = useCallback(
    (chapterId: string) => {
      if (isAgentLocked) {
        onLockedAction?.();
        return;
      }
      const chapter = listModel.chapterById.get(chapterId);
      if (chapter) {
        onMoveChapterToVolume(chapter);
      }
    },
    [isAgentLocked, listModel, onLockedAction, onMoveChapterToVolume]
  );

  const menuItems = useMemo<ContextMenuItem[]>(() => {
    if (!contextMenuChapterId || isAgentLocked) return [];

    const items: ContextMenuItem[] = [];

    if (!compact) {
      items.push({
        id: "openInNewTab",
        label: t("chapterMenu.openInNewTab"),
        icon: ExternalLink,
        onClick: () =>
          handleOpenInNewTab(contextMenuChapterId, contextMenuChapterTitle ?? ""),
      });
    }

    items.push({
      id: "addToConversation",
      label: t("chapterMenu.addToConversation"),
      icon: AtSign,
      disabled: !onAddToConversation,
      onClick: () => onAddToConversation?.(buildChapterMentionTag({
        chapterId: contextMenuChapterId,
        label: (contextMenuChapterTitle ?? "").trim() || t("writing.untitledChapter"),
      })),
    });

    items.push(
      {
        id: "duplicate",
        label: t("chapterMenu.duplicate"),
        icon: Copy,
        onClick: () =>
          handleDuplicate(contextMenuChapterId, contextMenuChapterTitle ?? ""),
      },
      {
        id: "rename",
        label: t("chapterMenu.rename"),
        icon: Pencil,
        onClick: () => handleStartRename(contextMenuChapterId),
      },
      {
        id: "moveToVolume",
        label: t("chapterMenu.moveToVolume"),
        icon: MoveRight,
        onClick: () => handleMoveToVolume(contextMenuChapterId),
      },
      {
        id: "delete",
        label: t("chapterMenu.delete"),
        icon: Trash2,
        danger: true,
        onClick: () => handleDelete(contextMenuChapterId),
      }
    );

    return items;
  }, [
    compact,
    contextMenuChapterId,
    contextMenuChapterTitle,
    handleDelete,
    handleDuplicate,
    handleMoveToVolume,
    onAddToConversation,
    handleOpenInNewTab,
    handleStartRename,
    isAgentLocked,
    t,
  ]);

  const renderItem = useCallback(
    (index: number) => {
      const row: GroupedVolumeListItem | undefined = listModel.items[index];
      if (!row) {
        return <VirtuosoFallbackMeasuredItem />;
      }

      if (row.type === "empty") {
        return (
          <Box px="4" py="3" style={{ borderBottom: "1px solid var(--gray-a4)" }}>
            <Text size="1" color="gray">
              {t("volume.empty")}
            </Text>
          </Box>
        );
      }

      return (
        <ChapterListItem
          chapter={row.chapter}
          isActive={currentChapterId === row.chapter.id}
          isRenaming={renamingChapterId === row.chapter.id}
          isMenuOpen={contextMenuChapterId === row.chapter.id && contextMenuPos !== null}
          onSelectChapter={onChapterSelect}
          onLongPressStart={handleLongPressStart}
          onRequestContextMenu={handleRequestContextMenu}
          onRenameChapter={handleRenameConfirm}
          onRenameCancel={handleRenameCancel}
          summaryStatus={summaryStatusMap[row.chapter.id]?.status}
          summaryIsStale={summaryStatusMap[row.chapter.id]?.isStale}
        />
      );
    },
    [
      contextMenuChapterId,
      contextMenuPos,
      currentChapterId,
      handleLongPressStart,
      handleRenameCancel,
      handleRenameConfirm,
      handleRequestContextMenu,
      listModel,
      onChapterSelect,
      renamingChapterId,
      summaryStatusMap,
      t,
    ]
  );

  const renderGroupHeader = useCallback(
    (groupIndex: number) => {
      const volume = volumes[groupIndex];
      if (!volume) return <VirtuosoFallbackMeasuredItem />;

      return (
        <VolumeHeader
          volume={volume}
          isExpanded={expandedVolumeIds.has(volume.id)}
          isRenaming={renamingVolumeId === volume.id}
          isFirst={groupIndex === 0}
          isLast={groupIndex === volumes.length - 1}
          isAgentLocked={isAgentLocked}
          onToggle={() => handleToggleVolume(volume.id)}
          onStartRename={() => onStartRenameVolume(volume.id)}
          onRenameConfirm={(title) => onRenameVolume(volume.id, title)}
          onRenameCancel={onCancelRenameVolume}
          onEditDescription={() => onEditVolumeDescription(volume)}
          onCreateChapter={() => onCreateChapterInVolume(volume.id)}
          onAddToConversation={onAddToConversation}
          onMoveUp={() => onMoveVolumeUp(volume)}
          onMoveDown={() => onMoveVolumeDown(volume)}
          onDelete={() => onDeleteVolume(volume)}
          onLockedAction={onLockedAction}
        />
      );
    },
    [
      expandedVolumeIds,
      isAgentLocked,
      onCancelRenameVolume,
      onAddToConversation,
      onCreateChapterInVolume,
      onDeleteVolume,
      onEditVolumeDescription,
      onLockedAction,
      onMoveVolumeDown,
      onMoveVolumeUp,
      onRenameVolume,
      onStartRenameVolume,
      handleToggleVolume,
      renamingVolumeId,
      volumes,
    ]
  );

  if (isDragMode) {
    return (
      <GroupedVolumeListScroller
        ref={(node) => {
          scrollerElementRef.current = node;
        }}
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          position: "relative",
          outline: "none",
          WebkitOverflowScrolling: "touch",
        }}
        tabIndex={0}
      >
        <Box style={{ minHeight: "100%" }}>
          {volumes.map((volume, groupIndex) => {
            const isExpanded = expandedVolumeIds.has(volume.id);
            const sortedChapters = getSortedVolumeChapters(volume.chapters, dragOrderMap);
            const chapterIds = sortedChapters.map((chapter) => chapter.id);

            return (
              <Box key={volume.id} style={{ minWidth: 0 }}>
                <Box
                  style={{
                    position: "sticky",
                    top: 0,
                    zIndex: 3,
                  }}
                >
                  <VolumeHeader
                    volume={volume}
                    isExpanded={isExpanded}
                    isRenaming={renamingVolumeId === volume.id}
                    isFirst={groupIndex === 0}
                    isLast={groupIndex === volumes.length - 1}
                    isAgentLocked={isAgentLocked}
                    onToggle={() => handleToggleVolume(volume.id)}
                    onStartRename={() => onStartRenameVolume(volume.id)}
                    onRenameConfirm={(title) => onRenameVolume(volume.id, title)}
                    onRenameCancel={onCancelRenameVolume}
                    onEditDescription={() => onEditVolumeDescription(volume)}
                    onCreateChapter={() => onCreateChapterInVolume(volume.id)}
                    onAddToConversation={onAddToConversation}
                    onMoveUp={() => onMoveVolumeUp(volume)}
                    onMoveDown={() => onMoveVolumeDown(volume)}
                    onDelete={() => onDeleteVolume(volume)}
                    onLockedAction={onLockedAction}
                  />
                </Box>

                {isExpanded && sortedChapters.length === 0 ? (
                  <Box px="4" py="3" style={{ borderBottom: "1px solid var(--gray-a4)" }}>
                    <Text size="1" color="gray">
                      {t("volume.empty")}
                    </Text>
                  </Box>
                ) : null}

                {isExpanded && sortedChapters.length > 0 ? (
                  <DndContext
                    sensors={sensors}
                    collisionDetection={closestCenter}
                    onDragEnd={(event) => handleSortableDragEnd(event, chapterIds)}
                    modifiers={[restrictToVerticalAxis, restrictToParentElement]}
                  >
                    <SortableContext items={chapterIds} strategy={verticalListSortingStrategy}>
                      {sortedChapters.map((chapter) => (
                        <SortableChapterListItem
                          key={chapter.id}
                          chapter={chapter}
                          isActive={currentChapterId === chapter.id}
                          onSelectChapter={onChapterSelect}
                          summaryStatus={summaryStatusMap[chapter.id]?.status}
                          summaryIsStale={summaryStatusMap[chapter.id]?.isStale}
                        />
                      ))}
                    </SortableContext>
                  </DndContext>
                ) : null}
              </Box>
            );
          })}
        </Box>
      </GroupedVolumeListScroller>
    );
  }

  return (
    <>
      <GroupedVirtuoso
        ref={virtuosoRef}
        style={{ flex: 1, minHeight: 0 }}
        groupCounts={listModel.groupCounts}
        overscan={5}
        atBottomStateChange={handleAtBottomStateChange}
        components={GROUPED_VOLUME_LIST_COMPONENTS}
        scrollerRef={handleScrollerRef}
        totalListHeightChanged={markListMeasured}
        rangeChanged={markListMeasured}
        computeItemKey={(index) => listModel.keyByInternalIndex.get(index) ?? index}
        groupContent={renderGroupHeader}
        itemContent={renderItem}
      />

      <ContextMenu
        position={contextMenuPos}
        items={menuItems}
        onClose={handleCloseContextMenu}
      />
    </>
  );
}

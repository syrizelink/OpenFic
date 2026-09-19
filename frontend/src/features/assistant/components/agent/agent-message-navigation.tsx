import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type FocusEvent,
} from "react";
import { useTranslation } from "react-i18next";

import { StreamingMarkdown } from "@/components";

import type { AgentMessageNavigationItem } from "./agent-message-navigation-utils";
import {
  getMessageNavigationNeighborDistance,
  getMessageNavigationNeighborCount,
  getMessageNavigationNeighborScale,
  getMessageNavigationScrollState,
} from "./agent-message-navigation-utils";

import "./agent-message-navigation.css";

interface AgentMessageNavigationProps {
  items: readonly AgentMessageNavigationItem[];
  activeIndex: number;
  onNavigate: (blockIndex: number) => void;
}

function normalizeUserPreview(content: string): string {
  return content.replace(/\s+/g, " ").trim();
}

export function AgentMessageNavigation({
  items,
  activeIndex,
  onNavigate,
}: AgentMessageNavigationProps) {
  const { t } = useTranslation();
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [previewTop, setPreviewTop] = useState<number | null>(null);
  const [scrollState, setScrollState] = useState({
    canScrollDown: false,
    canScrollUp: false,
  });
  const [navigationMaxHeight, setNavigationMaxHeight] = useState<number | null>(null);
  const navigationRef = useRef<HTMLElement | null>(null);
  const trackRef = useRef<HTMLOListElement | null>(null);
  const itemRefs = useRef<Array<HTMLLIElement | null>>([]);
  const hoverClearTimeoutRef = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (hoverClearTimeoutRef.current !== null) {
        window.clearTimeout(hoverClearTimeoutRef.current);
      }
    },
    [],
  );

  const cancelHoverClear = () => {
    if (hoverClearTimeoutRef.current === null) return;
    window.clearTimeout(hoverClearTimeoutRef.current);
    hoverClearTimeoutRef.current = null;
  };

  const scheduleHoverClear = () => {
    cancelHoverClear();
    hoverClearTimeoutRef.current = window.setTimeout(() => {
      hoverClearTimeoutRef.current = null;
      setHoveredIndex(null);
    }, 120);
  };

  const updatePreviewPosition = (index: number) => {
    const item = itemRefs.current[index];
    const navigation = navigationRef.current;
    if (!item || !navigation) return;

    const itemRect = item.getBoundingClientRect();
    const navigationRect = navigation.getBoundingClientRect();
    setPreviewTop(itemRect.top - navigationRect.top + itemRect.height / 2);
  };

  const updateScrollState = () => {
    const track = trackRef.current;
    if (!track) return;

    const nextState = getMessageNavigationScrollState(
      track.scrollTop,
      track.clientHeight,
      track.scrollHeight,
    );
    setScrollState((current) =>
      current.canScrollDown === nextState.canScrollDown &&
      current.canScrollUp === nextState.canScrollUp
        ? current
        : nextState,
    );
  };

  const handleFocus = (index: number) => {
    cancelHoverClear();
    setHoveredIndex(index);
    updatePreviewPosition(index);
  };

  const handleBlur = (event: FocusEvent<HTMLButtonElement>) => {
    if (
      event.relatedTarget instanceof Node &&
      navigationRef.current?.contains(event.relatedTarget)
    ) {
      return;
    }
    scheduleHoverClear();
  };

  const handleTrackScroll = () => {
    updateScrollState();
    if (hoveredIndex !== null) updatePreviewPosition(hoveredIndex);
  };

  const handleNavigate = (blockIndex: number) => {
    cancelHoverClear();
    onNavigate(blockIndex);
  };

  useLayoutEffect(() => {
    const track = trackRef.current;
    const container = track?.closest(".ai-sidebar-messages");
    if (!(container instanceof HTMLElement)) return;

    const updateNavigationMaxHeight = () => {
      setNavigationMaxHeight(Math.floor(container.clientHeight * 0.75));
    };
    const observer = new ResizeObserver(updateNavigationMaxHeight);
    observer.observe(container);
    updateNavigationMaxHeight();
    return () => observer.disconnect();
  }, [items.length]);

  useLayoutEffect(() => {
    const track = trackRef.current;
    if (!track) return;

    track.scrollTop = track.scrollHeight;
    const nextState = getMessageNavigationScrollState(
      track.scrollTop,
      track.clientHeight,
      track.scrollHeight,
    );
    setScrollState(nextState);
  }, [items.length, navigationMaxHeight]);

  if (items.length < 2) return null;

  const hoveredItem = hoveredIndex === null ? null : (items[hoveredIndex] ?? null);
  const hoveredPreviewId =
    hoveredIndex === null ? null : `agent-message-navigation-preview-${hoveredIndex}`;
  const trackStyle =
    navigationMaxHeight === null
      ? undefined
      : ({
          "--agent-message-navigation-max-height": `${navigationMaxHeight}px`,
        } as CSSProperties);

  return (
    <nav
      ref={navigationRef}
      className="agent-message-navigation"
      aria-label={t("assistant.messageNavigation.label")}
    >
      <div className="agent-message-navigation-viewport">
        <ol
          ref={trackRef}
          className="agent-message-navigation-track"
          style={trackStyle}
          data-hovering={hoveredIndex === null ? undefined : "true"}
          onScroll={handleTrackScroll}
        >
          {items.map((item, index) => {
            const isActive = index === activeIndex;
            const isHovered = index === hoveredIndex;
            const neighborDistance = getMessageNavigationNeighborDistance(
              index,
              hoveredIndex,
              items.length,
            );
            const neighborScale = neighborDistance
              ? Math.round(
                  getMessageNavigationNeighborScale(
                    neighborDistance,
                    getMessageNavigationNeighborCount(items.length),
                  ) * 1000,
                )
              : undefined;
            const previewId = `agent-message-navigation-preview-${index}`;

            return (
              <li
                key={item.id}
                ref={(element) => {
                  itemRefs.current[index] = element;
                }}
                className="agent-message-navigation-item"
                data-active={isActive ? "true" : undefined}
                data-hovered={isHovered ? "true" : undefined}
                data-neighbor={neighborDistance || undefined}
                data-neighbor-scale={neighborScale}
              >
                <button
                  type="button"
                  className="agent-message-navigation-button"
                  aria-label={t("assistant.messageNavigation.item", { count: index + 1 })}
                  aria-current={isActive ? "location" : undefined}
                  aria-describedby={isHovered ? previewId : undefined}
                  onClick={() => handleNavigate(item.blockIndex)}
                  onPointerEnter={() => handleFocus(index)}
                  onPointerLeave={scheduleHoverClear}
                  onFocus={() => handleFocus(index)}
                  onBlur={handleBlur}
                >
                  <span className="agent-message-navigation-line" />
                </button>
              </li>
            );
          })}
        </ol>
        {scrollState.canScrollUp ? (
          <span
            className="agent-message-navigation-scroll-mask agent-message-navigation-scroll-mask--top"
            aria-hidden="true"
          />
        ) : null}
        {scrollState.canScrollDown ? (
          <span
            className="agent-message-navigation-scroll-mask agent-message-navigation-scroll-mask--bottom"
            aria-hidden="true"
          />
        ) : null}
      </div>
      {hoveredItem && hoveredIndex !== null && previewTop !== null ? (
        <div
          id={hoveredPreviewId ?? undefined}
          className="agent-message-navigation-preview"
          role="button"
          tabIndex={0}
          aria-label={t("assistant.messageNavigation.item", { count: hoveredIndex + 1 })}
          style={
            {
              "--agent-message-navigation-preview-top": `${previewTop}px`,
            } as CSSProperties
          }
          onClick={() => handleNavigate(hoveredItem.blockIndex)}
          onKeyDown={(event) => {
            if (event.key !== "Enter" && event.key !== " ") return;
            event.preventDefault();
            handleNavigate(hoveredItem.blockIndex);
          }}
          onPointerEnter={cancelHoverClear}
          onPointerLeave={scheduleHoverClear}
        >
          <div className="agent-message-navigation-user-preview">
            {normalizeUserPreview(hoveredItem.userContent) ||
              t("assistant.messageNavigation.emptyUser")}
          </div>
          {hoveredItem.assistantContent ? (
            <StreamingMarkdown
              content={hoveredItem.assistantContent}
              className="agent-message-navigation-assistant-preview"
            />
          ) : null}
        </div>
      ) : null}
    </nav>
  );
}

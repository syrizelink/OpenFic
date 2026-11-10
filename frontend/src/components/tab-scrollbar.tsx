import { useEffect, useRef, type RefObject } from "react";

import "./tab-scrollbar.css";

interface TabScrollbarProps {
  listRef: RefObject<HTMLDivElement | null>;
  listId: string;
  label: string;
  items: readonly unknown[];
  isDragging: boolean;
}

export function TabScrollbar({ listRef, listId, label, items, isDragging }: TabScrollbarProps) {
  const scrollbarRef = useRef<HTMLDivElement>(null);
  const thumbRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const list = listRef.current;
    const scrollbar = scrollbarRef.current;
    const thumb = thumbRef.current;
    if (!list || !scrollbar || !thumb) return;
    let dragOffset = 0;

    const updateScrollbar = () => {
      const maxScroll = Math.max(0, list.scrollWidth - list.clientWidth);
      const thumbWidth = maxScroll ? Math.max(20, list.clientWidth ** 2 / list.scrollWidth) : 0;
      const parentRect = scrollbar.parentElement?.getBoundingClientRect();
      if (!parentRect) return;
      scrollbar.style.left = `${list.getBoundingClientRect().left - parentRect.left}px`;
      scrollbar.style.width = `${list.clientWidth}px`;
      thumb.style.width = `${thumbWidth}px`;
      thumb.style.transform = `translateX(${maxScroll ? (list.scrollLeft / maxScroll) * (list.clientWidth - thumbWidth) : 0}px)`;
      scrollbar.hidden = maxScroll === 0;
      scrollbar.setAttribute("aria-valuemax", String(maxScroll));
      scrollbar.setAttribute("aria-valuenow", String(Math.round(list.scrollLeft)));
    };
    const moveThumb = (clientX: number) => {
      const track = scrollbar.getBoundingClientRect();
      const travel = track.width - thumb.offsetWidth;
      if (travel <= 0) return;
      list.scrollLeft =
        ((clientX - track.left - dragOffset) / travel) * (list.scrollWidth - list.clientWidth);
    };
    const handlePointerDown = (event: PointerEvent) => {
      if (event.button !== 0) return;
      event.preventDefault();
      const rect = thumb.getBoundingClientRect();
      dragOffset = event.target === thumb ? event.clientX - rect.left : rect.width / 2;
      scrollbar.setPointerCapture(event.pointerId);
      moveThumb(event.clientX);
    };
    const handlePointerMove = (event: PointerEvent) => {
      if (scrollbar.hasPointerCapture(event.pointerId)) moveThumb(event.clientX);
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "ArrowLeft") list.scrollLeft -= 40;
      else if (event.key === "ArrowRight") list.scrollLeft += 40;
      else if (event.key === "Home") list.scrollLeft = 0;
      else if (event.key === "End") list.scrollLeft = list.scrollWidth;
      else return;
      event.preventDefault();
    };
    const handleWheel = (event: WheelEvent) => {
      if (event.ctrlKey || list.scrollWidth <= list.clientWidth) return;
      const delta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
      const scale = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? list.clientWidth : 1;
      event.preventDefault();
      list.scrollLeft += delta * scale;
    };
    const observer = new ResizeObserver(updateScrollbar);
    observer.observe(list);
    for (const tab of list.children) observer.observe(tab);
    const childObserver = new MutationObserver(() => {
      for (const tab of list.children) observer.observe(tab);
      updateScrollbar();
    });
    childObserver.observe(list, { childList: true });
    list.addEventListener("scroll", updateScrollbar, { passive: true });
    scrollbar.addEventListener("pointerdown", handlePointerDown);
    scrollbar.addEventListener("pointermove", handlePointerMove);
    scrollbar.addEventListener("keydown", handleKeyDown);
    scrollbar.addEventListener("wheel", handleWheel, { passive: false });
    updateScrollbar();
    return () => {
      observer.disconnect();
      childObserver.disconnect();
      list.removeEventListener("scroll", updateScrollbar);
      scrollbar.removeEventListener("pointerdown", handlePointerDown);
      scrollbar.removeEventListener("pointermove", handlePointerMove);
      scrollbar.removeEventListener("keydown", handleKeyDown);
      scrollbar.removeEventListener("wheel", handleWheel);
    };
  }, [items, listRef]);

  return (
    <div
      ref={scrollbarRef}
      className="tab-scrollbar"
      role="scrollbar"
      aria-label={label}
      aria-controls={listId}
      aria-orientation="horizontal"
      aria-valuemin={0}
      aria-valuemax={0}
      aria-valuenow={0}
      tabIndex={0}
      data-dragging={isDragging}
      hidden
    >
      <div
        ref={thumbRef}
        className="tab-scrollbar-thumb"
      />
    </div>
  );
}

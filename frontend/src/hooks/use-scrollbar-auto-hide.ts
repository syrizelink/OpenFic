/**
 * useScrollbarAutoHide Hook
 *
 * 自动隐藏滚动条的 hook。
 * - 用户滚轮滚动时显示滚动条，5 秒后自动隐藏
 * - hover 滚动条区域（右侧热区）时显示滚动条
 * - 打字导致的内容变化滚动不会触发显示
 */

import { useCallback, useRef, useEffect } from "react";

const SCROLLBAR_WIDTH = 20; // 滚动条热区宽度（包含一些余量）

/**
 * 返回一个对象包含：
 * - containerRef: 需要绑定到滚动容器的 ref
 * - scrollbarProps: 需要绑定到滚动容器的事件处理函数和 className
 */
export function useScrollbarAutoHide(hideDelay = 5000) {
  const containerRef = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isHoveringScrollbarRef = useRef(false);

  const showScrollbar = useCallback(() => {
    if (containerRef.current) {
      containerRef.current.classList.add("scrolling");
    }
  }, []);

  const hideScrollbar = useCallback(() => {
    // 如果正在 hover 滚动条区域，不隐藏
    if (isHoveringScrollbarRef.current) return;
    if (containerRef.current) {
      containerRef.current.classList.remove("scrolling");
    }
  }, []);

  const resetTimer = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    showScrollbar();
    timeoutRef.current = setTimeout(hideScrollbar, hideDelay);
  }, [showScrollbar, hideScrollbar, hideDelay]);

  // 滚轮事件（用户主动滚动）
  const handleWheel = useCallback(() => {
    resetTimer();
  }, [resetTimer]);

  // 鼠标移动事件 - 检测是否在右侧滚动条热区
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const isInScrollbarZone = e.clientX >= rect.right - SCROLLBAR_WIDTH;

      if (isInScrollbarZone && !isHoveringScrollbarRef.current) {
        isHoveringScrollbarRef.current = true;
        showScrollbar();
        // 清除自动隐藏定时器
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
          timeoutRef.current = null;
        }
      } else if (!isInScrollbarZone && isHoveringScrollbarRef.current) {
        isHoveringScrollbarRef.current = false;
        // 离开热区后启动隐藏定时器
        timeoutRef.current = setTimeout(hideScrollbar, hideDelay);
      }
    },
    [showScrollbar, hideScrollbar, hideDelay]
  );

  // 鼠标离开容器
  const handleMouseLeave = useCallback(() => {
    isHoveringScrollbarRef.current = false;
    timeoutRef.current = setTimeout(hideScrollbar, hideDelay);
  }, [hideScrollbar, hideDelay]);

  // 清理定时器
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return {
    containerRef,
    scrollbarProps: {
      className: "scrollbar-auto-hide",
      onWheel: handleWheel,
      onMouseMove: handleMouseMove,
      onMouseLeave: handleMouseLeave,
    },
  };
}

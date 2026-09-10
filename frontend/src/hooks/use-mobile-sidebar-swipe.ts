import { useRef } from "react";
import { useSwipeable, type SwipeableHandlers } from "react-swipeable";

const SWIPE_IGNORE_SELECTOR = "[data-mobile-sidebar-swipe-ignore]";

function isIgnoredSwipeTarget(target: EventTarget | null): boolean {
  return target instanceof Element && target.closest(SWIPE_IGNORE_SELECTOR) !== null;
}

interface UseMobileSidebarSwipeOptions {
  isEnabled: boolean;
  isOpen: boolean;
  onOpen?: () => void;
  onClose?: () => void;
  onSwipe?: () => void;
}

export function useMobileSidebarSwipe({
  isEnabled,
  isOpen,
  onOpen,
  onClose,
  onSwipe,
}: UseMobileSidebarSwipeOptions): SwipeableHandlers {
  const shouldIgnoreSwipeRef = useRef(false);

  return useSwipeable({
    delta: 40,
    onTouchStartOrOnMouseDown: ({ event }) => {
      shouldIgnoreSwipeRef.current = isIgnoredSwipeTarget(event.target);
    },
    onTouchEndOrOnMouseUp: () => {
      shouldIgnoreSwipeRef.current = false;
    },
    onSwipedRight: () => {
      if (shouldIgnoreSwipeRef.current || !isEnabled || isOpen) return;
      onSwipe?.();
      onOpen?.();
    },
    onSwipedLeft: () => {
      if (shouldIgnoreSwipeRef.current || !isEnabled || !isOpen) return;
      onSwipe?.();
      onClose?.();
    },
    trackTouch: isEnabled,
    trackMouse: false,
  });
}

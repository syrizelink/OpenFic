import { useSwipeable, type SwipeableHandlers } from "react-swipeable";

interface UseMobileSidebarSwipeOptions {
  isEnabled: boolean;
  isOpen: boolean;
  onOpen?: () => void;
  onClose?: () => void;
}

export function useMobileSidebarSwipe({
  isEnabled,
  isOpen,
  onOpen,
  onClose,
}: UseMobileSidebarSwipeOptions): SwipeableHandlers {
  return useSwipeable({
    delta: 40,
    onSwipedRight: () => {
      if (isEnabled && !isOpen) onOpen?.();
    },
    onSwipedLeft: () => {
      if (isEnabled && isOpen) onClose?.();
    },
    trackTouch: isEnabled,
    trackMouse: false,
  });
}

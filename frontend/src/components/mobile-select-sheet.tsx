import { Box, Dialog, Flex } from "@radix-ui/themes";
import clsx from "clsx";
import { useRef, useState } from "react";
import type {
  CSSProperties,
  AnimationEvent as ReactAnimationEvent,
  PointerEvent as ReactPointerEvent,
  ReactNode,
  TransitionEvent as ReactTransitionEvent,
} from "react";

import "./mobile-select-sheet.css";

export interface MobileSelectSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  trigger: ReactNode;
  children: ReactNode;
  contentClassName?: string;
}

interface DragState {
  pointerId: number;
  startY: number;
  currentY: number;
  isDragging: boolean;
}

const DRAG_START_THRESHOLD = 8;
const SWIPE_DISMISS_THRESHOLD = 80;

export function MobileSelectSheet({
  open,
  onOpenChange,
  title,
  trigger,
  children,
  contentClassName,
}: MobileSelectSheetProps) {
  const [dragOffset, setDragOffset] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [isSwipeClosing, setIsSwipeClosing] = useState(false);
  const [isEntering, setIsEntering] = useState(false);
  const dragStateRef = useRef<DragState | null>(null);

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (nextOpen) {
      setIsSwipeClosing(false);
      setIsDragging(false);
      setDragOffset(0);
      setIsEntering(true);
      onOpenChange(true);
      return;
    }

    if (isSwipeClosing) return;

    setIsEntering(false);
    setIsDragging(false);
    setDragOffset(0);
    setIsSwipeClosing(true);
  };

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.pointerType === "mouse" || event.button !== 0) return;

    dragStateRef.current = {
      pointerId: event.pointerId,
      startY: event.clientY,
      currentY: event.clientY,
      isDragging: false,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) return;

    dragState.currentY = event.clientY;
    const deltaY = event.clientY - dragState.startY;
    if (!dragState.isDragging && deltaY < DRAG_START_THRESHOLD) return;

    dragState.isDragging = true;
    setIsEntering(false);
    setIsDragging(true);
    const nextOffset = Math.max(0, deltaY);
    if (nextOffset > 0) event.preventDefault();
    setDragOffset(nextOffset);
  };

  const handlePointerEnd = (event: ReactPointerEvent<HTMLDivElement>) => {
    const dragState = dragStateRef.current;
    if (!dragState || dragState.pointerId !== event.pointerId) return;

    const wasDragging = dragState.isDragging;
    const finalOffset = Math.max(0, (event.clientY || dragState.currentY) - dragState.startY);
    dragStateRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }

    if (!wasDragging) return;

    setIsDragging(false);
    if (finalOffset >= SWIPE_DISMISS_THRESHOLD) {
      setDragOffset(finalOffset);
      setIsSwipeClosing(true);
      return;
    }
    setDragOffset(0);
  };

  const handleTransitionEnd = (event: ReactTransitionEvent<HTMLDivElement>) => {
    if (
      !isSwipeClosing ||
      event.target !== event.currentTarget ||
      event.propertyName !== "transform"
    ) {
      return;
    }

    onOpenChange(false);
  };

  const handleAnimationEnd = (event: ReactAnimationEvent<HTMLDivElement>) => {
    if (
      event.target !== event.currentTarget ||
      event.animationName !== "mobile-select-sheet-slide-in"
    ) {
      return;
    }

    setIsEntering(false);
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={handleDialogOpenChange}
    >
      <Dialog.Trigger>{trigger}</Dialog.Trigger>
      <Dialog.Content
        maxWidth="none"
        className={clsx("mobile-select-sheet-content", contentClassName)}
        aria-describedby={undefined}
        data-dragging={isDragging ? "true" : undefined}
        data-entering={isEntering ? "true" : undefined}
        data-swipe-closing={isSwipeClosing ? "true" : undefined}
        style={
          {
            "--mobile-select-sheet-drag-offset": `${dragOffset}px`,
          } as CSSProperties
        }
        onOpenAutoFocus={(event) => event.preventDefault()}
        onAnimationEnd={handleAnimationEnd}
        onTransitionEnd={handleTransitionEnd}
      >
        <Flex
          align="center"
          className="mobile-select-sheet-header"
        >
          <Box
            className="mobile-select-sheet-gesture-area"
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={handlePointerEnd}
            onPointerCancel={handlePointerEnd}
          >
            <Box
              aria-hidden="true"
              className="mobile-select-sheet-handle"
            />
          </Box>
          <Dialog.Title className="mobile-select-sheet-visually-hidden">{title}</Dialog.Title>
        </Flex>
        <Box className="mobile-select-sheet-body">{children}</Box>
      </Dialog.Content>
    </Dialog.Root>
  );
}

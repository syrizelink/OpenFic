import { ChevronDown } from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useLayoutEffect, useRef, useState } from "react";

import type { AgentMessage } from "@/lib/agent.types";

import { InlineMentionText } from "../../../inline-mention-text";
import { MessageCardShell, UserMessageShell } from "../../shared/message-shell";
import { joinClassNames } from "../../shared/message-shell-utils";

interface UserRequestMessageProps {
  message: AgentMessage;
  onOpenMentionChapter?: (chapterId: string, chapterTitle: string) => void;
}

const USER_MESSAGE_LAYOUT_TRANSITION = {
  duration: 0.22,
  ease: [0.22, 1, 0.36, 1] as const,
};

const USER_MESSAGE_AFFORDANCE_TRANSITION = {
  duration: 0.16,
  ease: [0.22, 1, 0.36, 1] as const,
};

interface UserMessageMeasurements {
  contentHeight: number;
  previewHeight: number;
}

export function UserRequestMessage({ message, onOpenMentionChapter }: UserRequestMessageProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isPointerInside, setIsPointerInside] = useState(false);
  const [suppressCollapsedOverlay, setSuppressCollapsedOverlay] = useState(false);
  const [measurements, setMeasurements] = useState<UserMessageMeasurements | null>(null);
  const [shouldAnimateHeight, setShouldAnimateHeight] = useState(false);
  const textRef = useRef<HTMLSpanElement>(null);

  const updateMeasurements = useCallback(() => {
    const text = textRef.current;
    if (!text) return;

    const lineHeight = Number.parseFloat(window.getComputedStyle(text).lineHeight);
    const contentHeight = text.scrollHeight;
    const previewHeight = Math.min(contentHeight, Math.ceil(lineHeight * 4));

    setMeasurements((current) => {
      if (current?.contentHeight === contentHeight && current.previewHeight === previewHeight) {
        return current;
      }
      return { contentHeight, previewHeight };
    });
  }, []);

  useLayoutEffect(() => {
    const text = textRef.current;
    if (!text) return;

    updateMeasurements();
    const resizeObserver = new ResizeObserver(updateMeasurements);
    resizeObserver.observe(text);
    return () => resizeObserver.disconnect();
  }, [message.content, updateMeasurements]);

  const isClamped =
    measurements !== null && measurements.contentHeight > measurements.previewHeight;
  const canToggle = isClamped || isExpanded;
  const showCollapsedMask = isClamped && !isExpanded;
  const showExpandArrow = showCollapsedMask && isPointerInside && !suppressCollapsedOverlay;
  const targetHeight = measurements
    ? isExpanded
      ? measurements.contentHeight
      : measurements.previewHeight
    : "auto";

  const handleToggle = useCallback(() => {
    if (!canToggle) return;

    setShouldAnimateHeight(true);
    if (isExpanded) {
      setIsExpanded(false);
      setSuppressCollapsedOverlay(true);
      return;
    }

    setSuppressCollapsedOverlay(false);
    setIsExpanded(true);
  }, [canToggle, isExpanded]);

  const handleHeightAnimationComplete = useCallback(() => {
    setShouldAnimateHeight(false);
  }, []);

  const handlePointerEnter = useCallback(() => {
    setIsPointerInside(true);
    setSuppressCollapsedOverlay(false);
  }, []);

  const handlePointerLeave = useCallback(() => {
    setIsPointerInside(false);
  }, []);

  return (
    <UserMessageShell>
      <MessageCardShell
        className={joinClassNames(
          "ai-sidebar-user-message",
          "agent-user-message-preview",
          isExpanded && "agent-user-message-preview--expanded",
          isClamped && "agent-user-message-preview--clamped",
        )}
        onClick={handleToggle}
        onPointerEnter={handlePointerEnter}
        onPointerLeave={handlePointerLeave}
        role={canToggle ? "button" : undefined}
        tabIndex={canToggle ? 0 : undefined}
        aria-expanded={isClamped ? isExpanded : undefined}
      >
        <motion.div
          className="agent-user-message-content-viewport"
          initial={false}
          animate={{ height: targetHeight }}
          transition={shouldAnimateHeight ? USER_MESSAGE_LAYOUT_TRANSITION : { duration: 0 }}
          onAnimationComplete={handleHeightAnimationComplete}
        >
          <InlineMentionText
            ref={textRef}
            text={message.content ?? ""}
            className="agent-user-message-preview-text"
            onOpenMentionChapter={onOpenMentionChapter}
          />
        </motion.div>
        <motion.div
          className="agent-user-message-expand-overlay"
          initial={false}
          animate={{ opacity: showCollapsedMask ? 1 : 0 }}
          transition={USER_MESSAGE_AFFORDANCE_TRANSITION}
          aria-hidden={!showCollapsedMask}
        >
          <motion.span
            className="agent-user-message-chevron-motion"
            animate={{ opacity: showExpandArrow ? 1 : 0, y: showExpandArrow ? 0 : 6 }}
            transition={USER_MESSAGE_AFFORDANCE_TRANSITION}
          >
            <ChevronDown
              size={14}
              className="agent-user-message-expand-icon"
            />
          </motion.span>
        </motion.div>
        <motion.div
          className="agent-user-message-collapse-indicator"
          initial={false}
          animate={{
            height: isExpanded ? "auto" : 0,
            marginTop: isExpanded ? 6 : 0,
            opacity: isExpanded ? 1 : 0,
            y: isExpanded ? 0 : -4,
          }}
          transition={USER_MESSAGE_AFFORDANCE_TRANSITION}
          aria-hidden={!isExpanded}
        >
          <motion.span
            className="agent-user-message-chevron-motion"
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={USER_MESSAGE_LAYOUT_TRANSITION}
          >
            <ChevronDown size={14} />
          </motion.span>
        </motion.div>
      </MessageCardShell>
    </UserMessageShell>
  );
}

import { ChevronDown } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";

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

export function UserRequestMessage({ message, onOpenMentionChapter }: UserRequestMessageProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isClamped, setIsClamped] = useState(false);
  const [isPointerInside, setIsPointerInside] = useState(false);
  const [suppressCollapsedOverlay, setSuppressCollapsedOverlay] = useState(false);
  const textRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = textRef.current;
    if (!el) return;
    setIsClamped(el.scrollHeight > el.clientHeight);
  }, [message.content]);

  const canToggle = isClamped || isExpanded;
  const showExpandOverlay =
    isClamped && !isExpanded && isPointerInside && !suppressCollapsedOverlay;

  const handleToggle = useCallback(() => {
    if (!canToggle) return;

    if (isExpanded) {
      setIsExpanded(false);
      setSuppressCollapsedOverlay(true);
      return;
    }

    setSuppressCollapsedOverlay(false);
    setIsExpanded(true);
  }, [canToggle, isExpanded]);

  const handlePointerEnter = useCallback(() => {
    setIsPointerInside(true);
    setSuppressCollapsedOverlay(false);
  }, []);

  const handlePointerLeave = useCallback(() => {
    setIsPointerInside(false);
  }, []);

  return (
    <UserMessageShell>
      <motion.div
        layout
        transition={USER_MESSAGE_LAYOUT_TRANSITION}
        style={{ width: "100%" }}
      >
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
          <InlineMentionText
            ref={textRef}
            text={message.content ?? ""}
            className="agent-user-message-preview-text"
            onOpenMentionChapter={onOpenMentionChapter}
          />
          <AnimatePresence initial={false}>
            {showExpandOverlay ? (
              <motion.div
                key="expand-overlay"
                className="agent-user-message-expand-overlay"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 6 }}
                transition={USER_MESSAGE_AFFORDANCE_TRANSITION}
              >
                <motion.span
                  className="agent-user-message-chevron-motion"
                  initial={{ rotate: 180 }}
                  animate={{ rotate: 0 }}
                  transition={USER_MESSAGE_LAYOUT_TRANSITION}
                >
                  <ChevronDown
                    size={14}
                    className="agent-user-message-expand-icon"
                  />
                </motion.span>
              </motion.div>
            ) : null}
          </AnimatePresence>
          <AnimatePresence initial={false}>
            {isExpanded ? (
              <motion.div
                key="collapse-indicator"
                className="agent-user-message-collapse-indicator"
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={USER_MESSAGE_AFFORDANCE_TRANSITION}
              >
                <motion.span
                  className="agent-user-message-chevron-motion"
                  initial={{ rotate: 0 }}
                  animate={{ rotate: 180 }}
                  transition={USER_MESSAGE_LAYOUT_TRANSITION}
                >
                  <ChevronDown size={14} />
                </motion.span>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </MessageCardShell>
      </motion.div>
    </UserMessageShell>
  );
}

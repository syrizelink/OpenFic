import { IconButton } from "@radix-ui/themes";
import { Clock3, Reply } from "lucide-react";
import { motion } from "motion/react";
import type { CSSProperties } from "react";
import { useTranslation } from "react-i18next";

import type { AgentPendingMessage } from "@/lib/agent.types";

import { InlineMentionText } from "./inline-mention-text";

interface AgentPendingMessageCardProps {
  pendingMessage: AgentPendingMessage;
  clearanceHeight: number;
  onCancel?: () => void;
  onOpenMentionChapter?: (chapterId: string, chapterTitle: string) => void;
}

export function AgentPendingMessageCard({
  pendingMessage,
  clearanceHeight,
  onCancel,
  onOpenMentionChapter,
}: AgentPendingMessageCardProps) {
  const { t } = useTranslation();
  const normalizedClearanceHeight = Math.max(clearanceHeight, 0);
  const overlapOffset = Math.min(normalizedClearanceHeight, 12);
  const style = {
    "--ai-sidebar-pending-clearance-height": `${normalizedClearanceHeight}px`,
    "--ai-sidebar-pending-overlap-offset": `${overlapOffset}px`,
  } as CSSProperties;

  return (
    <motion.div
      className="ai-sidebar-pending-shell"
      style={style}
      initial={{ opacity: 0, y: 10, height: 0 }}
      animate={{ opacity: 1, y: 0, height: "auto" }}
      exit={{ opacity: 0, y: 10, height: 0 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
    >
      <div className="ai-sidebar-pending-card-stack">
        <div className="ai-sidebar-pending-card">
          <div className="ai-sidebar-pending-card-content">
            <Clock3
              size={12}
              aria-hidden="true"
              className="ai-sidebar-pending-clock"
            />
            <InlineMentionText
              text={pendingMessage.content}
              className="ai-sidebar-pending-content"
              singleLine
              onOpenMentionChapter={onOpenMentionChapter}
            />
            <IconButton
              type="button"
              variant="ghost"
              size="1"
              className="ai-sidebar-pending-cancel"
              onClick={onCancel}
              disabled={!onCancel}
              aria-label={t("assistant.cancelPendingMessage")}
            >
              <Reply size={12} />
            </IconButton>
          </div>
          <div
            aria-hidden="true"
            className="ai-sidebar-pending-card-clearance"
          />
        </div>
      </div>
    </motion.div>
  );
}

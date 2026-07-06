import { SegmentedControl } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";

import { useWritingStore } from "../store/use-writing-store";
import { ChapterSidebar } from "./chapter-sidebar";
import { NoteSidebar } from "./note-sidebar";

interface WritingSidebarProps {
  projectId: string;
  onChapterSelect: (chapterId: string, chapterTitle: string) => void;
  onNoteSelect: (noteId: string, noteTitle: string) => void;
  onAddToConversation?: (markup: string) => void;
  isAgentLocked?: boolean;
  compact?: boolean;
  initialCurrentChapterNavigationKey?: string | null;
}

export function WritingSidebar({
  projectId,
  onChapterSelect,
  onNoteSelect,
  onAddToConversation,
  isAgentLocked = false,
  compact = false,
  initialCurrentChapterNavigationKey = null,
}: WritingSidebarProps) {
  const { t } = useTranslation();
  const sidebarView = useWritingStore((s) => s.sidebarView);
  const setSidebarView = useWritingStore((s) => s.setSidebarView);

  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "var(--color-background)",
      }}
    >
      <div
        style={{
          padding: compact ? "8px 8px" : "12px 12px",
          borderBottom: "1px solid var(--gray-a4)",
        }}
      >
        <SegmentedControl.Root
          value={sidebarView}
          onValueChange={(value) => setSidebarView(value as "chapters" | "notes")}
          size="2"
          style={{ width: "100%" }}
        >
          <SegmentedControl.Item value="chapters">{t("writing.chapters")}</SegmentedControl.Item>
          <SegmentedControl.Item value="notes">{t("writing.notes")}</SegmentedControl.Item>
        </SegmentedControl.Root>
      </div>

      {sidebarView === "chapters" ? (
        <ChapterSidebar
          projectId={projectId}
          onChapterSelect={onChapterSelect}
          onAddToConversation={onAddToConversation}
          isAgentLocked={isAgentLocked}
          compact={compact}
          initialCurrentChapterNavigationKey={initialCurrentChapterNavigationKey}
        />
      ) : (
        <NoteSidebar
          projectId={projectId}
          onNoteSelect={onNoteSelect}
          onAddToConversation={onAddToConversation}
          isAgentLocked={isAgentLocked}
          compact={compact}
        />
      )}
    </div>
  );
}

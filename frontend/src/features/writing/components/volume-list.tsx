import { Box, Flex, Skeleton, Text } from "@radix-ui/themes";
import { BookOpen } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { SummaryStatusItem } from "@/lib/api-client";
import type { ChapterListItem, VolumeWithChapters } from "@/lib/chapter.types";

import { GroupedVolumeList } from "./grouped-volume-list";
import type { GroupedVolumeListScrollRequest } from "./grouped-volume-list-focus";

interface VolumeListProps {
  projectId: string;
  volumes: VolumeWithChapters[];
  isLoading: boolean;
  onAddToConversation?: (markup: string) => void;
  scrollRequest?: GroupedVolumeListScrollRequest | null;
  expandedVolumeIds: Set<string>;
  renamingVolumeId: string | null;
  isAgentLocked?: boolean;
  compact?: boolean;
  initialCurrentChapterNavigationKey?: string | null;
  summaryStatusMap?: Record<string, SummaryStatusItem>;
  onToggleVolume: (volumeId: string) => void;
  onStartRenameVolume: (volumeId: string) => void;
  onRenameVolume: (volumeId: string, title: string) => void;
  onCancelRenameVolume: () => void;
  onEditVolumeDescription: (volume: VolumeWithChapters) => void;
  onCreateChapterInVolume: (volumeId: string) => void;
  onMoveVolumeUp: (volume: VolumeWithChapters) => void;
  onMoveVolumeDown: (volume: VolumeWithChapters) => void;
  onDeleteVolume: (volume: VolumeWithChapters) => void;
  onChapterSelect: (chapterId: string) => void;
  onOpenInNewTab: (chapterId: string, title: string) => void;
  onDuplicate: (chapterId: string, title: string) => void;
  onRenameChapter: (chapterId: string, title: string) => void;
  onMoveChapterToVolume: (chapter: ChapterListItem) => void;
  onDeleteChapter: (chapter: ChapterListItem) => void;
  onLockedAction?: () => void;
}

export function VolumeList({
  projectId,
  volumes,
  isLoading,
  onAddToConversation,
  scrollRequest = null,
  expandedVolumeIds,
  renamingVolumeId,
  isAgentLocked = false,
  compact = false,
  initialCurrentChapterNavigationKey = null,
  summaryStatusMap = {},
  onToggleVolume,
  onStartRenameVolume,
  onRenameVolume,
  onCancelRenameVolume,
  onEditVolumeDescription,
  onCreateChapterInVolume,
  onMoveVolumeUp,
  onMoveVolumeDown,
  onDeleteVolume,
  onChapterSelect,
  onOpenInNewTab,
  onDuplicate,
  onRenameChapter,
  onMoveChapterToVolume,
  onDeleteChapter,
  onLockedAction,
}: VolumeListProps) {
  const { t } = useTranslation();

  if (isLoading) {
    return (
      <Box p="2">
        {[1, 2, 3].map((item) => (
          <Box
            key={item}
            p="3"
          >
            <Skeleton
              height="16px"
              width="55%"
              mb="2"
            />
            <Skeleton
              height="12px"
              width="36%"
            />
          </Box>
        ))}
      </Box>
    );
  }

  if (volumes.length === 0) {
    return (
      <Flex
        direction="column"
        align="center"
        justify="center"
        py="9"
        gap="3"
        style={{ color: "var(--gray-9)" }}
      >
        <BookOpen size={40} />
        <Text
          size="2"
          color="gray"
        >
          {t("volume.empty")}
        </Text>
      </Flex>
    );
  }

  return (
    <GroupedVolumeList
      projectId={projectId}
      volumes={volumes}
      scrollRequest={scrollRequest}
      expandedVolumeIds={expandedVolumeIds}
      renamingVolumeId={renamingVolumeId}
      isAgentLocked={isAgentLocked}
      compact={compact}
      initialCurrentChapterNavigationKey={initialCurrentChapterNavigationKey}
      summaryStatusMap={summaryStatusMap}
      onToggleVolume={onToggleVolume}
      onStartRenameVolume={onStartRenameVolume}
      onRenameVolume={onRenameVolume}
      onCancelRenameVolume={onCancelRenameVolume}
      onEditVolumeDescription={onEditVolumeDescription}
      onCreateChapterInVolume={onCreateChapterInVolume}
      onMoveVolumeUp={onMoveVolumeUp}
      onMoveVolumeDown={onMoveVolumeDown}
      onDeleteVolume={onDeleteVolume}
      onChapterSelect={onChapterSelect}
      onOpenInNewTab={onOpenInNewTab}
      onDuplicate={onDuplicate}
      onRenameChapter={onRenameChapter}
      onMoveChapterToVolume={onMoveChapterToVolume}
      onDeleteChapter={onDeleteChapter}
      onAddToConversation={onAddToConversation}
      onLockedAction={onLockedAction}
    />
  );
}

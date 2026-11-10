import { Button, Flex, Text } from "@radix-ui/themes";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import { Spinner, toast } from "@/components";
import { CharacterEditor } from "@/features/characters/components/character-editor";
import { EntryEditor } from "@/features/world-info/components/entry-editor";
import { ChapterEditor } from "@/features/writing/components/chapter-editor";
import {
  fetchCharacter,
  fetchWorldInfoEntries,
  fetchWorldInfoEntry,
  updateCharacter,
} from "@/lib/api-client";

export type SidebarEntityKind = "chapter" | "character" | "world_info_entry";

interface SidebarEntityEditorProps {
  kind: SidebarEntityKind;
  entityId: string;
  isAgentLocked: boolean;
  onTitleChange: (title: string) => void;
  onAddToConversation: (markup: string) => void;
}

export function SidebarEntityEditor(props: SidebarEntityEditorProps) {
  if (props.kind === "chapter") {
    return (
      <ChapterEditor
        chapterId={props.entityId}
        isAgentLocked={props.isAgentLocked}
        onChapterUpdate={(chapter) => props.onTitleChange(chapter.title)}
        onAddToConversation={props.onAddToConversation}
      />
    );
  }
  if (props.kind === "character") return <SidebarCharacterEditor {...props} />;
  return <SidebarWorldInfoEditor {...props} />;
}

function SidebarCharacterEditor({
  entityId,
  isAgentLocked,
  onTitleChange,
}: SidebarEntityEditorProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const lockRef = useRef(isAgentLocked);
  lockRef.current = isAgentLocked;
  const query = useQuery({
    queryKey: ["character", entityId, "right-sidebar"],
    queryFn: ({ signal }) => fetchCharacter(entityId, signal),
  });
  const name = query.data?.name;
  useEffect(() => {
    if (name) onTitleChange(name);
  }, [name, onTitleChange]);

  if (query.isPending) return <SidebarEditorLoading />;
  if (query.isError) return <SidebarEditorError onRetry={() => void query.refetch()} />;
  return (
    <CharacterEditor
      key={entityId}
      character={query.data}
      isAgentLocked={isAgentLocked}
      canSave={() => !lockRef.current}
      onSave={async (data) => {
        try {
          const updated = await updateCharacter(entityId, data);
          await queryClient.cancelQueries({ queryKey: ["character", entityId] }, { revert: false });
          queryClient.setQueriesData({ queryKey: ["character", entityId] }, updated);
          void queryClient.invalidateQueries({ queryKey: ["characters", updated.projectId] });
          void queryClient.invalidateQueries({ queryKey: ["character-graph", updated.projectId] });
          return updated;
        } catch (error) {
          const status = (error as { response?: { status?: number } }).response?.status;
          toast.error(status === 409 ? t("characters.nameExists") : t("characters.updateFailed"));
          throw error;
        }
      }}
    />
  );
}

function SidebarWorldInfoEditor({
  entityId,
  isAgentLocked,
  onTitleChange,
}: SidebarEntityEditorProps) {
  const lockRef = useRef(isAgentLocked);
  lockRef.current = isAgentLocked;
  const query = useQuery({
    queryKey: ["world-info-entry-detail", entityId],
    queryFn: ({ signal }) => fetchWorldInfoEntry(entityId, signal),
  });
  const worldInfoId = query.data?.worldInfoId;
  const entriesQuery = useQuery({
    queryKey: ["world-info-entries", worldInfoId],
    queryFn: () => fetchWorldInfoEntries(worldInfoId!),
    enabled: Boolean(worldInfoId),
  });
  const name = query.data?.name;
  useEffect(() => {
    if (name) onTitleChange(name);
  }, [name, onTitleChange]);

  if (query.isError || entriesQuery.isError) {
    return (
      <SidebarEditorError
        onRetry={() => {
          void query.refetch();
          void entriesQuery.refetch();
        }}
      />
    );
  }
  if (query.isPending || entriesQuery.isPending) return <SidebarEditorLoading />;
  return (
    <EntryEditor
      key={entityId}
      entry={query.data}
      worldInfoId={query.data.worldInfoId}
      entries={entriesQuery.data.items}
      isAgentLocked={isAgentLocked}
      canSave={() => !lockRef.current}
    />
  );
}

function SidebarEditorLoading() {
  return (
    <Flex
      className="right-sidebar-placeholder"
      align="center"
      justify="center"
    >
      <Spinner />
    </Flex>
  );
}

function SidebarEditorError({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation();
  return (
    <Flex
      className="right-sidebar-placeholder"
      direction="column"
      align="center"
      justify="center"
      gap="3"
    >
      <Text
        size="2"
        color="gray"
      >
        {t("rightSidebar.loadFailed")}
      </Text>
      <Button
        variant="soft"
        onClick={onRetry}
      >
        {t("common.retry")}
      </Button>
    </Flex>
  );
}

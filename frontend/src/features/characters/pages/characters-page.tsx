import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertDialog, Box, Button, Dialog, Flex, Text } from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router";
import { useTranslation } from "react-i18next";
import { Group, Panel, Separator } from "react-resizable-panels";

import { toast } from "@/components/toast";
import {
  batchDeleteCharacters,
  batchFavoriteCharacters,
  createCharacter,
  deleteCharacter,
  fetchCharacter,
  fetchCharactersByProject,
  fetchProjects,
  updateCharacter,
} from "@/lib/api-client";
import { getPreference, setPreference } from "@/lib/local-db";
import { countTokens } from "@/lib/tiktoken-utils";
import type { Character, CharacterListItem, CharacterListResponse } from "@/lib/character.types";
import { useCharactersStore } from "../store/use-characters-store";
import { CharacterEditor } from "../components/character-editor";
import { CharacterList } from "../components/character-list";
import { CharacterProfileDialog } from "../components/character-profile-dialog";
import "./characters-page.css";

const LAST_PROJECT_KEY = "characters.lastProjectId";
const LAST_CHARACTER_KEY = "characters.lastCharacterId";

function toCharacterListItem(character: Character): CharacterListItem {
  return {
    id: character.id,
    projectId: character.projectId,
    name: character.name,
    imageUrl: character.imageUrl,
    tokenCount: countTokens(character.description),
    isFavorited: character.isFavorited,
    createdAt: character.createdAt,
    updatedAt: character.updatedAt,
  };
}

function sortCharacters(characters: CharacterListItem[]): CharacterListItem[] {
  return [...characters].sort((a, b) => {
    const favoriteComparison = Number(b.isFavorited) - Number(a.isFavorited);
    if (favoriteComparison !== 0) return favoriteComparison;
    return b.updatedAt.localeCompare(a.updatedAt);
  });
}

export function CharactersPage() {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const {
    currentProjectId,
    currentCharacterId,
    isListOpen,
    setCurrentProject,
    setCurrentCharacter,
    setListOpen,
  } = useCharactersStore();
  const [profileCharacter, setProfileCharacter] = useState<CharacterListItem | null>(null);
  const [deleteCharacterTarget, setDeleteCharacterTarget] = useState<CharacterListItem | null>(null);
  const [isMobile, setIsMobile] = useState(false);
  const [selectedCharacterLoadVersion, setSelectedCharacterLoadVersion] = useState(0);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const { data: projectsData } = useQuery({
    queryKey: ["projects", "characters-page"],
    queryFn: () => fetchProjects({ page: 1, pageSize: 100 }),
  });

  const projects = useMemo(() => projectsData?.items ?? [], [projectsData?.items]);

  useEffect(() => {
    const initProject = async () => {
      if (currentProjectId || projects.length === 0) return;
      const projectIdFromUrl = searchParams.get("projectId");
      const cachedProjectId = await getPreference(LAST_PROJECT_KEY);
      const nextProjectId =
        (projectIdFromUrl && projects.some((project) => project.id === projectIdFromUrl)
          ? projectIdFromUrl
          : null) ??
        (cachedProjectId && projects.some((project) => project.id === cachedProjectId)
          ? cachedProjectId
          : null) ??
        projects[0]?.id ??
        null;
      setCurrentProject(nextProjectId);
    };

    void initProject();
  }, [currentProjectId, projects, searchParams, setCurrentProject]);

  useEffect(() => {
    if (currentProjectId) void setPreference(LAST_PROJECT_KEY, currentProjectId);
  }, [currentProjectId]);

  const { data: charactersData, isLoading: isCharactersLoading } = useQuery({
    queryKey: ["characters", currentProjectId],
    queryFn: () => fetchCharactersByProject(currentProjectId!, { page: 1, pageSize: 100 }),
    enabled: !!currentProjectId,
    staleTime: 0,
  });

  const characters = useMemo(() => charactersData?.items ?? [], [charactersData?.items]);

  useEffect(() => {
    const restoreCharacter = async () => {
      if (!currentProjectId || currentCharacterId || characters.length === 0) return;
      const cachedCharacterId = await getPreference(LAST_CHARACTER_KEY);
      const nextCharacterId =
        (cachedCharacterId && characters.some((character) => character.id === cachedCharacterId)
          ? cachedCharacterId
          : null) ?? characters[0].id;
      setCurrentCharacter(nextCharacterId);
    };

    void restoreCharacter();
  }, [characters, currentCharacterId, currentProjectId, setCurrentCharacter]);

  useEffect(() => {
    if (currentCharacterId) void setPreference(LAST_CHARACTER_KEY, currentCharacterId);
  }, [currentCharacterId]);

  useEffect(() => {
    if (!currentCharacterId || characters.length === 0) return;
    if (!characters.some((character) => character.id === currentCharacterId)) {
      setCurrentCharacter(characters[0]?.id ?? null);
    }
  }, [characters, currentCharacterId, setCurrentCharacter]);

  const { data: selectedCharacter, isFetching: isCharacterLoading } = useQuery({
    queryKey: ["character", currentCharacterId, selectedCharacterLoadVersion],
    queryFn: () => fetchCharacter(currentCharacterId!),
    enabled: !!currentCharacterId,
    staleTime: 0,
    gcTime: 0,
  });

  const upsertCharacterCache = useCallback(
    (updated: CharacterListItem) => {
      queryClient.setQueryData(
        ["characters", updated.projectId],
        (old: CharacterListResponse | undefined) => {
          if (!old) return old;
          const exists = old.items.some((character) => character.id === updated.id);
          const items = exists
            ? old.items.map((character) => character.id === updated.id ? updated : character)
            : [updated, ...old.items];
          return {
            ...old,
            items: sortCharacters(items),
            total: exists ? old.total : old.total + 1,
          };
        }
      );
    },
    [queryClient]
  );

  const createMutation = useMutation({
    mutationFn: () =>
      createCharacter(currentProjectId!, {
        name: t("characters.untitledCharacter"),
      }),
    onSuccess: (character) => {
      queryClient.invalidateQueries({ queryKey: ["characters", currentProjectId] });
      setCurrentCharacter(character.id);
      setSelectedCharacterLoadVersion((prev) => prev + 1);
      toast.success(t("characters.created"));
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ characterId, data }: { characterId: string; data: Parameters<typeof updateCharacter>[1] }) =>
      updateCharacter(characterId, data),
    onSuccess: (character) => {
      upsertCharacterCache(toCharacterListItem(character));
      queryClient.setQueryData(["character", character.id, selectedCharacterLoadVersion], character);
      queryClient.invalidateQueries({ queryKey: ["characters", character.projectId] });
      setProfileCharacter(null);
    },
    onError: (error) => {
      const status = (error as { response?: { status?: number } }).response?.status;
      toast.error(status === 409 ? t("characters.nameExists") : t("characters.updateFailed"));
    },
  });

  const favoriteMutation = useMutation({
    mutationFn: ({ character, isFavorited }: { character: CharacterListItem; isFavorited: boolean }) =>
      updateCharacter(character.id, { isFavorited }),
    onMutate: ({ character, isFavorited }) => {
      upsertCharacterCache({
        ...character,
        isFavorited,
        updatedAt: new Date().toISOString(),
      });
    },
    onSuccess: (character) => {
      upsertCharacterCache(toCharacterListItem(character));
      queryClient.invalidateQueries({ queryKey: ["characters", character.projectId] });
      toast.success(character.isFavorited ? t("characters.favorited") : t("characters.unfavorited"));
    },
    onError: (_error, { character }) => {
      upsertCharacterCache(character);
      toast.error(t("characters.favoriteFailed"));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (characterId: string) => deleteCharacter(characterId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["characters", currentProjectId] });
      setCurrentCharacter(null);
      setDeleteCharacterTarget(null);
      toast.success(t("characters.deleted"));
    },
  });

  const batchDeleteMutation = useMutation({
    mutationFn: (characterIds: string[]) => batchDeleteCharacters(currentProjectId!, characterIds),
    onSuccess: (_deletedCount, characterIds) => {
      queryClient.invalidateQueries({ queryKey: ["characters", currentProjectId] });
      if (currentCharacterId && characterIds.includes(currentCharacterId)) setCurrentCharacter(null);
      toast.success(t("characters.deleted"));
    },
  });

  const batchFavoriteMutation = useMutation({
    mutationFn: ({ characterIds, isFavorited }: { characterIds: string[]; isFavorited: boolean }) =>
      batchFavoriteCharacters(currentProjectId!, characterIds, isFavorited),
    onMutate: ({ characterIds, isFavorited }) => {
      characters
        .filter((character) => characterIds.includes(character.id))
        .forEach((character) => {
          upsertCharacterCache({
            ...character,
            isFavorited,
            updatedAt: new Date().toISOString(),
          });
        });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["characters", currentProjectId] });
      toast.success(t("characters.favoriteUpdated"));
    },
    onError: () => {
      queryClient.invalidateQueries({ queryKey: ["characters", currentProjectId] });
      toast.error(t("characters.favoriteFailed"));
    },
  });

  const handleSelectProject = (projectId: string) => {
    setCurrentProject(projectId || null);
  };

  const handleSelectCharacter = (characterId: string) => {
    queryClient.removeQueries({ queryKey: ["character", characterId] });
    setCurrentCharacter(characterId);
    setSelectedCharacterLoadVersion((prev) => prev + 1);
    setListOpen(false);
  };

  const list = (
    <CharacterList
      characters={characters}
      projectId={currentProjectId ?? ""}
      selectedCharacterId={currentCharacterId}
      isLoading={isCharactersLoading}
      projects={projects}
      currentProjectId={currentProjectId ?? ""}
      onSelectProject={handleSelectProject}
      onCreateCharacter={() => createMutation.mutate()}
      onSelectCharacter={handleSelectCharacter}
      onEditProfile={setProfileCharacter}
      onDeleteCharacter={setDeleteCharacterTarget}
      onToggleFavorite={(character, isFavorited) => {
        favoriteMutation.mutate({ character, isFavorited });
      }}
      onBatchDelete={(characterIds) => batchDeleteMutation.mutate(characterIds)}
      onBatchFavorite={(characterIds, isFavorited) => {
        batchFavoriteMutation.mutate({ characterIds, isFavorited });
      }}
    />
  );

  const editorContent = (
    <CharacterEditor
      key={selectedCharacter?.id ?? "empty"}
      character={selectedCharacter ?? null}
      isSaving={updateMutation.isPending}
      isLoading={isCharacterLoading}
      onSave={async (data) => {
        if (!selectedCharacter) return;
        await updateMutation.mutateAsync({ characterId: selectedCharacter.id, data });
      }}
    />
  );

  return (
    <Flex className="characters-page" direction="column">
      {currentProjectId && !isMobile ? (
        <Group orientation="horizontal" className="characters-page-body">
          <Panel id="characters-list" defaultSize={300} minSize={250} maxSize={400} collapsible={false}>
            <Box className="characters-panel characters-page-list-panel">{list}</Box>
          </Panel>

          <Separator className="resize-handle characters-page-separator" />

          <Panel id="characters-editor" minSize={30}>
            <Box className="characters-panel characters-editor-shell">{editorContent}</Box>
          </Panel>

          <Separator className="resize-handle characters-page-separator" />

          <Panel id="characters-right" defaultSize={350} minSize={260} maxSize={450} collapsible={false}>
          </Panel>
        </Group>
      ) : currentProjectId ? (
        <Box className="characters-page-body characters-page-body--mobile">
          <Box className="characters-panel characters-editor-shell">{editorContent}</Box>
        </Box>
      ) : (
        <Flex className="characters-project-empty" align="center" justify="center" direction="column" gap="2">
          <Text size="3" weight="medium">{t("characters.noProject")}</Text>
          <Text size="2" color="gray">{t("characters.noProjectHint")}</Text>
        </Flex>
      )}

      <Dialog.Root open={isListOpen} onOpenChange={setListOpen}>
        <Dialog.Content className="characters-mobile-dialog" maxWidth="360px">
          <Dialog.Title>{t("characters.listTitle")}</Dialog.Title>
          {list}
        </Dialog.Content>
      </Dialog.Root>

      <CharacterProfileDialog
        character={profileCharacter}
        open={!!profileCharacter}
        isSaving={updateMutation.isPending}
        onOpenChange={(open) => {
          if (!open) setProfileCharacter(null);
        }}
        onSubmit={(data) => {
          if (!profileCharacter) return;
          updateMutation.mutate({ characterId: profileCharacter.id, data });
        }}
      />

      <AlertDialog.Root open={!!deleteCharacterTarget} onOpenChange={(open) => {
        if (!open) setDeleteCharacterTarget(null);
      }}>
        <AlertDialog.Content maxWidth="420px">
          <AlertDialog.Title>{t("characters.deleteCharacter")}</AlertDialog.Title>
          <AlertDialog.Description>
            {t("characters.deleteConfirm", { name: deleteCharacterTarget?.name ?? "" })}
          </AlertDialog.Description>
          <Flex justify="end" gap="3" mt="5">
            <AlertDialog.Cancel>
              <Button variant="soft" color="gray">{t("common.cancel")}</Button>
            </AlertDialog.Cancel>
            <AlertDialog.Action>
              <Button
                color="red"
                disabled={deleteMutation.isPending}
                onClick={() => {
                  if (deleteCharacterTarget) deleteMutation.mutate(deleteCharacterTarget.id);
                }}
              >
                {t("common.delete")}
              </Button>
            </AlertDialog.Action>
          </Flex>
        </AlertDialog.Content>
      </AlertDialog.Root>
    </Flex>
  );
}

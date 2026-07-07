import {
  Box,
  Button,
  Checkbox,
  Dialog,
  DropdownMenu,
  Flex,
  IconButton,
  Skeleton,
  Text,
  Tooltip,
} from "@radix-ui/themes";
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  CheckSquare,
  ListChecks,
  Pencil,
  Plus,
  Search,
  Star,
  StarOff,
  Trash2,
  UserRound,
} from "lucide-react";
import { motion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ProjectSelectField, Spinner } from "@/components";
import { ContextMenu, type ContextMenuItem } from "@/components/context-menu";
import type { CharacterListItem } from "@/lib/character.types";
import type { Project } from "@/lib/project.types";
import { formatRelativeTime } from "@/lib/time-utils";

import { CharacterSearchPopover } from "./character-search-popover";

const loadedAvatarUrls = new Set<string>();

interface CharacterListProps {
  characters: CharacterListItem[];
  projectId: string;
  projects: Project[];
  currentProjectId: string;
  selectedCharacterId: string | null;
  isLoading?: boolean;
  onSelectProject: (projectId: string) => void;
  onCreateCharacter: () => void;
  onSelectCharacter: (characterId: string) => void;
  onEditProfile: (character: CharacterListItem) => void;
  onDeleteCharacter: (character: CharacterListItem) => void;
  onToggleFavorite: (character: CharacterListItem, isFavorited: boolean) => void;
  onBatchDelete: (characterIds: string[]) => void;
  onBatchFavorite: (characterIds: string[], isFavorited: boolean) => void;
}

interface MenuPosition {
  x: number;
  y: number;
}

type SortField = "favorite" | "updatedAt" | "tokenCount" | "name";
type SortDirection = "asc" | "desc";

function getAvatarFallback(name: string): string {
  return name.trim().slice(0, 1).toUpperCase() || "?";
}

function CharacterListAvatar({
  character,
  onEditProfile,
}: {
  character: CharacterListItem;
  onEditProfile: (character: CharacterListItem) => void;
}) {
  const [isLoaded, setIsLoaded] = useState(
    () => !character.imageUrl || loadedAvatarUrls.has(character.imageUrl),
  );

  return (
    <button
      type="button"
      className="characters-list-avatar-button"
      onClick={(event) => {
        event.stopPropagation();
        onEditProfile(character);
      }}
      aria-label="edit character profile"
    >
      {character.imageUrl ? (
        <>
          {!isLoaded && (
            <Spinner
              size={18}
              className="characters-list-avatar-spinner"
            />
          )}
          <img
            src={character.imageUrl}
            alt=""
            className="characters-list-avatar-image"
            data-loaded={isLoaded ? "true" : "false"}
            onLoad={() => {
              if (character.imageUrl) loadedAvatarUrls.add(character.imageUrl);
              setIsLoaded(true);
            }}
          />
        </>
      ) : (
        <Text
          size="1"
          weight="medium"
        >
          {getAvatarFallback(character.name)}
        </Text>
      )}
      <span className="characters-list-avatar-overlay">
        <Pencil size={14} />
      </span>
    </button>
  );
}

export function CharacterList({
  characters,
  projectId,
  projects,
  currentProjectId,
  selectedCharacterId,
  isLoading = false,
  onSelectProject,
  onCreateCharacter,
  onSelectCharacter,
  onEditProfile,
  onDeleteCharacter,
  onToggleFavorite,
  onBatchDelete,
  onBatchFavorite,
}: CharacterListProps) {
  const { t } = useTranslation();
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null);
  const [menuCharacterId, setMenuCharacterId] = useState<string | null>(null);
  const [isMultiSelect, setIsMultiSelect] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchDeleteDialogOpen, setBatchDeleteDialogOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchExpanded, setSearchExpanded] = useState(false);
  const [sortField, setSortField] = useState<SortField>("favorite");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const searchContainerRef = useRef<HTMLDivElement | null>(null);

  const sortedCharacters = useMemo(() => {
    return [...characters].sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case "favorite":
          comparison = Number(a.isFavorited) - Number(b.isFavorited);
          if (comparison === 0) comparison = a.updatedAt.localeCompare(b.updatedAt);
          break;
        case "updatedAt":
          comparison = a.updatedAt.localeCompare(b.updatedAt);
          break;
        case "tokenCount":
          comparison = a.tokenCount - b.tokenCount;
          break;
        case "name":
          comparison = a.name.localeCompare(b.name, "zh-CN");
          break;
      }
      return sortDirection === "asc" ? comparison : -comparison;
    });
  }, [characters, sortDirection, sortField]);

  useEffect(() => {
    if (searchExpanded && searchContainerRef.current) {
      const input = searchContainerRef.current.querySelector("input");
      input?.focus();
    }
  }, [searchExpanded]);

  const menuCharacter = useMemo(
    () => characters.find((character) => character.id === menuCharacterId) ?? null,
    [characters, menuCharacterId],
  );

  const handleCloseContextMenu = useCallback(() => {
    setMenuPosition(null);
    setMenuCharacterId(null);
  }, []);

  const handleContextMenu = useCallback(
    (event: React.MouseEvent, character: CharacterListItem) => {
      event.preventDefault();
      setMenuCharacterId(character.id);
      if (isMultiSelect) {
        setSelectedIds((prev) => {
          if (prev.has(character.id)) return prev;
          const next = new Set(prev);
          next.add(character.id);
          return next;
        });
      }
      setMenuPosition({ x: event.clientX, y: event.clientY });
    },
    [isMultiSelect],
  );

  const handleToggleMultiSelect = useCallback(() => {
    setIsMultiSelect((prev) => {
      if (prev) setSelectedIds(new Set());
      return !prev;
    });
  }, []);

  const handleCheckCharacter = useCallback((characterId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(characterId)) {
        next.delete(characterId);
      } else {
        next.add(characterId);
      }
      return next;
    });
  }, []);

  const handleSelectAll = useCallback(() => {
    setSelectedIds(new Set(sortedCharacters.map((character) => character.id)));
  }, [sortedCharacters]);

  const handleDeselectAll = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const handleSortChange = useCallback(
    (field: SortField) => {
      if (sortField === field) {
        setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
        return;
      }
      setSortField(field);
      setSortDirection("desc");
    },
    [sortField],
  );

  function getSortIcon(field: SortField) {
    if (sortField !== field) return null;
    return sortDirection === "asc" ? <ArrowUp size={12} /> : <ArrowDown size={12} />;
  }

  const handleSearchChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value);
    if (event.target.value.trim()) setSearchOpen(true);
  }, []);

  const handleSearchToggle = useCallback(() => {
    setSearchExpanded((prev) => {
      if (prev) {
        setSearchOpen(false);
        return false;
      }
      return true;
    });
    if (!searchExpanded && searchQuery.trim()) setSearchOpen(true);
  }, [searchExpanded, searchQuery]);

  const handleSearchBlur = useCallback(() => {
    if (!searchQuery.trim()) {
      setSearchExpanded(false);
    }
  }, [searchQuery]);

  const handlePopoverOpenChange = useCallback((open: boolean) => {
    setSearchOpen(open);
    if (!open) setSearchExpanded(false);
  }, []);

  const handleBatchDeleteConfirm = useCallback(() => {
    if (selectedIds.size === 0) return;
    onBatchDelete(Array.from(selectedIds));
    setSelectedIds(new Set());
    setIsMultiSelect(false);
    setBatchDeleteDialogOpen(false);
  }, [onBatchDelete, selectedIds]);

  const handleBatchFavorite = useCallback(
    (isFavorited: boolean) => {
      if (selectedIds.size === 0) return;
      onBatchFavorite(Array.from(selectedIds), isFavorited);
      handleCloseContextMenu();
    },
    [handleCloseContextMenu, onBatchFavorite, selectedIds],
  );

  const menuItems = useMemo<ContextMenuItem[]>(() => {
    if (isMultiSelect) {
      return [
        {
          id: "favorite-selected",
          label: t("characters.favoriteSelected"),
          icon: Star,
          onClick: () => handleBatchFavorite(true),
        },
        {
          id: "unfavorite-selected",
          label: t("characters.unfavoriteSelected"),
          icon: StarOff,
          onClick: () => handleBatchFavorite(false),
        },
        {
          id: "delete-selected",
          label: t("characters.deleteSelected"),
          icon: Trash2,
          danger: true,
          onClick: () => setBatchDeleteDialogOpen(true),
        },
      ];
    }

    if (!menuCharacter) return [];

    return [
      {
        id: "edit-profile",
        label: t("characters.editProfile"),
        icon: Pencil,
        onClick: () => {
          handleCloseContextMenu();
          onEditProfile(menuCharacter);
        },
      },
      {
        id: "favorite",
        label: menuCharacter.isFavorited ? t("characters.unfavorite") : t("characters.favorite"),
        icon: menuCharacter.isFavorited ? StarOff : Star,
        onClick: () => {
          handleCloseContextMenu();
          onToggleFavorite(menuCharacter, !menuCharacter.isFavorited);
        },
      },
      {
        id: "delete",
        label: t("characters.deleteCharacter"),
        icon: Trash2,
        danger: true,
        onClick: () => {
          handleCloseContextMenu();
          onDeleteCharacter(menuCharacter);
        },
      },
    ];
  }, [
    handleBatchFavorite,
    handleCloseContextMenu,
    isMultiSelect,
    menuCharacter,
    onDeleteCharacter,
    onEditProfile,
    onToggleFavorite,
    t,
  ]);

  return (
    <>
      <Flex
        className="characters-list"
        direction="column"
      >
        <Box
          p="3"
          className="characters-list-header"
        >
          <Flex
            direction="column"
            gap="2"
          >
            <Box className="characters-list-project-select">
              <ProjectSelectField
                projects={projects}
                value={currentProjectId}
                onChange={onSelectProject}
                showNoneOption={false}
                placeholder={t("characters.selectProject")}
              />
            </Box>

            <Flex
              gap="2"
              align="center"
            >
              <Box
                ref={searchContainerRef}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 0,
                  height: "var(--space-6)",
                  paddingRight: searchExpanded ? "var(--space-2)" : 0,
                  border: "1px solid transparent",
                  borderColor: searchExpanded ? "var(--gray-a7)" : "transparent",
                  borderRadius: "max(var(--radius-2), var(--radius-full))",
                  background: searchExpanded ? "var(--color-surface)" : "transparent",
                  flex: searchExpanded ? 1 : undefined,
                  minWidth: 0,
                  position: "relative",
                  transition:
                    "border-color 0.15s ease, background 0.15s ease, padding-right 0.15s ease",
                }}
              >
                <CharacterSearchPopover
                  projectId={projectId}
                  query={searchQuery}
                  open={searchOpen}
                  onOpenChange={handlePopoverOpenChange}
                  onNavigateToMatch={onSelectCharacter}
                >
                  <Box
                    style={{
                      position: "absolute",
                      inset: 0,
                      pointerEvents: "none",
                    }}
                  />
                </CharacterSearchPopover>
                <IconButton
                  variant="ghost"
                  size="2"
                  aria-label={t("characters.search")}
                  onClick={searchExpanded ? undefined : handleSearchToggle}
                  style={{
                    flexShrink: 0,
                    opacity: searchExpanded ? 0.5 : 1,
                    transition: "opacity 0.15s ease",
                    cursor: searchExpanded ? "default" : undefined,
                  }}
                >
                  <Search size={16} />
                </IconButton>
                <motion.div
                  animate={{ width: searchExpanded ? 200 : 0, opacity: searchExpanded ? 1 : 0 }}
                  transition={{ duration: 0.15, ease: "easeOut" }}
                  style={{ overflow: "hidden" }}
                >
                  <input
                    type="text"
                    value={searchQuery}
                    placeholder={t("characters.searchPlaceholder")}
                    onChange={handleSearchChange}
                    onFocus={() => {
                      if (searchQuery.trim()) setSearchOpen(true);
                    }}
                    onBlur={handleSearchBlur}
                    style={{
                      width: 200,
                      border: "none",
                      outline: "none",
                      background: "transparent",
                      fontSize: "var(--font-size-2)",
                      lineHeight: "var(--line-height-2)",
                      color: "var(--gray-12)",
                      padding: 0,
                    }}
                  />
                </motion.div>
              </Box>

              {!searchExpanded && (
                <>
                  <Box style={{ flex: 1 }} />

                  {isMultiSelect ? (
                    <Tooltip
                      content={
                        selectedIds.size > 0
                          ? t("characters.deselectAll")
                          : t("characters.selectAll")
                      }
                    >
                      <IconButton
                        variant="ghost"
                        size="2"
                        onClick={selectedIds.size > 0 ? handleDeselectAll : handleSelectAll}
                      >
                        <CheckSquare size={16} />
                      </IconButton>
                    </Tooltip>
                  ) : (
                    <DropdownMenu.Root>
                      <DropdownMenu.Trigger>
                        <IconButton
                          variant="ghost"
                          size="2"
                          aria-label={t("characters.sort")}
                        >
                          <ArrowUpDown size={16} />
                        </IconButton>
                      </DropdownMenu.Trigger>
                      <DropdownMenu.Content align="end">
                        <DropdownMenu.Item onClick={() => handleSortChange("favorite")}>
                          <Flex
                            align="center"
                            justify="between"
                            width="100%"
                          >
                            <Text>{t("characters.sortByFavorite")}</Text>
                            {getSortIcon("favorite")}
                          </Flex>
                        </DropdownMenu.Item>
                        <DropdownMenu.Item onClick={() => handleSortChange("updatedAt")}>
                          <Flex
                            align="center"
                            justify="between"
                            width="100%"
                          >
                            <Text>{t("characters.sortByUpdated")}</Text>
                            {getSortIcon("updatedAt")}
                          </Flex>
                        </DropdownMenu.Item>
                        <DropdownMenu.Item onClick={() => handleSortChange("tokenCount")}>
                          <Flex
                            align="center"
                            justify="between"
                            width="100%"
                          >
                            <Text>{t("characters.sortByTokens")}</Text>
                            {getSortIcon("tokenCount")}
                          </Flex>
                        </DropdownMenu.Item>
                        <DropdownMenu.Item onClick={() => handleSortChange("name")}>
                          <Flex
                            align="center"
                            justify="between"
                            width="100%"
                          >
                            <Text>{t("characters.sortByName")}</Text>
                            {getSortIcon("name")}
                          </Flex>
                        </DropdownMenu.Item>
                      </DropdownMenu.Content>
                    </DropdownMenu.Root>
                  )}

                  <Tooltip
                    content={
                      isMultiSelect
                        ? t("characters.multiselectExit")
                        : t("characters.multiselectEnter")
                    }
                  >
                    <IconButton
                      variant={isMultiSelect ? "solid" : "ghost"}
                      size="2"
                      onClick={handleToggleMultiSelect}
                    >
                      <ListChecks size={16} />
                    </IconButton>
                  </Tooltip>
                </>
              )}
            </Flex>

            {isMultiSelect ? (
              <Tooltip content={t("characters.deleteSelectedTooltip")}>
                <IconButton
                  size="2"
                  variant="solid"
                  color="red"
                  disabled={selectedIds.size === 0}
                  onClick={() => setBatchDeleteDialogOpen(true)}
                  style={{ width: "100%" }}
                >
                  <Trash2 size={16} />
                  <Text
                    size="2"
                    ml="1"
                  >
                    {t("characters.deleteSelected")}
                  </Text>
                </IconButton>
              </Tooltip>
            ) : (
              <Tooltip content={t("characters.newCharacter")}>
                <IconButton
                  size="2"
                  variant="soft"
                  onClick={onCreateCharacter}
                  style={{ width: "100%" }}
                >
                  <Plus size={16} />
                  <Text
                    size="2"
                    ml="1"
                  >
                    {t("characters.newCharacter")}
                  </Text>
                </IconButton>
              </Tooltip>
            )}
          </Flex>
        </Box>

        <Box className="characters-list-body">
          {isLoading ? (
            <Flex
              direction="column"
              gap="0"
            >
              {Array.from({ length: 8 }).map((_, index) => (
                <Box
                  key={index}
                  p="3"
                  style={{ borderBottom: "1px solid var(--gray-a5)" }}
                >
                  <Flex
                    align="center"
                    gap="2"
                    justify="between"
                  >
                    <Skeleton
                      width="32px"
                      height="32px"
                      style={{ borderRadius: 999 }}
                    />
                    <Flex
                      direction="column"
                      gap="1"
                      style={{ flex: 1, minWidth: 0 }}
                    >
                      <Skeleton
                        height="14px"
                        width={`${50 + (index % 4) * 12}%`}
                        style={{ maxWidth: 200 }}
                      />
                      <Skeleton
                        height="12px"
                        width="120px"
                      />
                    </Flex>
                    <Skeleton
                      width="20px"
                      height="20px"
                    />
                  </Flex>
                </Box>
              ))}
            </Flex>
          ) : characters.length === 0 ? (
            <Flex
              className="characters-empty"
              direction="column"
              align="center"
              justify="center"
              gap="2"
              py="6"
            >
              <UserRound size={28} />
              <Text
                size="2"
                color="gray"
              >
                {t("characters.empty")}
              </Text>
              <Button
                size="2"
                variant="soft"
                onClick={onCreateCharacter}
              >
                {t("characters.newCharacter")}
              </Button>
            </Flex>
          ) : (
            <Flex
              direction="column"
              width="100%"
              style={{ minWidth: 0 }}
            >
              {sortedCharacters.map((character) => {
                const isSelected = character.id === selectedCharacterId;
                const isChecked = selectedIds.has(character.id);

                return (
                  <Box
                    key={character.id}
                    className="characters-list-item"
                    data-state={isSelected ? "selected" : "idle"}
                    role="button"
                    tabIndex={0}
                    onClick={() => {
                      if (isMultiSelect) {
                        handleCheckCharacter(character.id);
                        return;
                      }
                      onSelectCharacter(character.id);
                    }}
                    onKeyDown={(event) => {
                      if (event.key !== "Enter" && event.key !== " ") return;
                      event.preventDefault();
                      if (isMultiSelect) {
                        handleCheckCharacter(character.id);
                        return;
                      }
                      onSelectCharacter(character.id);
                    }}
                    onContextMenu={(event) => handleContextMenu(event, character)}
                  >
                    <Flex
                      className="characters-list-item-row"
                      align="center"
                      gap="2"
                      justify="between"
                    >
                      {isMultiSelect ? (
                        <Flex
                          className="characters-list-leading"
                          align="center"
                          justify="center"
                          onClick={(event) => event.stopPropagation()}
                        >
                          <Checkbox
                            checked={isChecked}
                            onCheckedChange={() => handleCheckCharacter(character.id)}
                            size="1"
                          />
                        </Flex>
                      ) : (
                        <Flex
                          className="characters-list-leading"
                          align="center"
                          justify="center"
                        >
                          <CharacterListAvatar
                            key={character.imageUrl ?? character.id}
                            character={character}
                            onEditProfile={onEditProfile}
                          />
                        </Flex>
                      )}

                      <Flex
                        className="characters-list-item-main"
                        align="center"
                        gap="2"
                        justify="between"
                      >
                        <Flex
                          direction="column"
                          gap="1"
                          style={{ flex: 1, minWidth: 0, overflow: "hidden" }}
                        >
                          <Text
                            size="2"
                            weight="medium"
                            className="characters-list-item-title"
                          >
                            {character.name}
                          </Text>
                          <Flex gap="2">
                            <Text
                              size="1"
                              color="gray"
                            >
                              {character.tokenCount} {t("characters.tokenCount")}
                            </Text>
                            <Text
                              size="1"
                              color="gray"
                            >
                              · {formatRelativeTime(character.updatedAt)}
                            </Text>
                          </Flex>
                        </Flex>

                        <IconButton
                          size="1"
                          variant="ghost"
                          className="characters-list-favorite-button"
                          style={{
                            width: "24px",
                            height: "24px",
                            color: character.isFavorited ? "var(--amber-9)" : "var(--gray-9)",
                          }}
                          aria-label={
                            character.isFavorited
                              ? t("characters.unfavorite")
                              : t("characters.favorite")
                          }
                          onClick={(event) => {
                            event.stopPropagation();
                            onToggleFavorite(character, !character.isFavorited);
                          }}
                        >
                          <Star
                            size={15}
                            fill={character.isFavorited ? "currentColor" : "none"}
                          />
                        </IconButton>
                      </Flex>
                    </Flex>
                  </Box>
                );
              })}
            </Flex>
          )}
        </Box>
      </Flex>

      <ContextMenu
        position={menuPosition}
        items={menuItems}
        onClose={handleCloseContextMenu}
      />

      <Dialog.Root
        open={batchDeleteDialogOpen}
        onOpenChange={setBatchDeleteDialogOpen}
      >
        <Dialog.Content style={{ maxWidth: 400 }}>
          <Dialog.Title>{t("characters.deleteSelected")}</Dialog.Title>
          <Dialog.Description
            size="2"
            mb="4"
          >
            {t("characters.batchDeleteConfirm", { count: selectedIds.size })}
          </Dialog.Description>
          <Flex
            gap="3"
            justify="end"
          >
            <Dialog.Close>
              <Button
                variant="soft"
                color="gray"
              >
                {t("common.cancel")}
              </Button>
            </Dialog.Close>
            <Button
              variant="solid"
              color="red"
              onClick={handleBatchDeleteConfirm}
            >
              {t("common.delete")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
    </>
  );
}

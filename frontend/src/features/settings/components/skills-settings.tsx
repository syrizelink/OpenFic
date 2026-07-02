import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Dialog,
  Flex,
  IconButton,
  Switch,
  Text,
  TextArea,
  TextField,
  Tooltip,
} from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { MoreHorizontal, Plus, Search, Trash2, Upload, X } from "lucide-react";
import Fuse from "fuse.js";
import { useTranslation } from "react-i18next";
import { Spinner } from "@/components";

import {
  createSkill,
  deleteSkill,
  fetchSkills,
  toggleSkill,
  updateSkill,
} from "@/lib/api-client";
import { toast } from "@/components/toast";
import { ContextMenu, type ContextMenuItem, type ContextMenuPosition } from "@/components/context-menu";
import { countTokens } from "@/lib/tiktoken-utils";
import { getPinyin, getInitials } from "@/lib/pinyin-search";
import type { Skill, SkillCreate, SkillListResponse } from "@/lib/skill.types";
import { ImportSkillDialog } from "./import-skill-dialog";
import "./skills-settings.css";

interface SkillFormState {
  name: string;
  summary: string;
  skillId: string;
  content: string;
}

interface SkillsSettingsProps {
  variant?: "page" | "settings";
  mobilePage?: "list" | "detail";
  mobileDirection?: 1 | -1;
  onMobileDetailTitleChange?: (title: string | null) => void;
  onMobilePageChange?: (page: "list" | "detail") => void;
}

const MotionBox = motion.create(Box);

const mobilePageVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? "100%" : "-100%",
  }),
  center: {
    x: 0,
  },
  exit: (direction: number) => ({
    x: direction > 0 ? "-100%" : "100%",
  }),
};

const EMPTY_FORM: SkillFormState = {
  name: "",
  summary: "",
  skillId: "",
  content: "",
};

function toFormState(skill: Skill | null): SkillFormState {
  if (!skill) return EMPTY_FORM;
  return {
    name: skill.name,
    summary: skill.summary,
    skillId: skill.skillId,
    content: skill.content,
  };
}

function isValidSkillId(skillId: string): boolean {
  if (!skillId) return true;
  return /^[a-z]+(?:-[a-z]+)*$/.test(skillId);
}

export function SkillsSettings({
  variant = "page",
  mobilePage,
  mobileDirection: controlledMobileDirection,
  onMobileDetailTitleChange,
  onMobilePageChange,
}: SkillsSettingsProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [contextMenuPos, setContextMenuPos] = useState<ContextMenuPosition | null>(null);
  const [contextMenuSkillId, setContextMenuSkillId] = useState<string | null>(null);

  const [isMobile, setIsMobile] = useState(false);
  const [internalMobilePage, setInternalMobilePage] = useState<"list" | "detail">("list");
  const [internalMobileDirection, setInternalMobileDirection] = useState<1 | -1>(1);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const currentMobilePage = mobilePage ?? internalMobilePage;
  const currentMobileDirection = controlledMobileDirection ?? internalMobileDirection;

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const { data, isLoading, error } = useQuery({
    queryKey: ["skills"],
    queryFn: () => fetchSkills({ page: 1, pageSize: 100 }),
  });

  const skills = useMemo(() => data?.items ?? [], [data?.items]);

  const searchableSkills = useMemo(() => {
    return skills.map((s) => ({
      id: s.id,
      name: s.name || "",
      namePinyin: getPinyin(s.name || ""),
      nameInitials: getInitials(s.name || ""),
      skillId: s.skillId || "",
    }));
  }, [skills]);

  const fuse = useMemo(() => {
    return new Fuse(searchableSkills, {
      keys: [
        { name: "name", weight: 3 },
        { name: "namePinyin", weight: 2 },
        { name: "nameInitials", weight: 2.5 },
        { name: "skillId", weight: 1.5 },
      ],
      threshold: 0.3,
      ignoreLocation: true,
    });
  }, [searchableSkills]);

  const filteredSkills = useMemo(() => {
    if (!searchQuery.trim()) return skills;
    const results = fuse.search(searchQuery);
    const matchedIds = new Set(results.map((r) => r.item.id));
    return skills.filter((s) => matchedIds.has(s.id));
  }, [skills, searchQuery, fuse]);

  const effectiveSelectedSkillId = useMemo(() => {
    if (selectedSkillId && skills.some((item) => item.id === selectedSkillId)) {
      return selectedSkillId;
    }
    return skills[0]?.id ?? null;
  }, [selectedSkillId, skills]);

  const selectedSkill = useMemo(
    () => skills.find((item) => item.id === effectiveSelectedSkillId) ?? null,
    [effectiveSelectedSkillId, skills]
  );
  const isSettingsVariant = variant === "settings";

  const handleMobilePageChange = useCallback((page: "list" | "detail") => {
    if (controlledMobileDirection === undefined) {
      setInternalMobileDirection(page === "detail" ? 1 : -1);
    }
    onMobilePageChange?.(page);
    if (mobilePage === undefined) setInternalMobilePage(page);
  }, [controlledMobileDirection, mobilePage, onMobilePageChange]);

  useEffect(() => {
    onMobileDetailTitleChange?.(selectedSkill?.name || null);
  }, [onMobileDetailTitleChange, selectedSkill]);

  const createMutation = useMutation({
    mutationFn: (payload: SkillCreate) => createSkill(payload),
    onSuccess: (createdSkill) => {
      queryClient.invalidateQueries({ queryKey: ["skills"] });
      setSelectedSkillId(createdSkill.id);
      toast.success(t("settingsExtra.skills.newSkill"));
    },
    onError: () => {
      toast.error(t("common.error"));
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ skillDbId, payload }: { skillDbId: string; payload: SkillFormState }) =>
      updateSkill(skillDbId, {
        name: payload.name,
        summary: payload.summary,
        skillId: payload.skillId || undefined,
        content: payload.content,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["skills"] });
    },
    onError: () => {
      toast.error(t("settings.saveFailed"));
    },
  });

  const toggleMutation = useMutation({
    mutationFn: ({ skillDbId }: { skillDbId: string; nextEnabled: boolean }) => toggleSkill(skillDbId),
    onMutate: async ({ skillDbId, nextEnabled }) => {
      await queryClient.cancelQueries({ queryKey: ["skills"] });
      const previous = queryClient.getQueryData<SkillListResponse>(["skills"]);

      if (previous) {
        queryClient.setQueryData<SkillListResponse>(["skills"], {
          ...previous,
          items: previous.items.map((item) =>
            item.id === skillDbId ? { ...item, isEnabled: nextEnabled } : item
          ),
        });
      }

      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["skills"], context.previous);
      }
      toast.error(t("common.error"));
    },
    onSuccess: (updatedSkill) => {
      queryClient.setQueryData<SkillListResponse>(["skills"], (current) => {
        if (!current) return current;
        return {
          ...current,
          items: current.items.map((item) =>
            item.id === updatedSkill.id ? updatedSkill : item
          ),
        };
      });
      toast.success(updatedSkill.isEnabled ? t("worldInfo.enabled") : t("worldInfo.disabled"));
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["skills"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (skillDbId: string) => deleteSkill(skillDbId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["skills"] });
      setDeleteDialogOpen(false);
      toast.success(t("common.delete"));
    },
    onError: () => {
      toast.error(t("common.error"));
    },
  });

  const handleCreate = () => {
    const defaultPayload: SkillCreate = {
      name: t("settingsExtra.skills.newSkill"),
      summary: "",
      skillId: "",
      content: "",
      isEnabled: false,
    };
    createMutation.mutate(defaultPayload);
  };

  const handleSave = useCallback(
    (skillDbId: string, payload: SkillFormState) => {
      return updateMutation.mutateAsync({ skillDbId, payload });
    },
    [updateMutation]
  );

  const handleContextMenu = useCallback((skillId: string, position: ContextMenuPosition) => {
    setContextMenuPos(position);
    setContextMenuSkillId(skillId);
  }, []);

  const handleCloseContextMenu = useCallback(() => {
    setContextMenuPos(null);
    setContextMenuSkillId(null);
  }, []);

  const contextMenuItems = useMemo<ContextMenuItem[]>(() => {
    if (!contextMenuSkillId) return [];
    const skill = skills.find((s) => s.id === contextMenuSkillId);
    if (!skill) return [];

    return [
      {
        id: "delete",
        label: t("common.delete"),
        icon: Trash2,
        danger: true,
        onClick: () => {
          setSelectedSkillId(contextMenuSkillId);
          setDeleteDialogOpen(true);
          handleCloseContextMenu();
        },
      },
    ];
  }, [contextMenuSkillId, skills, handleCloseContextMenu, t]);

  const listContent = (
    <div className="skills-settings-list-container">
      <div className="skills-settings-toolbar">
        <Flex align="center" justify="between" gap="2" className="skills-settings-toolbar-row">
          <Box style={{ flex: 1, minWidth: 0 }}>
            <TextField.Root
              size="2"
              placeholder={t("settingsExtra.skills.searchPlaceholder")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            >
              <TextField.Slot>
                <Search size={14} />
              </TextField.Slot>
              {searchQuery && (
                <TextField.Slot>
                  <IconButton
                    variant="ghost"
                    size="1"
                    onClick={() => setSearchQuery("")}
                  >
                    <X size={12} />
                  </IconButton>
                </TextField.Slot>
              )}
            </TextField.Root>
          </Box>

          <Flex align="center" gap="1" className="skills-settings-toolbar-actions">
            <Tooltip content={t("settingsExtra.skills.newSkill")}>
              <IconButton
                size="2"
                variant="ghost"
                color="gray"
                aria-label={t("settingsExtra.skills.newSkill")}
                onClick={handleCreate}
                disabled={createMutation.isPending}
              >
                <Plus size={14} />
              </IconButton>
            </Tooltip>

            <Tooltip content={t("settingsExtra.skills.importSkill")}>
              <IconButton
                size="2"
                variant="ghost"
                color="gray"
                aria-label={t("settingsExtra.skills.importSkill")}
                onClick={() => setImportDialogOpen(true)}
                disabled={createMutation.isPending}
              >
                <Upload size={14} />
              </IconButton>
            </Tooltip>
          </Flex>
        </Flex>
      </div>

      <div className="skills-settings-list">
        {filteredSkills.length === 0 ? (
          <Flex align="center" justify="center" p="6" style={{ height: "100%" }}>
            <Text size="2" color="gray" align="center">
              {searchQuery.trim()
                ? t("settingsExtra.skills.noSearchResults")
                : t("settingsExtra.skills.empty")}
            </Text>
          </Flex>
        ) : (
          <Flex direction="column" gap="2" className="skills-settings-list-body">
            {filteredSkills.map((skill) => (
              <SkillListItem
                key={skill.id}
                skill={skill}
                isSelected={skill.id === effectiveSelectedSkillId}
                isMenuOpen={skill.id === contextMenuSkillId}
                onSelect={() => {
                  setSelectedSkillId(skill.id);
                  if (isMobile) handleMobilePageChange("detail");
                }}
                onToggle={() =>
                  toggleMutation.mutate({
                    skillDbId: skill.id,
                    nextEnabled: !skill.isEnabled,
                  })
                }
                onContextMenu={(pos) => handleContextMenu(skill.id, pos)}
              />
            ))}
          </Flex>
        )}
      </div>
    </div>
  );

  if (isLoading) {
    return (
      <Flex align="center" justify="center" style={{ height: "100%" }}>
        <Spinner size={18} />
      </Flex>
    );
  }

  if (error) {
    return (
      <Flex align="center" justify="center" style={{ height: "100%" }}>
        <Text color="red">{t("settingsExtra.skills.loadFailed")}</Text>
      </Flex>
    );
  }

  const detailContent = !selectedSkill ? (
    <Box className="skills-settings-empty-state">
      <Text size="2" color="gray">
        {t("settingsExtra.skills.selectSkill")}
      </Text>
    </Box>
  ) : (
    <SkillEditor
      key={selectedSkill.id}
      skill={selectedSkill}
      onSave={handleSave}
    />
  );

  if (isMobile) {
    return (
      <Flex
        direction="column"
        className={`skills-settings${isSettingsVariant ? " skills-settings--settings" : ""}`}
      >
        <Box className="settings-dialog-mobile-page-stack">
          <AnimatePresence initial={false} custom={currentMobileDirection} mode="sync">
            {currentMobilePage === "list" ? (
              <MotionBox
                key="skills-mobile-list"
                custom={currentMobileDirection}
                variants={mobilePageVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                className="settings-dialog-mobile-page"
              >
                <Box className="skills-settings-mobile-page">
                  <Box className="skills-settings-mobile-page-content">{listContent}</Box>
                </Box>
              </MotionBox>
            ) : (
              <MotionBox
                key="skills-mobile-detail"
                custom={currentMobileDirection}
                variants={mobilePageVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                className="settings-dialog-mobile-page"
              >
                <div className={`skills-settings-editor-panel${isSettingsVariant ? " skills-settings-editor-panel--settings" : ""}`}>
                  {detailContent}
                </div>
              </MotionBox>
            )}
          </AnimatePresence>
        </Box>

        <ContextMenu
          position={contextMenuPos}
          items={contextMenuItems}
          onClose={handleCloseContextMenu}
        />

        <Dialog.Root open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <Dialog.Content style={{ maxWidth: 420 }}>
            <Dialog.Title>{t("settingsExtra.skills.deleteTitle")}</Dialog.Title>
            <Dialog.Description size="2" mt="2">
              {t("settingsExtra.skills.deleteDescription")}
            </Dialog.Description>
            <Flex justify="end" gap="2" mt="4">
              <Button variant="soft" color="gray" onClick={() => setDeleteDialogOpen(false)}>
                {t("common.cancel")}
              </Button>
              <Button
                color="red"
                onClick={() => effectiveSelectedSkillId && deleteMutation.mutate(effectiveSelectedSkillId)}
              >
                {t("common.delete")}
              </Button>
            </Flex>
          </Dialog.Content>
        </Dialog.Root>

        <ImportSkillDialog
          open={importDialogOpen}
          onOpenChange={setImportDialogOpen}
          onCreate={(payload) => createMutation.mutate(payload)}
        />
      </Flex>
    );
  }

  return (
    <Flex
      direction="column"
      className={`skills-settings${isSettingsVariant ? " skills-settings--settings" : ""}`}
    >
      <Flex className={`skills-settings-layout${isSettingsVariant ? " skills-settings-layout--settings" : ""}`}>
        <Box
          display={{ initial: "none", md: "block" }}
          className={`skills-settings-list-panel${isSettingsVariant ? " skills-settings-list-panel--settings" : ""}`}
        >
          {listContent}
        </Box>

        <div className={`skills-settings-editor-panel${isSettingsVariant ? " skills-settings-editor-panel--settings" : ""}`}>
          {detailContent}
        </div>
      </Flex>

      <ContextMenu
        position={contextMenuPos}
        items={contextMenuItems}
        onClose={handleCloseContextMenu}
      />

      <Dialog.Root open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <Dialog.Content style={{ maxWidth: 420 }}>
          <Dialog.Title>{t("settingsExtra.skills.deleteTitle")}</Dialog.Title>
          <Dialog.Description size="2" mt="2">
            {t("settingsExtra.skills.deleteDescription")}
          </Dialog.Description>
          <Flex justify="end" gap="2" mt="4">
            <Button variant="soft" color="gray" onClick={() => setDeleteDialogOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              color="red"
              onClick={() => effectiveSelectedSkillId && deleteMutation.mutate(effectiveSelectedSkillId)}
            >
              {t("common.delete")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>

      <ImportSkillDialog
        open={importDialogOpen}
        onOpenChange={setImportDialogOpen}
        onCreate={(payload) => createMutation.mutate(payload)}
      />
    </Flex>
  );
}

interface SkillListItemProps {
  skill: Skill;
  isSelected: boolean;
  isMenuOpen: boolean;
  onSelect: () => void;
  onToggle: () => void;
  onContextMenu: (position: ContextMenuPosition) => void;
}

function SkillListItem({
  skill,
  isSelected,
  isMenuOpen,
  onSelect,
  onToggle,
  onContextMenu,
}: SkillListItemProps) {
  const { t } = useTranslation();
  const handleContextMenu = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      onContextMenu({ x: e.clientX, y: e.clientY });
    },
    [onContextMenu]
  );

  return (
    <div
      role="button"
      tabIndex={0}
      className={`skills-settings-list-item${isSelected ? " skills-settings-list-item--selected" : ""}${isMenuOpen ? " skills-settings-list-item--menu-open" : ""}${!skill.isComplete ? " skills-settings-list-item--incomplete" : ""}`}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
      onContextMenu={handleContextMenu}
    >
      <Flex align="start" justify="between" gap="2" className="skills-settings-item-row">
        <Flex direction="column" gap="1" className="skills-settings-item-content">
          <Flex align="center" gap="2" className="skills-settings-item-title-row">
            <Text size="2" truncate weight={isSelected ? "medium" : "regular"}>
              {skill.name || t("settingsExtra.skills.untitled")}
            </Text>
            {!skill.isComplete ? (
              <Badge size="1" variant="soft" color="amber">
                {t("settingsExtra.skills.incomplete")}
              </Badge>
            ) : null}
          </Flex>
          <Text size="1" color="gray" className="skills-settings-item-description">
            {skill.summary || t("settingsExtra.skills.noDescription")}
          </Text>
        </Flex>

        <Flex align="center" gap="1" className="skills-settings-item-actions">
          <Switch
            size="1"
            checked={skill.isEnabled}
            disabled={!skill.isComplete}
            onClick={(e) => e.stopPropagation()}
            onCheckedChange={onToggle}
          />
          <IconButton
            type="button"
            variant="ghost"
            color="gray"
            size="1"
            className="skills-settings-item-menu"
            aria-label={t("settingsExtra.skills.menu")}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              const rect = event.currentTarget.getBoundingClientRect();
              onContextMenu({ x: rect.right, y: rect.bottom + 4 });
            }}
          >
            <MoreHorizontal size={14} />
          </IconButton>
        </Flex>
      </Flex>
    </div>
  );
}

interface SkillEditorProps {
  skill: Skill;
  onSave: (skillDbId: string, payload: SkillFormState) => Promise<unknown>;
}

function SkillEditor({ skill, onSave }: SkillEditorProps) {
  const { t } = useTranslation();
  const [form, setForm] = useState<SkillFormState>(() => toFormState(skill));
  const [lastSaved, setLastSaved] = useState<string>(() => JSON.stringify(toFormState(skill)));
  const [isSaving, setIsSaving] = useState(false);
  const tokenCount = useMemo(() => countTokens(form.content), [form.content]);

  const hasUnsavedChanges = JSON.stringify(form) !== lastSaved;
  const canSave = hasUnsavedChanges && !isSaving && isValidSkillId(form.skillId);

  const handleSave = useCallback(async () => {
    if (!canSave) return;
    const currentJson = JSON.stringify(form);
    setIsSaving(true);
    try {
      await onSave(skill.id, form);
      setLastSaved(currentJson);
    } finally {
      setIsSaving(false);
    }
  }, [canSave, form, onSave, skill.id]);

  return (
    <Box p={{ initial: "4", md: "5" }}>
      <Flex direction="column" gap="1" className="skills-settings-editor-content">
        <Flex direction="column" gap="3">
          <Box>
            <Text size="2" weight="medium" as="label">
              {t("settingsExtra.skills.name")}
            </Text>
            <TextField.Root
              mt="2"
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
              placeholder={t("settingsExtra.skills.namePlaceholder")}
            />
          </Box>

          <Box>
            <Text size="2" weight="medium" as="label">
              {t("settingsExtra.skills.summary")}
            </Text>
            <TextArea
              mt="2"
              value={form.summary}
              onChange={(e) => setForm((prev) => ({ ...prev, summary: e.target.value }))}
              placeholder={t("settingsExtra.skills.summaryPlaceholder")}
              rows={3}
            />
          </Box>

          <Box>
            <Text size="2" weight="medium" as="label">
              {t("settingsExtra.skills.id")}
            </Text>
            <TextField.Root
              mt="2"
              value={form.skillId}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, skillId: e.target.value.trim() }))
              }
              placeholder={t("settingsExtra.skills.idPlaceholder")}
            />
            <Text
              size="1"
              color={form.skillId && !isValidSkillId(form.skillId) ? "red" : "gray"}
              style={{ display: "block", marginTop: 6, visibility: form.skillId && !isValidSkillId(form.skillId) ? "visible" : "hidden" }}
            >
              {t("settingsExtra.skills.idHelp")}
            </Text>
          </Box>

          <Box>
            <Flex justify="between" align="center">
              <Text size="2" weight="medium" as="label">
                {t("settingsExtra.skills.content")}
              </Text>
              <Text size="1" color="gray">
                {tokenCount} tokens
              </Text>
            </Flex>
            <TextArea
              mt="2"
              value={form.content}
              onChange={(e) => setForm((prev) => ({ ...prev, content: e.target.value }))}
              placeholder={t("settingsExtra.skills.contentPlaceholder")}
              rows={18}
            />
          </Box>
        </Flex>

        <Flex align="center" justify="end" className="skills-settings-editor-actions">
          <Button onClick={() => void handleSave()} disabled={!canSave}>
            {isSaving ? t("settingsExtra.skills.saving") : t("common.save")}
          </Button>
        </Flex>
      </Flex>
    </Box>
  );
}

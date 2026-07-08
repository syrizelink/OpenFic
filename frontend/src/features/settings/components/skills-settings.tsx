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
import Fuse from "fuse.js";
import { FilePen, MoreHorizontal, PenLine, Plus, Search, Trash2, Import, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";
import {
  ContextMenu,
  type ContextMenuItem,
  type ContextMenuPosition,
} from "@/components/context-menu";
import { toast } from "@/components/toast";
import {
  createSkill,
  createSkillReferenceDoc,
  deleteSkill,
  deleteSkillReferenceDoc,
  fetchSkills,
  fetchSkillReferenceDocs,
  toggleSkill,
  updateSkill,
  updateSkillReferenceDoc,
} from "@/lib/api-client";
import { getPinyin, getInitials } from "@/lib/pinyin-search";
import type { Skill, SkillCreate, SkillListResponse } from "@/lib/skill.types";
import type {
  SkillReferenceDoc,
  SkillReferenceDocCreate,
} from "@/lib/skill-reference-doc.types";
import { countTokens } from "@/lib/tiktoken-utils";

import { ImportSkillDialog } from "./import-skill-dialog";

import { fetchAgentDefinitions } from "../lib/agent-definitions-api";

import "./skills-settings.css";

interface SkillFormState {
  name: string;
  summary: string;
  content: string;
}

interface SkillsSettingsProps {
  variant?: "page" | "settings";
  mobilePage?: "list" | "detail";
  mobileDirection?: 1 | -1;
  mobileRefDocEdit?: boolean;
  onMobileDetailTitleChange?: (title: string | null) => void;
  onMobilePageChange?: (page: "list" | "detail") => void;
  onMobileRefDocEditChange?: (active: boolean) => void;
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
  content: "",
};

function toFormState(skill: Skill | null): SkillFormState {
  if (!skill) return EMPTY_FORM;
  return {
    name: skill.name,
    summary: skill.summary,
    content: skill.content,
  };
}

export function SkillsSettings({
  variant = "page",
  mobilePage,
  mobileDirection: controlledMobileDirection,
  mobileRefDocEdit: controlledMobileRefDocEdit,
  onMobileDetailTitleChange,
  onMobilePageChange,
  onMobileRefDocEditChange,
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
  const [internalMobileRefDocEdit, setInternalMobileRefDocEdit] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const currentMobilePage = mobilePage ?? internalMobilePage;
  const currentMobileDirection = controlledMobileDirection ?? internalMobileDirection;
  const currentMobileRefDocEdit = controlledMobileRefDocEdit ?? internalMobileRefDocEdit;

  const [editingRefDoc, setEditingRefDoc] = useState<SkillReferenceDoc | null>(null);
  const [renamingRefDocId, setRenamingRefDocId] = useState<string | null>(null);
  const [deletingRefDoc, setDeletingRefDoc] = useState<SkillReferenceDoc | null>(null);

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

  const { data: agentDefinitions } = useQuery({
    queryKey: ["agent-definitions"],
    queryFn: fetchAgentDefinitions,
  });

  const skills = useMemo(() => data?.items ?? [], [data?.items]);

  const agentCountBySkillId = useMemo(() => {
    const counts = new Map<string, number>();
    for (const agent of agentDefinitions ?? []) {
      for (const skillId of agent.enabled_skills) {
        if (!skillId) continue;
        counts.set(skillId, (counts.get(skillId) ?? 0) + 1);
      }
    }
    return counts;
  }, [agentDefinitions]);

  const searchableSkills = useMemo(() => {
    return skills.map((s) => ({
      id: s.id,
      name: s.name || "",
      namePinyin: getPinyin(s.name || ""),
      nameInitials: getInitials(s.name || ""),
    }));
  }, [skills]);

  const fuse = useMemo(() => {
    return new Fuse(searchableSkills, {
      keys: [
        { name: "name", weight: 3 },
        { name: "namePinyin", weight: 2 },
        { name: "nameInitials", weight: 2.5 },
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
    [effectiveSelectedSkillId, skills],
  );
  const isSettingsVariant = variant === "settings";

  const { data: refDocsData } = useQuery({
    queryKey: ["skill-reference-docs", effectiveSelectedSkillId],
    queryFn: () => fetchSkillReferenceDocs(effectiveSelectedSkillId as string),
    enabled: !!effectiveSelectedSkillId,
  });
  const refDocs = useMemo(() => refDocsData ?? [], [refDocsData]);

  const handleMobilePageChange = useCallback(
    (page: "list" | "detail") => {
      if (controlledMobileDirection === undefined) {
        setInternalMobileDirection(page === "detail" ? 1 : -1);
      }
      onMobilePageChange?.(page);
      if (mobilePage === undefined) setInternalMobilePage(page);
    },
    [controlledMobileDirection, mobilePage, onMobilePageChange],
  );

  useEffect(() => {
    onMobileDetailTitleChange?.(selectedSkill?.name || null);
  }, [onMobileDetailTitleChange, selectedSkill]);

  useEffect(() => {
    setEditingRefDoc(null);
    setRenamingRefDocId(null);
    setDeletingRefDoc(null);
  }, [effectiveSelectedSkillId]);

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
        content: payload.content,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["skills"] });
    },
onError: () => {
      toast.error(t("common.error"));
    },
  });

  const handleImported = useCallback(
    (skill: Skill) => {
      queryClient.invalidateQueries({ queryKey: ["skills"] });
      setSelectedSkillId(skill.id);
      toast.success(t("settingsExtra.skills.importedSkill"));
    },
    [queryClient, t],
  );

  const toggleMutation = useMutation({
    mutationFn: ({ skillDbId }: { skillDbId: string; nextEnabled: boolean }) =>
      toggleSkill(skillDbId),
    onMutate: async ({ skillDbId, nextEnabled }) => {
      await queryClient.cancelQueries({ queryKey: ["skills"] });
      const previous = queryClient.getQueryData<SkillListResponse>(["skills"]);

      if (previous) {
        queryClient.setQueryData<SkillListResponse>(["skills"], {
          ...previous,
          items: previous.items.map((item) =>
            item.id === skillDbId ? { ...item, isEnabled: nextEnabled } : item,
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
          items: current.items.map((item) => (item.id === updatedSkill.id ? updatedSkill : item)),
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

  const createRefDocMutation = useMutation({
    mutationFn: ({ skillDbId, payload }: { skillDbId: string; payload: SkillReferenceDocCreate }) =>
      createSkillReferenceDoc(skillDbId, payload),
    onSuccess: () => {
      if (effectiveSelectedSkillId) {
        queryClient.invalidateQueries({
          queryKey: ["skill-reference-docs", effectiveSelectedSkillId],
        });
      }
      toast.success(t("settingsExtra.skills.referenceDocCreated"));
    },
    onError: () => {
      toast.error(t("common.error"));
    },
  });

  const renameRefDocMutation = useMutation({
    mutationFn: ({
      skillDbId,
      docId,
      title,
    }: {
      skillDbId: string;
      docId: string;
      title: string;
    }) => updateSkillReferenceDoc(skillDbId, docId, { title }),
    onMutate: async ({ skillDbId, docId, title }) => {
      const queryKey = ["skill-reference-docs", skillDbId];
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<SkillReferenceDoc[]>(queryKey);
      queryClient.setQueryData<SkillReferenceDoc[]>(queryKey, (current) =>
        current?.map((d) => (d.id === docId ? { ...d, title } : d)) ?? current,
      );
      return { previous, skillDbId };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["skill-reference-docs", context.skillDbId], context.previous);
      }
      toast.error(t("settingsExtra.skills.referenceDocRenameFailed"));
    },
    onSuccess: () => {
      toast.success(t("settingsExtra.skills.referenceDocRenamed"));
    },
    onSettled: (_data, _error, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["skill-reference-docs", variables.skillDbId],
      });
    },
  });

  const editRefDocContentMutation = useMutation({
    mutationFn: ({
      skillDbId,
      docId,
      content,
    }: {
      skillDbId: string;
      docId: string;
      content: string;
    }) => updateSkillReferenceDoc(skillDbId, docId, { content }),
    onSuccess: () => {
      if (effectiveSelectedSkillId) {
        queryClient.invalidateQueries({
          queryKey: ["skill-reference-docs", effectiveSelectedSkillId],
        });
      }
      toast.success(t("common.saveSuccess"));
    },
    onError: () => {
      toast.error(t("common.saveFailed"));
    },
  });

  const deleteRefDocMutation = useMutation({
    mutationFn: ({ skillDbId, docId }: { skillDbId: string; docId: string }) =>
      deleteSkillReferenceDoc(skillDbId, docId),
    onSuccess: () => {
      if (effectiveSelectedSkillId) {
        queryClient.invalidateQueries({
          queryKey: ["skill-reference-docs", effectiveSelectedSkillId],
        });
      }
      setDeletingRefDoc(null);
      toast.success(t("common.deleteSuccess"));
    },
    onError: () => {
      toast.error(t("common.deleteFailed"));
    },
  });

  const handleCreate = () => {
    const defaultPayload: SkillCreate = {
      name: t("settingsExtra.skills.newSkill"),
      summary: "",
      content: "",
      isEnabled: false,
    };
    createMutation.mutate(defaultPayload);
  };

  const handleSave = useCallback(
    (skillDbId: string, payload: SkillFormState) => {
      return updateMutation.mutateAsync({ skillDbId, payload });
    },
    [updateMutation],
  );

  const handleContextMenu = useCallback((skillDbId: string, position: ContextMenuPosition) => {
    setContextMenuPos(position);
    setContextMenuSkillId(skillDbId);
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

  const handleCreateRefDoc = useCallback(() => {
    if (!effectiveSelectedSkillId) return;
    createRefDocMutation.mutate({
      skillDbId: effectiveSelectedSkillId,
      payload: { title: t("settingsExtra.skills.newReferenceDoc"), content: "" },
    });
  }, [createRefDocMutation, effectiveSelectedSkillId, t]);

  const handleStartRenameRefDoc = useCallback((doc: SkillReferenceDoc) => {
    setRenamingRefDocId(doc.id);
  }, []);

  const handleConfirmRenameRefDoc = useCallback(
    (newTitle: string) => {
      const docId = renamingRefDocId;
      setRenamingRefDocId(null);
      if (!docId || !effectiveSelectedSkillId) return;
      const current = refDocs.find((d) => d.id === docId);
      if (current && newTitle.trim() && newTitle.trim() !== current.title) {
        renameRefDocMutation.mutate({
          skillDbId: effectiveSelectedSkillId,
          docId,
          title: newTitle.trim(),
        });
      }
    },
    [renamingRefDocId, effectiveSelectedSkillId, refDocs, renameRefDocMutation],
  );

  const handleCancelRenameRefDoc = useCallback(() => {
    setRenamingRefDocId(null);
  }, []);

  const handleEditRefDoc = useCallback(
    (doc: SkillReferenceDoc) => {
      setEditingRefDoc(doc);
      if (isMobile) {
        setInternalMobileRefDocEdit(true);
        onMobileRefDocEditChange?.(true);
        onMobileDetailTitleChange?.(doc.title || t("settingsExtra.skills.untitledReferenceDoc"));
      }
    },
    [isMobile, onMobileRefDocEditChange, onMobileDetailTitleChange, t],
  );

  const handleDeleteRefDoc = useCallback((doc: SkillReferenceDoc) => {
    setDeletingRefDoc(doc);
  }, []);

  const handleSaveRefDocContent = useCallback(
    async (content: string) => {
      if (!editingRefDoc || !effectiveSelectedSkillId) return;
      await editRefDocContentMutation.mutateAsync({
        skillDbId: effectiveSelectedSkillId,
        docId: editingRefDoc.id,
        content,
      });
    },
    [editingRefDoc, effectiveSelectedSkillId, editRefDocContentMutation],
  );

  const handleConfirmDeleteRefDoc = useCallback(() => {
    if (!deletingRefDoc || !effectiveSelectedSkillId) return;
    deleteRefDocMutation.mutate({
      skillDbId: effectiveSelectedSkillId,
      docId: deletingRefDoc.id,
    });
  }, [deletingRefDoc, effectiveSelectedSkillId, deleteRefDocMutation]);

  const handleExitRefDocEdit = useCallback(() => {
    setInternalMobileRefDocEdit(false);
    onMobileRefDocEditChange?.(false);
  }, [onMobileRefDocEditChange]);

  const prevMobileRefDocEditRef = useRef(false);
  useEffect(() => {
    if (prevMobileRefDocEditRef.current && !currentMobileRefDocEdit) {
      setEditingRefDoc(null);
      onMobileDetailTitleChange?.(selectedSkill?.name || null);
    }
    prevMobileRefDocEditRef.current = currentMobileRefDocEdit;
  }, [currentMobileRefDocEdit, onMobileDetailTitleChange, selectedSkill]);

  const listContent = (
    <div className="skills-settings-list-container">
      <div className="skills-settings-toolbar">
        <Flex
          align="center"
          justify="between"
          gap="2"
          className="skills-settings-toolbar-row"
        >
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

          <Flex
            align="center"
            gap="1"
            className="skills-settings-toolbar-actions"
          >
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
                <Import size={14} />
              </IconButton>
            </Tooltip>
          </Flex>
        </Flex>
      </div>

      <div className="skills-settings-list">
        {filteredSkills.length === 0 ? (
          <Flex
            align="center"
            justify="center"
            p="6"
            style={{ height: "100%" }}
          >
            <Text
              size="2"
              color="gray"
              align="center"
            >
              {searchQuery.trim()
                ? t("settingsExtra.skills.noSearchResults")
                : t("settingsExtra.skills.empty")}
            </Text>
          </Flex>
        ) : (
          <Flex
            direction="column"
            gap="2"
            className="skills-settings-list-body"
          >
            {filteredSkills.map((skill) => (
              <SkillListItem
                key={skill.id}
                skill={skill}
                agentCount={agentCountBySkillId.get(skill.id) ?? 0}
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
      <Flex
        align="center"
        justify="center"
        style={{ height: "100%" }}
      >
        <Spinner size={18} />
      </Flex>
    );
  }

  if (error) {
    return (
      <Flex
        align="center"
        justify="center"
        style={{ height: "100%" }}
      >
        <Text color="red">{t("settingsExtra.skills.loadFailed")}</Text>
      </Flex>
    );
  }

  const detailContent = !selectedSkill ? (
    <Box className="skills-settings-empty-state">
      <Text
        size="2"
        color="gray"
      >
        {t("settingsExtra.skills.selectSkill")}
      </Text>
    </Box>
  ) : (
    <SkillEditor
      key={selectedSkill.id}
      skill={selectedSkill}
      onSave={handleSave}
      refDocs={refDocs}
      renamingRefDocId={renamingRefDocId}
      onCreateRefDoc={handleCreateRefDoc}
      onStartRenameRefDoc={handleStartRenameRefDoc}
      onConfirmRenameRefDoc={handleConfirmRenameRefDoc}
      onCancelRenameRefDoc={handleCancelRenameRefDoc}
      onEditRefDoc={handleEditRefDoc}
      onDeleteRefDoc={handleDeleteRefDoc}
      isCreatingRefDoc={createRefDocMutation.isPending}
      isRenamingRefDoc={renameRefDocMutation.isPending}
    />
  );

  const refDocDialogs = (
    <>
      <SkillReferenceDocEditDialog
        doc={editingRefDoc}
        open={!!editingRefDoc && !isMobile}
        onOpenChange={(o) => !o && setEditingRefDoc(null)}
        onSave={handleSaveRefDocContent}
        isSaving={editRefDocContentMutation.isPending}
      />
      <SkillReferenceDocDeleteDialog
        doc={deletingRefDoc}
        open={!!deletingRefDoc}
        onOpenChange={(o) => !o && setDeletingRefDoc(null)}
        onConfirm={handleConfirmDeleteRefDoc}
        isSaving={deleteRefDocMutation.isPending}
      />
    </>
  );

  const mobilePageTransition = { duration: 0.22, ease: [0.22, 1, 0.36, 1] as const };

  const effectiveMobilePage = currentMobileRefDocEdit ? "ref-doc-edit" : currentMobilePage;

  if (isMobile) {
    return (
      <Flex
        direction="column"
        className={`skills-settings${isSettingsVariant ? " skills-settings--settings" : ""}`}
      >
        <Box className="settings-dialog-mobile-page-stack">
          <AnimatePresence
            initial={false}
            custom={currentMobileDirection}
            mode="sync"
          >
            {effectiveMobilePage === "list" ? (
              <MotionBox
                key="skills-mobile-list"
                custom={currentMobileDirection}
                variants={mobilePageVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={mobilePageTransition}
                className="settings-dialog-mobile-page"
              >
                <Box className="skills-settings-mobile-page">
                  <Box className="skills-settings-mobile-page-content">{listContent}</Box>
                </Box>
              </MotionBox>
            ) : effectiveMobilePage === "ref-doc-edit" ? (
              <MotionBox
                key="skills-mobile-ref-doc-edit"
                custom={currentMobileDirection}
                variants={mobilePageVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={mobilePageTransition}
                className="settings-dialog-mobile-page"
              >
                <div
                  className={`skills-settings-editor-panel${isSettingsVariant ? " skills-settings-editor-panel--settings" : ""}`}
                >
                  {editingRefDoc ? (
                    <div className="skills-settings-editor">
                      <div className="skills-settings-editor-scroll">
                        <Flex
                          direction="column"
                          gap="3"
                          className="skills-settings-editor-content"
                        >
                          <Text
                            size="3"
                            weight="medium"
                          >
                            {editingRefDoc.title || t("settingsExtra.skills.untitledReferenceDoc")}
                          </Text>
                          <ReferenceDocEditor
                            doc={editingRefDoc}
                            onSave={handleSaveRefDocContent}
                            onDone={handleExitRefDocEdit}
                            isSaving={editRefDocContentMutation.isPending}
                          />
                        </Flex>
                      </div>
                    </div>
                  ) : null}
                </div>
              </MotionBox>
            ) : (
              <MotionBox
                key="skills-mobile-detail"
                custom={currentMobileDirection}
                variants={mobilePageVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={mobilePageTransition}
                className="settings-dialog-mobile-page"
              >
                <div
                  className={`skills-settings-editor-panel${isSettingsVariant ? " skills-settings-editor-panel--settings" : ""}`}
                >
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

        <Dialog.Root
          open={deleteDialogOpen}
          onOpenChange={setDeleteDialogOpen}
        >
          <Dialog.Content style={{ maxWidth: 420 }}>
            <Dialog.Title>{t("settingsExtra.skills.deleteTitle")}</Dialog.Title>
            <Dialog.Description
              size="2"
              mt="2"
            >
              {t("settingsExtra.skills.deleteDescription")}
            </Dialog.Description>
            <Flex
              justify="end"
              gap="2"
              mt="4"
            >
              <Button
                variant="soft"
                color="gray"
                onClick={() => setDeleteDialogOpen(false)}
              >
                {t("common.cancel")}
              </Button>
              <Button
                color="red"
                onClick={() =>
                  effectiveSelectedSkillId && deleteMutation.mutate(effectiveSelectedSkillId)
                }
              >
                {t("common.delete")}
              </Button>
            </Flex>
          </Dialog.Content>
        </Dialog.Root>

        {refDocDialogs}

        <ImportSkillDialog
          open={importDialogOpen}
          onOpenChange={setImportDialogOpen}
          onImported={handleImported}
        />
      </Flex>
    );
  }

  return (
    <Flex
      direction="column"
      className={`skills-settings${isSettingsVariant ? " skills-settings--settings" : ""}`}
    >
      <Flex
        className={`skills-settings-layout${isSettingsVariant ? " skills-settings-layout--settings" : ""}`}
      >
        <Box
          display={{ initial: "none", md: "block" }}
          className={`skills-settings-list-panel${isSettingsVariant ? " skills-settings-list-panel--settings" : ""}`}
        >
          {listContent}
        </Box>

        <div
          className={`skills-settings-editor-panel${isSettingsVariant ? " skills-settings-editor-panel--settings" : ""}`}
        >
          {detailContent}
        </div>
      </Flex>

      <ContextMenu
        position={contextMenuPos}
        items={contextMenuItems}
        onClose={handleCloseContextMenu}
      />

      <Dialog.Root
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
      >
        <Dialog.Content style={{ maxWidth: 420 }}>
          <Dialog.Title>{t("settingsExtra.skills.deleteTitle")}</Dialog.Title>
          <Dialog.Description
            size="2"
            mt="2"
          >
            {t("settingsExtra.skills.deleteDescription")}
          </Dialog.Description>
          <Flex
            justify="end"
            gap="2"
            mt="4"
          >
            <Button
              variant="soft"
              color="gray"
              onClick={() => setDeleteDialogOpen(false)}
            >
              {t("common.cancel")}
            </Button>
            <Button
              color="red"
              onClick={() =>
                effectiveSelectedSkillId && deleteMutation.mutate(effectiveSelectedSkillId)
              }
            >
              {t("common.delete")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>

      {refDocDialogs}

      <ImportSkillDialog
        open={importDialogOpen}
        onOpenChange={setImportDialogOpen}
        onImported={handleImported}
      />
    </Flex>
  );
}

interface SkillListItemProps {
  skill: Skill;
  agentCount: number;
  isSelected: boolean;
  isMenuOpen: boolean;
  onSelect: () => void;
  onToggle: () => void;
  onContextMenu: (position: ContextMenuPosition) => void;
}

function SkillListItem({
  skill,
  agentCount,
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
    [onContextMenu],
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
      <Flex
        direction="column"
        gap="1"
        className="skills-settings-item-content"
      >
        <Flex
          align="center"
          justify="between"
          gap="2"
          className="skills-settings-item-row"
        >
          <Flex
            align="center"
            gap="2"
            className="skills-settings-item-title-row"
          >
            <Text
              size="2"
              truncate
              weight={isSelected ? "medium" : "regular"}
            >
              {skill.name || t("settingsExtra.skills.untitled")}
            </Text>
            {!skill.isComplete ? (
              <Badge
                size="1"
                variant="soft"
                color="amber"
              >
                {t("settingsExtra.skills.incomplete")}
              </Badge>
            ) : null}
            <Tooltip
              content={
                agentCount > 0
                  ? t("settingsExtra.skills.agentCountTooltip", { count: agentCount })
                  : t("settingsExtra.skills.agentCountZero")
              }
            >
              <Badge
                size="1"
                variant="soft"
                color={agentCount > 0 ? "green" : "amber"}
                className="skills-settings-item-agent-count"
              >
                {agentCount}
              </Badge>
            </Tooltip>
          </Flex>

          <Flex
            align="center"
            gap="1"
            className="skills-settings-item-actions"
          >
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
        <Text
          size="1"
          color="gray"
          className="skills-settings-item-description"
        >
          {skill.summary || t("settingsExtra.skills.noDescription")}
        </Text>
      </Flex>
    </div>
  );
}

interface SkillEditorProps {
  skill: Skill;
  onSave: (skillDbId: string, payload: SkillFormState) => Promise<unknown>;
  refDocs: SkillReferenceDoc[];
  renamingRefDocId: string | null;
  onCreateRefDoc: () => void;
  onStartRenameRefDoc: (doc: SkillReferenceDoc) => void;
  onConfirmRenameRefDoc: (newTitle: string) => void;
  onCancelRenameRefDoc: () => void;
  onEditRefDoc: (doc: SkillReferenceDoc) => void;
  onDeleteRefDoc: (doc: SkillReferenceDoc) => void;
  isCreatingRefDoc: boolean;
  isRenamingRefDoc: boolean;
}

function SkillEditor({
  skill,
  onSave,
  refDocs,
  renamingRefDocId,
  onCreateRefDoc,
  onStartRenameRefDoc,
  onConfirmRenameRefDoc,
  onCancelRenameRefDoc,
  onEditRefDoc,
  onDeleteRefDoc,
  isCreatingRefDoc,
  isRenamingRefDoc,
}: SkillEditorProps) {
  const { t } = useTranslation();
  const [form, setForm] = useState<SkillFormState>(() => toFormState(skill));
  const [lastSaved, setLastSaved] = useState<string>(() => JSON.stringify(toFormState(skill)));
  const [isSaving, setIsSaving] = useState(false);
  const tokenCount = useMemo(() => countTokens(form.content), [form.content]);

  const hasUnsavedChanges = JSON.stringify(form) !== lastSaved;
  const canSave = hasUnsavedChanges && !isSaving;

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
    <div className="skills-settings-editor">
      <div className="skills-settings-editor-scroll">
        <Flex
          direction="column"
          gap="3"
          className="skills-settings-editor-content"
        >
          <Box>
            <Text
              size="2"
              weight="medium"
              as="label"
            >
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
            <Text
              size="2"
              weight="medium"
              as="label"
            >
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
            <Flex
              justify="between"
              align="center"
            >
              <Text
                size="2"
                weight="medium"
                as="label"
              >
                {t("settingsExtra.skills.content")}
              </Text>
              <Text
                size="1"
                color="gray"
              >
                {tokenCount} tokens
              </Text>
            </Flex>
            <TextArea
              mt="2"
              value={form.content}
              onChange={(e) => setForm((prev) => ({ ...prev, content: e.target.value }))}
              placeholder={t("settingsExtra.skills.contentPlaceholder")}
              rows={12}
            />
          </Box>

          <SkillReferenceDocsSection
            refDocs={refDocs}
            renamingRefDocId={renamingRefDocId}
            onCreate={onCreateRefDoc}
            onStartRename={onStartRenameRefDoc}
            onConfirmRename={onConfirmRenameRefDoc}
            onCancelRename={onCancelRenameRefDoc}
            onEdit={onEditRefDoc}
            onDelete={onDeleteRefDoc}
            isCreating={isCreatingRefDoc}
            isRenaming={isRenamingRefDoc}
          />
        </Flex>
      </div>

      <div className="skills-settings-editor-footer">
        <Button
          onClick={() => void handleSave()}
          disabled={!canSave}
        >
          {isSaving ? t("settingsExtra.skills.saving") : t("common.save")}
        </Button>
      </div>
    </div>
  );
}

interface SkillReferenceDocsSectionProps {
  refDocs: SkillReferenceDoc[];
  renamingRefDocId: string | null;
  onCreate: () => void;
  onStartRename: (doc: SkillReferenceDoc) => void;
  onConfirmRename: (newTitle: string) => void;
  onCancelRename: () => void;
  onEdit: (doc: SkillReferenceDoc) => void;
  onDelete: (doc: SkillReferenceDoc) => void;
  isCreating: boolean;
  isRenaming: boolean;
}

function SkillReferenceDocsSection({
  refDocs,
  renamingRefDocId,
  onCreate,
  onStartRename,
  onConfirmRename,
  onCancelRename,
  onEdit,
  onDelete,
  isCreating,
  isRenaming,
}: SkillReferenceDocsSectionProps) {
  const { t } = useTranslation();

  return (
    <Box className="skills-settings-refdocs">
      <Flex
        align="center"
        justify="between"
        gap="2"
        className="skills-settings-refdocs-header"
      >
        <Text
          size="2"
          weight="medium"
        >
          {t("settingsExtra.skills.referenceDocs")} ({refDocs.length})
        </Text>
        <Button
          size="1"
          variant="ghost"
          color="gray"
          onClick={onCreate}
          disabled={isCreating}
        >
          <Plus size={14} />
          {t("settingsExtra.skills.newReferenceDocButton")}
        </Button>
      </Flex>

      <Flex
        direction="column"
        gap="1"
        className="skills-settings-refdocs-list"
      >
        {refDocs.length === 0 ? (
          <Text
            size="1"
            color="gray"
            className="skills-settings-refdocs-empty"
          >
            {t("settingsExtra.skills.referenceDocsEmpty")}
          </Text>
        ) : (
          refDocs.map((doc) => (
            <Flex
              key={doc.id}
              align="center"
              justify="between"
              gap="2"
              className={`skills-settings-refdocs-item${renamingRefDocId === doc.id ? " skills-settings-refdocs-item--renaming" : ""}`}
            >
              <Box
                className="skills-settings-refdocs-item-title"
                onClick={(e) => e.stopPropagation()}
              >
                {renamingRefDocId === doc.id ? (
                  <RefDocRenameInput
                    initialValue={doc.title}
                    onConfirm={onConfirmRename}
                    onCancel={onCancelRename}
                  />
                ) : (
                  <Text
                    size="2"
                    truncate
                  >
                    {doc.title || t("settingsExtra.skills.untitledReferenceDoc")}
                  </Text>
                )}
              </Box>

              <Box className="skills-settings-refdocs-item-meta">
                <Text
                  size="1"
                  color="gray"
                  className="skills-settings-refdocs-item-tokens"
                >
                  {doc.tokens} {t("settingsExtra.skills.tokens")}
                </Text>
                <Flex
                  align="center"
                  gap="1"
                  className="skills-settings-refdocs-item-actions"
                >
                  <Tooltip content={t("common.rename")}>
                    <IconButton
                      size="1"
                      variant="ghost"
                      color="gray"
                      aria-label={t("common.rename")}
                      disabled={isRenaming}
                      onClick={() => onStartRename(doc)}
                    >
                      <PenLine size={14} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip content={t("common.edit")}>
                    <IconButton
                      size="1"
                      variant="ghost"
                      color="gray"
                      aria-label={t("common.edit")}
                      onClick={() => onEdit(doc)}
                    >
                      <FilePen size={14} />
                    </IconButton>
                  </Tooltip>
                  <Tooltip content={t("common.delete")}>
                    <IconButton
                      size="1"
                      variant="ghost"
                      color="red"
                      aria-label={t("common.delete")}
                      onClick={() => onDelete(doc)}
                    >
                      <Trash2 size={14} />
                    </IconButton>
                  </Tooltip>
                </Flex>
              </Box>
            </Flex>
          ))
        )}
      </Flex>
    </Box>
  );
}

interface RefDocRenameInputProps {
  initialValue: string;
  onConfirm: (newTitle: string) => void;
  onCancel: () => void;
}

function RefDocRenameInput({ initialValue, onConfirm, onCancel }: RefDocRenameInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState(initialValue);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, []);

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (trimmed && trimmed !== initialValue) {
      onConfirm(trimmed);
      return;
    }
    onCancel();
  }, [initialValue, onCancel, onConfirm, value]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLInputElement>) => {
      if (event.key === "Enter") {
        event.preventDefault();
        handleSubmit();
      } else if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    },
    [handleSubmit, onCancel],
  );

  return (
    <input
      ref={inputRef}
      type="text"
      value={value}
      onChange={(event) => setValue(event.target.value)}
      onBlur={handleSubmit}
      onKeyDown={handleKeyDown}
      onClick={(event) => event.stopPropagation()}
      className="skills-settings-refdocs-item-rename-input"
    />
  );
}

interface ReferenceDocEditorProps {
  doc: SkillReferenceDoc;
  onSave: (content: string) => Promise<void>;
  onDone: () => void;
  isSaving: boolean;
}

function ReferenceDocEditor({ doc, onSave, onDone, isSaving }: ReferenceDocEditorProps) {
  const { t } = useTranslation();
  const [content, setContent] = useState(doc.content);
  const hasChanges = content !== doc.content;

  const handleSave = useCallback(async () => {
    if (!hasChanges) {
      onDone();
      return;
    }
    await onSave(content);
    onDone();
  }, [hasChanges, onSave, content, onDone]);

  return (
    <Flex
      direction="column"
      gap="3"
    >
      <TextArea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder={t("settingsExtra.skills.referenceDocContentPlaceholder")}
        rows={12}
      />
      <Flex
        gap="3"
        justify="end"
      >
        <Button
          variant="soft"
          color="gray"
          onClick={onDone}
          disabled={isSaving}
        >
          {t("common.cancel")}
        </Button>
        <Button
          onClick={() => void handleSave()}
          disabled={isSaving || !hasChanges}
        >
          {isSaving ? <Spinner size={18} /> : null}
          {t("common.save")}
        </Button>
      </Flex>
    </Flex>
  );
}

interface SkillReferenceDocEditDialogProps {
  doc: SkillReferenceDoc | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (content: string) => Promise<void>;
  isSaving: boolean;
}

function SkillReferenceDocEditDialog({
  doc,
  open,
  onOpenChange,
  onSave,
  isSaving,
}: SkillReferenceDocEditDialogProps) {
  const { t } = useTranslation();

  return (
    <Dialog.Root
      open={open}
      onOpenChange={onOpenChange}
    >
      <Dialog.Content style={{ maxWidth: 640 }}>
        <Dialog.Title>
          {doc?.title || t("settingsExtra.skills.untitledReferenceDoc")}
        </Dialog.Title>
        {doc ? (
          <Box mt="4">
            <ReferenceDocEditor
              doc={doc}
              onSave={onSave}
              onDone={() => onOpenChange(false)}
              isSaving={isSaving}
            />
          </Box>
        ) : null}
      </Dialog.Content>
    </Dialog.Root>
  );
}

interface SkillReferenceDocDeleteDialogProps {
  doc: SkillReferenceDoc | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  isSaving: boolean;
}

function SkillReferenceDocDeleteDialog({
  open,
  onOpenChange,
  onConfirm,
  isSaving,
}: SkillReferenceDocDeleteDialogProps) {
  const { t } = useTranslation();

  return (
    <Dialog.Root
      open={open}
      onOpenChange={onOpenChange}
    >
      <Dialog.Content style={{ maxWidth: 420 }}>
        <Dialog.Title>{t("settingsExtra.skills.deleteReferenceDoc")}</Dialog.Title>
        <Dialog.Description
          size="2"
          mt="2"
        >
          {t("settingsExtra.skills.deleteReferenceDocDescription")}
        </Dialog.Description>
        <Flex
          justify="end"
          gap="2"
          mt="4"
        >
          <Button
            variant="soft"
            color="gray"
            onClick={() => onOpenChange(false)}
            disabled={isSaving}
          >
            {t("common.cancel")}
          </Button>
          <Button
            color="red"
            onClick={onConfirm}
            disabled={isSaving}
          >
            {t("common.delete")}
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

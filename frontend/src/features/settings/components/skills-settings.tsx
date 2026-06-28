import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Dialog,
  Flex,
  IconButton,
  Spinner,
  Switch,
  Text,
  TextArea,
  TextField,
  Tooltip,
} from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { List, MoreHorizontal, Plus, Search, Trash2, Upload, X } from "lucide-react";
import { motion } from "motion/react";
import Fuse from "fuse.js";

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

const MotionBox = motion.create(Box);

interface SkillFormState {
  name: string;
  summary: string;
  skillId: string;
  content: string;
}

interface SkillsSettingsProps {
  variant?: "page" | "settings";
}

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

export function SkillsSettings({ variant = "page" }: SkillsSettingsProps) {
  const queryClient = useQueryClient();
  const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [contextMenuPos, setContextMenuPos] = useState<ContextMenuPosition | null>(null);
  const [contextMenuSkillId, setContextMenuSkillId] = useState<string | null>(null);

  const [isMobile, setIsMobile] = useState(false);
  const [mobileListOpen, setMobileListOpen] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);

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

  const createMutation = useMutation({
    mutationFn: (payload: SkillCreate) => createSkill(payload),
    onSuccess: (createdSkill) => {
      queryClient.invalidateQueries({ queryKey: ["skills"] });
      setSelectedSkillId(createdSkill.id);
      toast.success("技能已创建");
    },
    onError: () => {
      toast.error("技能创建失败");
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
      toast.error("技能保存失败");
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
      toast.error("技能启用状态更新失败");
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
      toast.success(updatedSkill.isEnabled ? "技能已启用" : "技能已停用");
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
      toast.success("技能已删除");
    },
    onError: () => {
      toast.error("技能删除失败");
    },
  });

  const handleCreate = () => {
    const defaultPayload: SkillCreate = {
      name: "新建技能",
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
        label: "删除",
        icon: Trash2,
        danger: true,
        onClick: () => {
          setSelectedSkillId(contextMenuSkillId);
          setDeleteDialogOpen(true);
          handleCloseContextMenu();
        },
      },
    ];
  }, [contextMenuSkillId, skills, handleCloseContextMenu]);

  const listContent = (
    <div className="skills-settings-list-container">
      <div className="skills-settings-toolbar">
        <Flex align="center" justify="between" gap="2" className="skills-settings-toolbar-row">
          <Box style={{ flex: 1, minWidth: 0 }}>
            <TextField.Root
              size="2"
              placeholder="搜索技能..."
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
            <Tooltip content="新建技能">
              <IconButton
                size="2"
                variant="ghost"
                color="gray"
                aria-label="新建技能"
                onClick={handleCreate}
                disabled={createMutation.isPending}
              >
                <Plus size={14} />
              </IconButton>
            </Tooltip>

            <Tooltip content="导入技能">
              <IconButton
                size="2"
                variant="ghost"
                color="gray"
                aria-label="导入技能"
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
              {searchQuery.trim() ? "无匹配结果" : "暂无技能"}
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
                  if (isMobile) setMobileListOpen(false);
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
        <Spinner size="3" />
      </Flex>
    );
  }

  if (error) {
    return (
      <Flex align="center" justify="center" style={{ height: "100%" }}>
        <Text color="red">技能列表加载失败</Text>
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
          {isMobile && (
            <Flex gap="2" className="skills-settings-mobile-trigger">
              <Tooltip content="查看技能列表">
                <IconButton
                  variant="ghost"
                  size="2"
                  onClick={() => setMobileListOpen((prev) => !prev)}
                >
                  <List size={18} />
                </IconButton>
              </Tooltip>
            </Flex>
          )}

          {!selectedSkill ? (
            <Box className="skills-settings-empty-state">
              <Text size="2" color="gray">
                请选择一个技能
              </Text>
            </Box>
          ) : (
            <SkillEditor
              key={selectedSkill.id}
              skill={selectedSkill}
              onSave={handleSave}
            />
          )}
        </div>
      </Flex>

      {isMobile && (
        <>
          <motion.div
            initial={false}
            animate={{ opacity: mobileListOpen ? 1 : 0 }}
            transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
            className="skills-settings-mobile-backdrop"
            onClick={() => setMobileListOpen(false)}
            style={{ pointerEvents: mobileListOpen ? "auto" : "none" }}
          />

          <MotionBox
            initial={false}
            animate={{ x: mobileListOpen ? 0 : -320 }}
            transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
            className="skills-settings-mobile-overlay"
            style={{ pointerEvents: mobileListOpen ? "auto" : "none" }}
          >
            <Box className={`skills-settings-mobile-sheet${isSettingsVariant ? " skills-settings-mobile-sheet--settings" : ""}`}>
              {listContent}
            </Box>
          </MotionBox>
        </>
      )}

      <ContextMenu
        position={contextMenuPos}
        items={contextMenuItems}
        onClose={handleCloseContextMenu}
      />

      <Dialog.Root open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <Dialog.Content style={{ maxWidth: 420 }}>
          <Dialog.Title>删除技能</Dialog.Title>
          <Dialog.Description size="2" mt="2">
            删除后无法恢复。
          </Dialog.Description>
          <Flex justify="end" gap="2" mt="4">
            <Button variant="soft" color="gray" onClick={() => setDeleteDialogOpen(false)}>
              取消
            </Button>
            <Button
              color="red"
              onClick={() => effectiveSelectedSkillId && deleteMutation.mutate(effectiveSelectedSkillId)}
            >
              删除
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
              {skill.name || "未命名技能"}
            </Text>
            {!skill.isComplete ? (
              <Badge size="1" variant="soft" color="amber">
                待完善
              </Badge>
            ) : null}
          </Flex>
          <Text size="1" color="gray" className="skills-settings-item-description">
            {skill.summary || "暂无描述"}
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
            aria-label="技能菜单"
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
              名称
            </Text>
            <TextField.Root
              mt="2"
              value={form.name}
              onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
              placeholder="输入技能名"
            />
          </Box>

          <Box>
            <Text size="2" weight="medium" as="label">
              简述
            </Text>
            <TextArea
              mt="2"
              value={form.summary}
              onChange={(e) => setForm((prev) => ({ ...prev, summary: e.target.value }))}
              placeholder="输入对技能的简略描述"
              rows={3}
            />
          </Box>

          <Box>
            <Text size="2" weight="medium" as="label">
              ID
            </Text>
            <TextField.Root
              mt="2"
              value={form.skillId}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, skillId: e.target.value.trim() }))
              }
              placeholder="仅小写英文和 -"
            />
            <Text
              size="1"
              color={form.skillId && !isValidSkillId(form.skillId) ? "red" : "gray"}
              style={{ display: "block", marginTop: 6, visibility: form.skillId && !isValidSkillId(form.skillId) ? "visible" : "hidden" }}
            >
              ID 只允许英文小写字母和 &apos;-&apos;
            </Text>
          </Box>

          <Box>
            <Flex justify="between" align="center">
              <Text size="2" weight="medium" as="label">
                内容
              </Text>
              <Text size="1" color="gray">
                {tokenCount} tokens
              </Text>
            </Flex>
            <TextArea
              mt="2"
              value={form.content}
              onChange={(e) => setForm((prev) => ({ ...prev, content: e.target.value }))}
              placeholder="输入技能的完整内容"
              rows={18}
            />
          </Box>
        </Flex>

        <Flex align="center" justify="end" className="skills-settings-editor-actions">
          <Button onClick={() => void handleSave()} disabled={!canSave}>
            {isSaving ? "保存中..." : "保存"}
          </Button>
        </Flex>
      </Flex>
    </Box>
  );
}

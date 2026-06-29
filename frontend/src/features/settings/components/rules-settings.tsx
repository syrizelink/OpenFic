import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  Dialog,
  Flex,
  IconButton,
  Text,
  TextArea,
  TextField,
  Tooltip,
} from "@radix-ui/themes";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { MoreHorizontal, Plus, Search, Trash2, X } from "lucide-react";
import Fuse from "fuse.js";
import { useTranslation } from "react-i18next";
import { Spinner } from "@/components";

import {
  createAgentRule,
  deleteAgentRule,
  fetchAgentRules,
  updateAgentRule,
} from "@/lib/api-client";
import type { AgentRule, AgentRuleCreate, AgentRuleListResponse } from "@/lib/agent-rule.types";
import { ContextMenu, type ContextMenuItem, type ContextMenuPosition } from "@/components/context-menu";
import { toast } from "@/components/toast";
import "./skills-settings.css";

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

interface RulesSettingsProps {
  mobilePage?: "list" | "detail";
  mobileDirection?: 1 | -1;
  onMobileDetailTitleChange?: (title: string | null) => void;
  onMobilePageChange?: (page: "list" | "detail") => void;
}

interface RuleFormState {
  title: string;
  content: string;
}

const EMPTY_FORM: RuleFormState = {
  title: "",
  content: "",
};

function toFormState(rule: AgentRule | null): RuleFormState {
  if (!rule) return EMPTY_FORM;
  return {
    title: rule.title,
    content: rule.content,
  };
}

export function RulesSettings({
  mobilePage,
  mobileDirection: controlledMobileDirection,
  onMobileDetailTitleChange,
  onMobilePageChange,
}: RulesSettingsProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [contextMenuPos, setContextMenuPos] = useState<ContextMenuPosition | null>(null);
  const [contextMenuRuleId, setContextMenuRuleId] = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(false);
  const [internalMobilePage, setInternalMobilePage] = useState<"list" | "detail">("list");
  const [internalMobileDirection, setInternalMobileDirection] = useState<1 | -1>(1);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const { data, isLoading, error } = useQuery({
    queryKey: ["agent-rules"],
    queryFn: () => fetchAgentRules({ page: 1, pageSize: 100 }),
  });

  const rules = useMemo(() => data?.items ?? [], [data?.items]);

  const searchableRules = useMemo(
    () => rules.map((rule) => ({ id: rule.id, title: rule.title, content: rule.content })),
    [rules],
  );

  const fuse = useMemo(
    () =>
      new Fuse(searchableRules, {
        keys: [
          { name: "title", weight: 2 },
          { name: "content", weight: 1 },
        ],
        threshold: 0.3,
        ignoreLocation: true,
      }),
    [searchableRules],
  );

  const filteredRules = useMemo(() => {
    if (!searchQuery.trim()) return rules;
    const results = fuse.search(searchQuery);
    const matchedIds = new Set(results.map((result) => result.item.id));
    return rules.filter((rule) => matchedIds.has(rule.id));
  }, [rules, searchQuery, fuse]);

  const effectiveSelectedRuleId = useMemo(() => {
    if (selectedRuleId && rules.some((rule) => rule.id === selectedRuleId)) return selectedRuleId;
    return rules[0]?.id ?? null;
  }, [selectedRuleId, rules]);

  const selectedRule = useMemo(
    () => rules.find((rule) => rule.id === effectiveSelectedRuleId) ?? null,
    [effectiveSelectedRuleId, rules],
  );
  const currentMobilePage = mobilePage ?? internalMobilePage;
  const currentMobileDirection = controlledMobileDirection ?? internalMobileDirection;

  const handleMobilePageChange = useCallback((page: "list" | "detail") => {
    if (controlledMobileDirection === undefined) {
      setInternalMobileDirection(page === "detail" ? 1 : -1);
    }
    onMobilePageChange?.(page);
    if (mobilePage === undefined) setInternalMobilePage(page);
  }, [controlledMobileDirection, mobilePage, onMobilePageChange]);

  useEffect(() => {
    onMobileDetailTitleChange?.(selectedRule?.title || null);
  }, [onMobileDetailTitleChange, selectedRule]);

  const createMutation = useMutation({
    mutationFn: (payload: AgentRuleCreate) => createAgentRule(payload),
    onSuccess: (createdRule) => {
      queryClient.invalidateQueries({ queryKey: ["agent-rules"] });
      setSelectedRuleId(createdRule.id);
      toast.success(t("settingsExtra.rules.newRule"));
    },
    onError: () => toast.error(t("settingsExtra.rules.loadFailed")),
  });

  const updateMutation = useMutation({
    mutationFn: ({ ruleId, payload }: { ruleId: string; payload: RuleFormState }) =>
      updateAgentRule(ruleId, payload),
    onSuccess: (updatedRule) => {
      queryClient.setQueryData<AgentRuleListResponse>(["agent-rules"], (current) => {
        if (!current) return current;
        return {
          ...current,
          items: current.items.map((item) => (item.id === updatedRule.id ? updatedRule : item)),
        };
      });
    },
    onError: () => toast.error(t("settings.saveFailed")),
  });

  const deleteMutation = useMutation({
    mutationFn: (ruleId: string) => deleteAgentRule(ruleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-rules"] });
      setDeleteDialogOpen(false);
      setContextMenuRuleId(null);
      toast.success(t("common.delete"));
    },
    onError: () => toast.error(t("common.error")),
  });

  const handleCreate = useCallback(() => {
    createMutation.mutate({
      title: "新建规则",
      content: "",
    });
  }, [createMutation]);

  const handleSave = useCallback(
    (ruleId: string, payload: RuleFormState) => {
      return updateMutation.mutateAsync({ ruleId, payload });
    },
    [updateMutation],
  );

  const handleContextMenu = useCallback((ruleId: string, position: ContextMenuPosition) => {
    setContextMenuPos(position);
    setContextMenuRuleId(ruleId);
  }, []);

  const handleCloseContextMenu = useCallback(() => {
    setContextMenuPos(null);
    setContextMenuRuleId(null);
  }, []);

  const contextMenuItems = useMemo<ContextMenuItem[]>(() => {
    if (!contextMenuRuleId) return [];
    return [
      {
        id: "delete",
        label: "删除",
        icon: Trash2,
        danger: true,
        onClick: () => {
          setSelectedRuleId(contextMenuRuleId);
          setDeleteDialogOpen(true);
          handleCloseContextMenu();
        },
      },
    ];
  }, [contextMenuRuleId, handleCloseContextMenu]);

  const listContent = (
    <div className="skills-settings-list-container">
      <div className="skills-settings-toolbar">
        <Flex align="center" justify="between" gap="2" className="skills-settings-toolbar-row">
          <Box style={{ flex: 1, minWidth: 0 }}>
            <TextField.Root
              size="2"
              placeholder="搜索规则..."
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            >
              <TextField.Slot>
                <Search size={14} />
              </TextField.Slot>
              {searchQuery ? (
                <TextField.Slot>
                  <IconButton variant="ghost" size="1" onClick={() => setSearchQuery("")}>
                    <X size={12} />
                  </IconButton>
                </TextField.Slot>
              ) : null}
            </TextField.Root>
          </Box>

          <Flex align="center" gap="1" className="skills-settings-toolbar-actions">
            <Tooltip content="新建规则">
              <IconButton
                size="2"
                variant="ghost"
                color="gray"
                aria-label="新建规则"
                onClick={handleCreate}
                disabled={createMutation.isPending}
              >
                <Plus size={14} />
              </IconButton>
            </Tooltip>
          </Flex>
        </Flex>
      </div>

      <div className="skills-settings-list">
        {filteredRules.length === 0 ? (
          <Flex align="center" justify="center" p="6" style={{ height: "100%" }}>
            <Text size="2" color="gray" align="center">
              {searchQuery.trim() ? "无匹配结果" : "暂无规则"}
            </Text>
          </Flex>
        ) : (
          <Flex direction="column" gap="2" className="skills-settings-list-body">
            {filteredRules.map((rule) => (
              <RuleListItem
                key={rule.id}
                rule={rule}
                isSelected={rule.id === effectiveSelectedRuleId}
                isMenuOpen={rule.id === contextMenuRuleId}
                onSelect={() => {
                  setSelectedRuleId(rule.id);
                  if (isMobile) handleMobilePageChange("detail");
                }}
                onContextMenu={(position) => handleContextMenu(rule.id, position)}
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
        <Text color="red">规则列表加载失败</Text>
      </Flex>
    );
  }

  const detailContent = !selectedRule ? (
    <Box className="skills-settings-empty-state">
      <Text size="2" color="gray">
        请选择一条规则
      </Text>
    </Box>
  ) : (
    <RuleEditor key={selectedRule.id} rule={selectedRule} onSave={handleSave} />
  );

  if (isMobile) {
    return (
      <Flex direction="column" className="skills-settings skills-settings--settings">
        <Box className="settings-dialog-mobile-page-stack">
          <AnimatePresence initial={false} custom={currentMobileDirection} mode="sync">
            {currentMobilePage === "list" ? (
              <MotionBox
                key="rules-mobile-list"
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
                key="rules-mobile-detail"
                custom={currentMobileDirection}
                variants={mobilePageVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                className="settings-dialog-mobile-page"
              >
                <div className="skills-settings-editor-panel skills-settings-editor-panel--settings">
                  {detailContent}
                </div>
              </MotionBox>
            )}
          </AnimatePresence>
        </Box>

        <ContextMenu position={contextMenuPos} items={contextMenuItems} onClose={handleCloseContextMenu} />

        <Dialog.Root open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <Dialog.Content style={{ maxWidth: 420 }}>
            <Dialog.Title>删除规则</Dialog.Title>
            <Dialog.Description size="2" mt="2">
              删除后无法恢复。
            </Dialog.Description>
            <Flex justify="end" gap="2" mt="4">
              <Button variant="soft" color="gray" onClick={() => setDeleteDialogOpen(false)}>
                取消
              </Button>
              <Button
                color="red"
                onClick={() => {
                  if (effectiveSelectedRuleId) deleteMutation.mutate(effectiveSelectedRuleId);
                }}
              >
                删除
              </Button>
            </Flex>
          </Dialog.Content>
        </Dialog.Root>
      </Flex>
    );
  }

  return (
    <Flex direction="column" className="skills-settings skills-settings--settings">
      <Flex className="skills-settings-layout skills-settings-layout--settings">
        <Box display={{ initial: "none", md: "block" }} className="skills-settings-list-panel skills-settings-list-panel--settings">
          {listContent}
        </Box>

        <div className="skills-settings-editor-panel skills-settings-editor-panel--settings">
          {detailContent}
        </div>
      </Flex>

      <ContextMenu position={contextMenuPos} items={contextMenuItems} onClose={handleCloseContextMenu} />

      <Dialog.Root open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <Dialog.Content style={{ maxWidth: 420 }}>
          <Dialog.Title>删除规则</Dialog.Title>
          <Dialog.Description size="2" mt="2">
            删除后无法恢复。
          </Dialog.Description>
          <Flex justify="end" gap="2" mt="4">
            <Button variant="soft" color="gray" onClick={() => setDeleteDialogOpen(false)}>
              取消
            </Button>
            <Button
              color="red"
              onClick={() => {
                if (effectiveSelectedRuleId) deleteMutation.mutate(effectiveSelectedRuleId);
              }}
            >
              删除
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
    </Flex>
  );
}

interface RuleListItemProps {
  rule: AgentRule;
  isSelected: boolean;
  isMenuOpen: boolean;
  onSelect: () => void;
  onContextMenu: (position: ContextMenuPosition) => void;
}

function RuleListItem({ rule, isSelected, isMenuOpen, onSelect, onContextMenu }: RuleListItemProps) {
  const handleContextMenu = useCallback(
    (event: React.MouseEvent) => {
      event.preventDefault();
      onContextMenu({ x: event.clientX, y: event.clientY });
    },
    [onContextMenu],
  );

  return (
    <div
      role="button"
      tabIndex={0}
      className={`skills-settings-list-item${isSelected ? " skills-settings-list-item--selected" : ""}${isMenuOpen ? " skills-settings-list-item--menu-open" : ""}`}
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
        <Flex align="center" className="skills-settings-item-content">
          <Text size="2" truncate weight={isSelected ? "medium" : "regular"}>
            {rule.title || "未命名规则"}
          </Text>
        </Flex>

        <Flex align="center" gap="1" className="skills-settings-item-actions">
          <IconButton
            type="button"
            variant="ghost"
            color="gray"
            size="1"
            className="skills-settings-item-menu"
            aria-label="规则菜单"
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

interface RuleEditorProps {
  rule: AgentRule;
  onSave: (ruleId: string, payload: RuleFormState) => Promise<unknown>;
}

function RuleEditor({ rule, onSave }: RuleEditorProps) {
  const [form, setForm] = useState<RuleFormState>(() => toFormState(rule));
  const [lastSaved, setLastSaved] = useState<string>(() => JSON.stringify(toFormState(rule)));
  const [isSaving, setIsSaving] = useState(false);
  const hasUnsavedChanges = JSON.stringify(form) !== lastSaved;
  const canSave = hasUnsavedChanges && !isSaving && Boolean(form.title.trim());

  const handleSave = useCallback(async () => {
    if (!canSave) return;
    const currentJson = JSON.stringify(form);
    setIsSaving(true);
    try {
      await onSave(rule.id, form);
      setLastSaved(currentJson);
    } finally {
      setIsSaving(false);
    }
  }, [canSave, form, onSave, rule.id]);

  return (
    <Box p={{ initial: "4", md: "5" }}>
      <Flex direction="column" gap="1" className="skills-settings-editor-content">
        <Flex direction="column" gap="4">
          <Box>
            <Text size="2" weight="medium" as="label">
              标题
            </Text>
            <TextField.Root
              mt="2"
              value={form.title}
              onChange={(event) => {
                setForm((prev) => ({ ...prev, title: event.target.value }));
              }}
              placeholder="输入规则标题，例如：回复语言"
            />
          </Box>

          <Box>
            <TextArea
              mt="2"
              value={form.content}
              onChange={(event) => {
                setForm((prev) => ({ ...prev, content: event.target.value }));
              }}
              placeholder="输入规则内容，例如：回复时使用简体中文"
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

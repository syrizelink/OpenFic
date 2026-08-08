import {
  Badge,
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
import Fuse from "fuse.js";
import { Copy, MoreHorizontal, Plus, Search, Trash2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";
import {
  ContextMenu,
  type ContextMenuItem,
  type ContextMenuPosition,
} from "@/components/context-menu";
import { SimpleSelect } from "@/components/select";
import { toast } from "@/components/toast";
import type {
  AgentRule,
  AgentRuleCreate,
  AgentRuleListResponse,
  AgentRuleScope,
} from "@/lib/agent-rule.types";
import {
  createAgentRule,
  deleteAgentRule,
  fetchAgentRuleScopes,
  fetchAgentRules,
  updateAgentRule,
} from "@/lib/api-client";
import { countTokens } from "@/lib/tiktoken-utils";

import { AgentSettingsLockNotice } from "./agent-settings-lock-notice";

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
  isAgentSettingsLocked: boolean;
  isAgentSettingsLockLoading: boolean;
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

function scopeValue(scope: { scope: string; projectId: string | null }): string {
  return scope.scope === "global" ? "global" : `project:${scope.projectId}`;
}

function parseScopeValue(value: string): { scope: string; projectId: string | null } {
  if (value === "global") return { scope: "global", projectId: null };
  const projectId = value.startsWith("project:") ? value.slice("project:".length) : null;
  return { scope: "project", projectId };
}

export function RulesSettings({
  mobilePage,
  mobileDirection: controlledMobileDirection,
  onMobileDetailTitleChange,
  onMobilePageChange,
  isAgentSettingsLocked,
  isAgentSettingsLockLoading,
}: RulesSettingsProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [copyDialogOpen, setCopyDialogOpen] = useState(false);
  const [copyRuleId, setCopyRuleId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [contextMenuPos, setContextMenuPos] = useState<ContextMenuPosition | null>(null);
  const [contextMenuRuleId, setContextMenuRuleId] = useState<string | null>(null);
  const [selectedScope, setSelectedScope] = useState<string>("global");
  const [isMobile, setIsMobile] = useState(false);
  const [internalMobilePage, setInternalMobilePage] = useState<"list" | "detail">("list");
  const [internalMobileDirection, setInternalMobileDirection] = useState<1 | -1>(1);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  useEffect(() => {
    if (!isAgentSettingsLocked) return;
    setDeleteDialogOpen(false);
    setCopyDialogOpen(false);
    setCopyRuleId(null);
    setContextMenuPos(null);
    setContextMenuRuleId(null);
  }, [isAgentSettingsLocked]);

  const { data: scopesData } = useQuery({
    queryKey: ["agent-rule-scopes"],
    queryFn: fetchAgentRuleScopes,
  });

  const scopes = useMemo(() => scopesData?.items ?? [], [scopesData?.items]);

  useEffect(() => {
    if (scopes.length === 0) return;
    const exists = scopes.some((scope) => scopeValue(scope) === selectedScope);
    if (!exists) setSelectedScope("global");
  }, [scopes, selectedScope]);

  const activeScope = useMemo(() => parseScopeValue(selectedScope), [selectedScope]);

  const rulesQueryKey = useMemo(
    () => ["agent-rules", activeScope.scope, activeScope.projectId],
    [activeScope.scope, activeScope.projectId],
  );

  const { data, isLoading, error } = useQuery({
    queryKey: rulesQueryKey,
    queryFn: () =>
      fetchAgentRules({
        page: 1,
        pageSize: 100,
        scope: activeScope.scope,
        projectId: activeScope.projectId,
      }),
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
  const copyRule = useMemo(
    () => rules.find((rule) => rule.id === copyRuleId) ?? null,
    [copyRuleId, rules],
  );
  const currentMobilePage = mobilePage ?? internalMobilePage;
  const currentMobileDirection = controlledMobileDirection ?? internalMobileDirection;

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
    onMobileDetailTitleChange?.(selectedRule?.title || null);
  }, [onMobileDetailTitleChange, selectedRule]);

  const createMutation = useMutation({
    mutationFn: (payload: AgentRuleCreate) =>
      createAgentRule({
        ...payload,
        scope: activeScope.scope,
        projectId: activeScope.projectId,
      }),
    onSuccess: (createdRule) => {
      queryClient.invalidateQueries({ queryKey: rulesQueryKey });
      queryClient.invalidateQueries({ queryKey: ["agent-rule-scopes"] });
      setSelectedRuleId(createdRule.id);
      toast.success(t("settingsExtra.rules.newRule"));
    },
    onError: () => toast.error(t("common.error")),
  });

  const updateMutation = useMutation({
    mutationFn: ({ ruleId, payload }: { ruleId: string; payload: RuleFormState }) =>
      updateAgentRule(ruleId, payload),
    onSuccess: (updatedRule) => {
      queryClient.setQueryData<AgentRuleListResponse>(rulesQueryKey, (current) => {
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
      queryClient.invalidateQueries({ queryKey: rulesQueryKey });
      queryClient.invalidateQueries({ queryKey: ["agent-rule-scopes"] });
      setDeleteDialogOpen(false);
      setContextMenuRuleId(null);
      toast.success(t("common.delete"));
    },
    onError: () => toast.error(t("common.error")),
  });

  const copyMutation = useMutation({
    mutationFn: ({
      ruleId,
      target,
    }: {
      ruleId: string;
      target: { scope: string; projectId: string | null };
    }) => {
      const rule = rules.find((item) => item.id === ruleId);
      if (!rule) throw new Error("rule not found");
      return createAgentRule({
        title: rule.title,
        content: rule.content,
        scope: target.scope,
        projectId: target.projectId,
      });
    },
    onSuccess: (_copied, vars) => {
      queryClient.invalidateQueries({
        queryKey: ["agent-rules", vars.target.scope, vars.target.projectId],
      });
      queryClient.invalidateQueries({ queryKey: ["agent-rule-scopes"] });
      setCopyDialogOpen(false);
      setCopyRuleId(null);
      setContextMenuRuleId(null);
      toast.success(t("settingsExtra.rules.copySuccess"));
    },
    onError: () => toast.error(t("common.error")),
  });

  const handleCreate = useCallback(() => {
    createMutation.mutate({
      title: t("settingsExtra.rules.newRule"),
      content: "",
    });
  }, [createMutation, t]);

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
    if (!contextMenuRuleId || isAgentSettingsLocked) return [];
    return [
      {
        id: "copy",
        label: t("settingsExtra.rules.copyToScope"),
        icon: Copy,
        onClick: () => {
          setCopyRuleId(contextMenuRuleId);
          setCopyDialogOpen(true);
          handleCloseContextMenu();
        },
      },
      {
        id: "delete",
        label: t("common.delete"),
        icon: Trash2,
        danger: true,
        onClick: () => {
          setSelectedRuleId(contextMenuRuleId);
          setDeleteDialogOpen(true);
          handleCloseContextMenu();
        },
      },
    ];
  }, [contextMenuRuleId, handleCloseContextMenu, isAgentSettingsLocked, t]);

  const listContent = (
    <div className="skills-settings-list-container">
      <Box className="rules-settings-scope-selector">
        <SimpleSelect
          value={selectedScope}
          options={scopes.map((scope) => ({
            value: scopeValue(scope),
            label: scope.scope === "global" ? t("settingsExtra.rules.globalScope") : scope.title,
            separatorAfter: scope.scope === "global",
            suffix: (
              <Badge
                size="1"
                variant="soft"
                color="green"
                radius="medium"
                className="rules-settings-scope-badge"
              >
                {scope.ruleCount}
              </Badge>
            ),
          }))}
          onChange={setSelectedScope}
          placeholder={t("settingsExtra.rules.scopePlaceholder")}
          size="2"
          contentClassName="rules-settings-scope-content"
        />
      </Box>
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
              placeholder={t("settingsExtra.rules.searchPlaceholder")}
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            >
              <TextField.Slot>
                <Search size={14} />
              </TextField.Slot>
              {searchQuery ? (
                <TextField.Slot>
                  <IconButton
                    variant="ghost"
                    size="1"
                    onClick={() => setSearchQuery("")}
                  >
                    <X size={12} />
                  </IconButton>
                </TextField.Slot>
              ) : null}
            </TextField.Root>
          </Box>

          <Flex
            align="center"
            gap="1"
            className="skills-settings-toolbar-actions"
          >
            <Tooltip content={t("settingsExtra.rules.newRule")}>
              <IconButton
                size="2"
                variant="ghost"
                color="gray"
                aria-label={t("settingsExtra.rules.newRule")}
                onClick={handleCreate}
                disabled={isAgentSettingsLocked || createMutation.isPending}
              >
                <Plus size={14} />
              </IconButton>
            </Tooltip>
          </Flex>
        </Flex>
      </div>

      <div className="skills-settings-list">
        {filteredRules.length === 0 ? (
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
                ? t("settingsExtra.rules.noSearchResults")
                : t("settingsExtra.rules.empty")}
            </Text>
          </Flex>
        ) : (
          <Flex
            direction="column"
            gap="2"
            className="skills-settings-list-body"
          >
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
                isAgentSettingsLocked={isAgentSettingsLocked}
              />
            ))}
          </Flex>
        )}
      </div>
    </div>
  );

  if (isLoading || isAgentSettingsLockLoading) {
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
        <Text color="red">{t("settingsExtra.rules.loadFailed")}</Text>
      </Flex>
    );
  }

  const detailContent = !selectedRule ? (
    <Box className="skills-settings-empty-state">
      <Text
        size="2"
        color="gray"
      >
        {t("settingsExtra.rules.selectRule")}
      </Text>
    </Box>
  ) : (
    <RuleEditor
      key={selectedRule.id}
      rule={selectedRule}
      onSave={handleSave}
      isAgentSettingsLocked={isAgentSettingsLocked}
    />
  );

  if (isMobile) {
    return (
      <Flex
        direction="column"
        className="skills-settings skills-settings--settings"
      >
        <AgentSettingsLockNotice isLocked={isAgentSettingsLocked} />
        <Box className="settings-dialog-mobile-page-stack">
          <AnimatePresence
            initial={false}
            custom={currentMobileDirection}
            mode="sync"
          >
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
            <Dialog.Title>{t("settingsExtra.rules.deleteTitle")}</Dialog.Title>
            <Dialog.Description
              size="2"
              mt="2"
            >
              {t("settingsExtra.rules.deleteDescription")}
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
                disabled={isAgentSettingsLocked}
                onClick={() => {
                  if (effectiveSelectedRuleId) deleteMutation.mutate(effectiveSelectedRuleId);
                }}
              >
                {t("common.delete")}
              </Button>
            </Flex>
          </Dialog.Content>
        </Dialog.Root>

        <CopyRuleDialog
          open={copyDialogOpen}
          onOpenChange={setCopyDialogOpen}
          rule={copyRule}
          scopes={scopes}
          isAgentSettingsLocked={isAgentSettingsLocked}
          onCopy={(target) => {
            if (copyRuleId) copyMutation.mutate({ ruleId: copyRuleId, target });
          }}
        />
      </Flex>
    );
  }

  return (
    <Flex
      direction="column"
      className="skills-settings skills-settings--settings"
    >
      <AgentSettingsLockNotice isLocked={isAgentSettingsLocked} />
      <Flex className="skills-settings-layout skills-settings-layout--settings">
        <Box
          display={{ initial: "none", md: "block" }}
          className="skills-settings-list-panel skills-settings-list-panel--settings"
        >
          {listContent}
        </Box>

        <div className="skills-settings-editor-panel skills-settings-editor-panel--settings">
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
          <Dialog.Title>{t("settingsExtra.rules.deleteTitle")}</Dialog.Title>
          <Dialog.Description
            size="2"
            mt="2"
          >
            {t("settingsExtra.rules.deleteDescription")}
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
              disabled={isAgentSettingsLocked}
              onClick={() => {
                if (effectiveSelectedRuleId) deleteMutation.mutate(effectiveSelectedRuleId);
              }}
            >
              {t("common.delete")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>

      <CopyRuleDialog
        open={copyDialogOpen}
        onOpenChange={setCopyDialogOpen}
        rule={copyRule}
        scopes={scopes}
        isAgentSettingsLocked={isAgentSettingsLocked}
        onCopy={(target) => {
          if (copyRuleId) copyMutation.mutate({ ruleId: copyRuleId, target });
        }}
      />
    </Flex>
  );
}

interface RuleListItemProps {
  rule: AgentRule;
  isSelected: boolean;
  isMenuOpen: boolean;
  onSelect: () => void;
  onContextMenu: (position: ContextMenuPosition) => void;
  isAgentSettingsLocked: boolean;
}

function RuleListItem({
  rule,
  isSelected,
  isMenuOpen,
  onSelect,
  onContextMenu,
  isAgentSettingsLocked,
}: RuleListItemProps) {
  const { t } = useTranslation();
  const handleContextMenu = useCallback(
    (event: React.MouseEvent) => {
      if (isAgentSettingsLocked) return;
      event.preventDefault();
      onContextMenu({ x: event.clientX, y: event.clientY });
    },
    [isAgentSettingsLocked, onContextMenu],
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
      <Flex
        align="start"
        justify="between"
        gap="2"
        className="skills-settings-item-row"
      >
        <Flex
          align="center"
          className="skills-settings-item-content"
        >
          <Text
            size="2"
            truncate
            weight={isSelected ? "medium" : "regular"}
          >
            {rule.title || t("settingsExtra.rules.untitled")}
          </Text>
        </Flex>

        <Flex
          align="center"
          gap="1"
          className="skills-settings-item-actions"
        >
          <IconButton
            type="button"
            variant="ghost"
            color="gray"
            size="1"
            className="skills-settings-item-menu"
            aria-label={t("settingsExtra.rules.menu")}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              const rect = event.currentTarget.getBoundingClientRect();
              onContextMenu({ x: rect.right, y: rect.bottom + 4 });
            }}
            disabled={isAgentSettingsLocked}
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
  isAgentSettingsLocked: boolean;
}

function RuleEditor({ rule, onSave, isAgentSettingsLocked }: RuleEditorProps) {
  const { t } = useTranslation();
  const [form, setForm] = useState<RuleFormState>(() => toFormState(rule));
  const [lastSaved, setLastSaved] = useState<string>(() => JSON.stringify(toFormState(rule)));
  const [isSaving, setIsSaving] = useState(false);
  const tokenCount = useMemo(() => countTokens(form.content), [form.content]);
  const hasUnsavedChanges = JSON.stringify(form) !== lastSaved;
  const canSave =
    !isAgentSettingsLocked && hasUnsavedChanges && !isSaving && Boolean(form.title.trim());

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
    <div className="skills-settings-editor">
      <div className="skills-settings-editor-scroll">
        <Flex
          direction="column"
          gap="4"
          className="skills-settings-editor-content"
        >
          <Box>
            <Text
              size="2"
              weight="medium"
              as="label"
            >
              {t("settingsExtra.rules.title")}
            </Text>
            <TextField.Root
              mt="2"
              value={form.title}
              onChange={(event) => {
                setForm((prev) => ({ ...prev, title: event.target.value }));
              }}
              placeholder={t("settingsExtra.rules.titlePlaceholder")}
              disabled={isAgentSettingsLocked}
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
                {t("settingsExtra.rules.content")}
              </Text>
              <Text
                size="1"
                color="gray"
              >
                {tokenCount} {t("settingsExtra.rules.tokens")}
              </Text>
            </Flex>
            <TextArea
              mt="2"
              value={form.content}
              onChange={(event) => {
                setForm((prev) => ({ ...prev, content: event.target.value }));
              }}
              placeholder={t("settingsExtra.rules.contentPlaceholder")}
              rows={18}
              disabled={isAgentSettingsLocked}
            />
          </Box>
        </Flex>
      </div>

      <div className="skills-settings-editor-footer">
        <Button
          onClick={() => void handleSave()}
          disabled={!canSave}
        >
          {isSaving ? t("settingsExtra.rules.saving") : t("common.save")}
        </Button>
      </div>
    </div>
  );
}

interface CopyRuleDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  rule: AgentRule | null;
  scopes: AgentRuleScope[];
  isAgentSettingsLocked: boolean;
  onCopy: (target: { scope: string; projectId: string | null }) => void;
}

function CopyRuleDialog({
  open,
  onOpenChange,
  rule,
  scopes,
  isAgentSettingsLocked,
  onCopy,
}: CopyRuleDialogProps) {
  const { t } = useTranslation();
  const defaultTarget = useMemo(() => {
    if (!rule) return "global";
    const ownValue = scopeValue({ scope: rule.scope, projectId: rule.projectId });
    return scopes.find((scope) => scopeValue(scope) !== ownValue)
      ? scopeValue(scopes.find((scope) => scopeValue(scope) !== ownValue)!)
      : "global";
  }, [rule, scopes]);
  const [targetScope, setTargetScope] = useState(defaultTarget);

  useEffect(() => {
    if (!open) return;
    setTargetScope(defaultTarget);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, rule?.id]);

  const availableScopes = useMemo(() => {
    if (!rule) return [];
    const ownValue = scopeValue({ scope: rule.scope, projectId: rule.projectId });
    return scopes.filter((scope) => scopeValue(scope) !== ownValue);
  }, [rule, scopes]);

  const target = parseScopeValue(targetScope);
  const canCopy = availableScopes.length > 0 && !isAgentSettingsLocked;

  return (
    <Dialog.Root
      open={open}
      onOpenChange={onOpenChange}
    >
      <Dialog.Content style={{ maxWidth: 480 }}>
        <Dialog.Title>{t("settingsExtra.rules.copyToScope")}</Dialog.Title>
        <Flex
          direction="column"
          gap="3"
          mt="3"
        >
          <Box>
            <Text
              size="2"
              weight="medium"
            >
              {t("settingsExtra.rules.title")}
            </Text>
            <Text
              size="2"
              mt="1"
              as="div"
              color="gray"
            >
              {rule?.title || t("settingsExtra.rules.untitled")}
            </Text>
          </Box>
          <Box>
            <Text
              size="2"
              weight="medium"
            >
              {t("settingsExtra.rules.content")}
            </Text>
            <Text
              size="2"
              mt="1"
              as="div"
              color="gray"
              className="rules-settings-copy-preview"
            >
              {rule?.content || t("settingsExtra.rules.emptyContent")}
            </Text>
          </Box>
          <Box>
            <Text
              size="2"
              weight="medium"
              mb="2"
              as="div"
            >
              {t("settingsExtra.rules.copyTargetScope")}
            </Text>
            <SimpleSelect
              value={targetScope}
              options={availableScopes.map((scope) => ({
                value: scopeValue(scope),
                label:
                  scope.scope === "global" ? t("settingsExtra.rules.globalScope") : scope.title,
                separatorAfter: scope.scope === "global",
              }))}
              onChange={setTargetScope}
              size="2"
              contentClassName="rules-settings-scope-content"
            />
          </Box>
        </Flex>
        <Flex
          justify="end"
          gap="2"
          mt="4"
        >
          <Button
            variant="soft"
            color="gray"
            onClick={() => onOpenChange(false)}
          >
            {t("common.cancel")}
          </Button>
          <Button
            disabled={!canCopy || !rule}
            onClick={() => onCopy(target)}
          >
            {t("settingsExtra.rules.copyAction")}
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

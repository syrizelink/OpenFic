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
import { Plus, ScrollText, Trash2 } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { ConfirmDialog, ContextMenu, Spinner, toast } from "@/components";
import type { ContextMenuItem, ContextMenuPosition } from "@/components";
import {
  createProjectRule,
  deleteProjectRule,
  fetchProjectRules,
  updateProjectRule,
} from "@/lib/api-client";
import type { ProjectRule } from "@/lib/project-rule.types";
import { createToastThrottler } from "@/lib/ui-utils";

import "./project-rules-sidebar.css";

interface ProjectRulesSidebarProps {
  projectId: string;
  isAgentLocked?: boolean;
  compact?: boolean;
}

interface RuleFormState {
  title: string;
  content: string;
}

export function ProjectRulesSidebar({
  projectId,
  isAgentLocked = false,
  compact = false,
}: ProjectRulesSidebarProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [editingRule, setEditingRule] = useState<ProjectRule | null>(null);
  const [form, setForm] = useState<RuleFormState>({ title: "", content: "" });
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ProjectRule | null>(null);
  const [contextMenuPos, setContextMenuPos] = useState<ContextMenuPosition | null>(null);
  const [contextMenuRule, setContextMenuRule] = useState<ProjectRule | null>(null);

  const showLockedToast = useMemo(
    () => createToastThrottler(t("writing.projectRules.agentLocked")),
    [t],
  );

  const { data, isLoading, error } = useQuery({
    queryKey: ["project-rules", projectId],
    queryFn: () => fetchProjectRules(projectId, { page: 1, pageSize: 100 }),
  });

  const rules = data?.items ?? [];

  const invalidate = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["project-rules", projectId] });
  }, [queryClient, projectId]);

  const createMutation = useMutation({
    mutationFn: () =>
      createProjectRule(projectId, {
        title: t("writing.projectRules.newRule"),
        content: "",
      }),
    onSuccess: (createdRule) => {
      invalidate();
      setEditingRule(createdRule);
      setForm({ title: createdRule.title, content: createdRule.content });
    },
    onError: () => toast.error(t("common.error")),
  });

  const updateMutation = useMutation({
    mutationFn: ({ ruleId, payload }: { ruleId: string; payload: RuleFormState }) =>
      updateProjectRule(projectId, ruleId, payload),
    onSuccess: () => {
      invalidate();
      setEditingRule(null);
    },
    onError: () => toast.error(t("settings.saveFailed")),
  });

  const deleteMutation = useMutation({
    mutationFn: (ruleId: string) => deleteProjectRule(projectId, ruleId),
    onSuccess: () => {
      invalidate();
      setDeleteDialogOpen(false);
      setDeleteTarget(null);
      toast.success(t("common.delete"));
    },
    onError: () => toast.error(t("common.error")),
  });

  const handleCreate = useCallback(() => {
    if (isAgentLocked) {
      showLockedToast();
      return;
    }
    createMutation.mutate();
  }, [createMutation, isAgentLocked, showLockedToast]);

  const handleOpenRule = useCallback((rule: ProjectRule) => {
    setEditingRule(rule);
    setForm({ title: rule.title, content: rule.content });
  }, []);

  const handleSave = useCallback(() => {
    if (!editingRule) return;
    if (isAgentLocked) {
      showLockedToast();
      return;
    }
    updateMutation.mutate({ ruleId: editingRule.id, payload: form });
  }, [editingRule, form, isAgentLocked, showLockedToast, updateMutation]);

  const handleContextMenu = useCallback(
    (rule: ProjectRule, position: ContextMenuPosition) => {
      if (isAgentLocked) return;
      setContextMenuPos(position);
      setContextMenuRule(rule);
    },
    [isAgentLocked],
  );

  const handleCloseContextMenu = useCallback(() => {
    setContextMenuPos(null);
    setContextMenuRule(null);
  }, []);

  const contextMenuItems = useMemo<ContextMenuItem[]>(() => {
    if (!contextMenuRule) return [];
    return [
      {
        id: "delete",
        label: t("common.delete"),
        icon: Trash2,
        danger: true,
        onClick: () => {
          setDeleteTarget(contextMenuRule);
          setDeleteDialogOpen(true);
          handleCloseContextMenu();
        },
      },
    ];
  }, [contextMenuRule, handleCloseContextMenu, t]);

  if (isLoading) {
    return (
      <Flex
        align="center"
        justify="center"
        style={{ flex: 1 }}
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
        p="4"
        style={{ flex: 1 }}
      >
        <Text
          size="2"
          color="red"
        >
          {t("writing.projectRules.loadFailed")}
        </Text>
      </Flex>
    );
  }

  return (
    <Flex
      direction="column"
      style={{ flex: 1, minHeight: 0 }}
    >
      <Box
        px="3"
        py="2"
        style={{ borderBottom: "1px solid var(--gray-a4)" }}
      >
        <Flex
          align="center"
          justify="between"
        >
          <Text
            size="1"
            color="gray"
          >
            {t("writing.projectRules.hint")}
          </Text>
          <Tooltip content={t("writing.projectRules.newRule")}>
            <IconButton
              variant="ghost"
              size="2"
              aria-label={t("writing.projectRules.newRule")}
              onClick={handleCreate}
              disabled={createMutation.isPending}
            >
              <Plus size={16} />
            </IconButton>
          </Tooltip>
        </Flex>
      </Box>

      <Box
        style={{ flex: 1, minHeight: 0, overflowY: "auto" }}
        p={compact ? "1" : "2"}
      >
        {rules.length === 0 ? (
          <Flex
            direction="column"
            align="center"
            justify="center"
            gap="2"
            py="6"
          >
            <ScrollText
              size={20}
              color="var(--gray-8)"
            />
            <Text
              size="1"
              color="gray"
              align="center"
            >
              {t("writing.projectRules.empty")}
            </Text>
          </Flex>
        ) : (
          <Flex
            direction="column"
            gap="1"
          >
            {rules.map((rule) => (
              <button
                key={rule.id}
                type="button"
                onClick={() => handleOpenRule(rule)}
                onContextMenu={(event) => {
                  event.preventDefault();
                  handleContextMenu(rule, { x: event.clientX, y: event.clientY });
                }}
                style={{
                  all: "unset",
                  cursor: "pointer",
                  padding: "6px 8px",
                  borderRadius: "var(--radius-2)",
                  width: "100%",
                  boxSizing: "border-box",
                }}
                className="project-rules-sidebar-item"
              >
                <Flex
                  direction="column"
                  gap="1"
                  style={{ minWidth: 0 }}
                >
                  <Text
                    size="2"
                    truncate
                  >
                    {rule.title || t("writing.projectRules.untitled")}
                  </Text>
                  {rule.content ? (
                    <Text
                      size="1"
                      color="gray"
                      truncate
                    >
                      {rule.content}
                    </Text>
                  ) : null}
                </Flex>
              </button>
            ))}
          </Flex>
        )}
      </Box>

      <ContextMenu
        position={contextMenuPos}
        items={contextMenuItems}
        onClose={handleCloseContextMenu}
      />

      <Dialog.Root
        open={editingRule !== null}
        onOpenChange={(open) => {
          if (!open) setEditingRule(null);
        }}
      >
        <Dialog.Content style={{ maxWidth: 480 }}>
          <Dialog.Title>{t("writing.projectRules.editTitle")}</Dialog.Title>
          <Flex
            direction="column"
            gap="3"
            mt="3"
          >
            <Box>
              <Text
                size="2"
                weight="medium"
                as="label"
              >
                {t("writing.projectRules.title")}
              </Text>
              <TextField.Root
                mt="1"
                value={form.title}
                onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
                placeholder={t("writing.projectRules.titlePlaceholder")}
              />
            </Box>
            <Box>
              <Text
                size="2"
                weight="medium"
                as="label"
              >
                {t("writing.projectRules.content")}
              </Text>
              <TextArea
                mt="1"
                value={form.content}
                onChange={(event) => setForm((prev) => ({ ...prev, content: event.target.value }))}
                placeholder={t("writing.projectRules.contentPlaceholder")}
                rows={8}
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
              onClick={() => setEditingRule(null)}
            >
              {t("common.cancel")}
            </Button>
            <Button
              onClick={handleSave}
              disabled={updateMutation.isPending || !form.title.trim()}
            >
              {updateMutation.isPending ? t("writing.projectRules.saving") : t("common.save")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>

      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={(open) => {
          setDeleteDialogOpen(open);
          if (!open) setDeleteTarget(null);
        }}
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
        title={t("writing.projectRules.deleteTitle")}
        description={t("writing.projectRules.deleteDescription")}
        confirmText={t("common.delete")}
        cancelText={t("common.cancel")}
      />
    </Flex>
  );
}

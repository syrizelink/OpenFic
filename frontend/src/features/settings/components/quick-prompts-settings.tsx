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
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";
import { ContextMenu, type ContextMenuPosition } from "@/components/context-menu";
import { SimpleSelect } from "@/components/select";
import { showErrorToast, toast } from "@/components/toast";
import {
  deleteQuickPrompt,
  fetchAgentRuleScopes,
  fetchQuickPrompts,
  saveQuickPrompt,
} from "@/lib/api-client";
import type { QuickPrompt } from "@/lib/api-client";
import { countTokens } from "@/lib/tiktoken-utils";

import { AgentSettingsLockNotice } from "./agent-settings-lock-notice";

import "./skills-settings.css";
import "./quick-prompts-settings.css";

const MotionBox = motion.create(Box);
const mobilePageVariants = {
  enter: (direction: number) => ({
    transform: direction > 0 ? "translateX(100%)" : "translateX(-100%)",
  }),
  center: { transform: "translateX(0%)" },
  exit: (direction: number) => ({
    transform: direction > 0 ? "translateX(-100%)" : "translateX(100%)",
  }),
};

interface Props {
  mobilePage: "list" | "detail";
  mobileDirection: 1 | -1;
  onMobilePageChange: (page: "list" | "detail") => void;
  onMobileDetailTitleChange: (title: string | null) => void;
  isAgentSettingsLocked: boolean;
  isAgentSettingsLockLoading: boolean;
}

function scopeValue(scope: { scope: string; projectId: string | null }): string {
  return scope.scope === "global" ? "global" : `project:${scope.projectId}`;
}

export function QuickPromptsSettings({
  mobilePage,
  mobileDirection,
  onMobilePageChange,
  onMobileDetailTitleChange,
  isAgentSettingsLocked,
  isAgentSettingsLockLoading,
}: Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedScope, setSelectedScope] = useState("global");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [menuPosition, setMenuPosition] = useState<ContextMenuPosition | null>(null);
  const [menuId, setMenuId] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [copyId, setCopyId] = useState<string | null>(null);
  const [targetScope, setTargetScope] = useState("global");
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);
  const {
    data: prompts = [],
    isLoading,
    error,
  } = useQuery({ queryKey: ["quick-prompts"], queryFn: () => fetchQuickPrompts() });
  const { data: scopesData } = useQuery({
    queryKey: ["agent-rule-scopes"],
    queryFn: fetchAgentRuleScopes,
  });
  const scopes = scopesData?.items ?? [];
  const activePrompts = useMemo(
    () =>
      prompts.filter(
        (prompt) =>
          scopeValue({ scope: prompt.scope, projectId: prompt.project_id }) === selectedScope,
      ),
    [prompts, selectedScope],
  );
  const fuse = useMemo(
    () =>
      new Fuse(activePrompts, {
        keys: [
          { name: "command", weight: 2 },
          { name: "content", weight: 1 },
        ],
        threshold: 0.3,
        ignoreLocation: true,
      }),
    [activePrompts],
  );
  const filteredPrompts = searchQuery.trim()
    ? fuse.search(searchQuery).map((result) => result.item)
    : activePrompts;
  const selectedPrompt =
    activePrompts.find((prompt) => prompt.id === selectedId) ?? activePrompts[0] ?? null;
  const copyPrompt = prompts.find((prompt) => prompt.id === copyId);
  const availableScopes = scopes.filter((scope) => scopeValue(scope) !== selectedScope);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);
  useEffect(() => {
    onMobileDetailTitleChange(selectedPrompt?.command || null);
  }, [onMobileDetailTitleChange, selectedPrompt?.command]);
  useEffect(() => {
    if (scopesData && !scopesData.items.some((scope) => scopeValue(scope) === selectedScope))
      setSelectedScope("global");
  }, [scopesData, selectedScope]);
  useEffect(() => {
    if (isAgentSettingsLocked) {
      setMenuPosition(null);
      setMenuId(null);
      setDeleteId(null);
      setCopyId(null);
    }
  }, [isAgentSettingsLocked]);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["quick-prompts"] });
  const create = useMutation({
    mutationFn: () => {
      let command = "new-prompt";
      let suffix = 2;
      while (activePrompts.some((prompt) => prompt.command === command))
        command = `new-prompt-${suffix++}`;
      return saveQuickPrompt({
        command,
        content: "",
        scope: selectedScope === "global" ? "global" : "project",
        project_id: selectedScope === "global" ? null : selectedScope.slice(8),
      });
    },
    onSuccess: (prompt) => {
      setSelectedId(prompt.id);
      void refresh();
      toast.success(t("settingsExtra.quickPrompts.created"));
    },
    onError: (error) => showErrorToast(t("settingsExtra.quickPrompts.createFailed"), error),
  });
  const update = useMutation({
    mutationFn: ({
      prompt,
      command,
      content,
    }: {
      prompt: QuickPrompt;
      command: string;
      content: string;
    }) =>
      saveQuickPrompt(
        { command, content, scope: prompt.scope, project_id: prompt.project_id },
        prompt.id,
      ),
    onSuccess: (prompt) => {
      queryClient.setQueryData<QuickPrompt[]>(["quick-prompts"], (current) =>
        current?.map((item) => (item.id === prompt.id ? prompt : item)),
      );
      toast.success(t("settingsExtra.quickPrompts.saved"));
    },
    onError: (error) => showErrorToast(t("settingsExtra.quickPrompts.saveFailed"), error),
  });
  const remove = useMutation({
    mutationFn: deleteQuickPrompt,
    onSuccess: () => {
      setDeleteId(null);
      void refresh();
      toast.success(t("settingsExtra.quickPrompts.deleted"));
    },
    onError: (error) => showErrorToast(t("settingsExtra.quickPrompts.deleteFailed"), error),
  });
  const copy = useMutation({
    mutationFn: () => {
      if (!copyPrompt) throw new Error("Quick prompt not found");
      return saveQuickPrompt({
        command: copyPrompt.command,
        content: copyPrompt.content,
        scope: targetScope === "global" ? "global" : "project",
        project_id: targetScope === "global" ? null : targetScope.slice(8),
      });
    },
    onSuccess: () => {
      setCopyId(null);
      void refresh();
      toast.success(t("settingsExtra.quickPrompts.copied"));
    },
    onError: (error) => showErrorToast(t("settingsExtra.quickPrompts.copyFailed"), error),
  });
  const closeMenu = () => {
    setMenuPosition(null);
    setMenuId(null);
  };

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
                {
                  prompts.filter(
                    (prompt) =>
                      scopeValue({ scope: prompt.scope, projectId: prompt.project_id }) ===
                      scopeValue(scope),
                  ).length
                }
              </Badge>
            ),
          }))}
          onChange={(value) => {
            setSelectedScope(value);
            setSelectedId(null);
          }}
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
          <Box className="quick-prompts-search">
            <TextField.Root
              size="2"
              placeholder={t("settingsExtra.quickPrompts.searchPlaceholder")}
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            >
              <TextField.Slot>
                <Search size={14} />
              </TextField.Slot>
              {searchQuery && (
                <TextField.Slot>
                  <IconButton
                    variant="ghost"
                    color="gray"
                    highContrast
                    size="1"
                    aria-label={t("settingsExtra.quickPrompts.clearSearch")}
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
            <Tooltip content={t("settingsExtra.quickPrompts.new")}>
              <IconButton
                size="2"
                variant="ghost"
                color="gray"
                aria-label={t("settingsExtra.quickPrompts.new")}
                disabled={isAgentSettingsLocked || create.isPending}
                onClick={() => create.mutate()}
              >
                <Plus size={14} />
              </IconButton>
            </Tooltip>
          </Flex>
        </Flex>
      </div>
      <div className="skills-settings-list">
        {filteredPrompts.length === 0 ? (
          <Flex
            align="center"
            justify="center"
            p="6"
            className="quick-prompts-list-empty"
          >
            <Text
              size="2"
              color="gray"
              align="center"
            >
              {searchQuery.trim()
                ? t("settingsExtra.quickPrompts.noSearchResults")
                : t("settingsExtra.quickPrompts.empty")}
            </Text>
          </Flex>
        ) : (
          <Flex
            direction="column"
            gap="2"
            className="skills-settings-list-body"
          >
            {filteredPrompts.map((prompt) => (
              <div
                key={prompt.id}
                role="button"
                tabIndex={0}
                className={`skills-settings-list-item${prompt.id === selectedPrompt?.id ? " skills-settings-list-item--selected" : ""}${prompt.id === menuId ? " skills-settings-list-item--menu-open" : ""}`}
                onClick={() => {
                  setSelectedId(prompt.id);
                  if (isMobile) onMobilePageChange("detail");
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelectedId(prompt.id);
                    if (isMobile) onMobilePageChange("detail");
                  }
                }}
                onContextMenu={(event) => {
                  if (isAgentSettingsLocked) return;
                  event.preventDefault();
                  setMenuId(prompt.id);
                  setMenuPosition({ x: event.clientX, y: event.clientY });
                }}
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
                      weight={prompt.id === selectedPrompt?.id ? "medium" : "regular"}
                    >
                      /{prompt.command}
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
                      disabled={isAgentSettingsLocked}
                      onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        const rect = event.currentTarget.getBoundingClientRect();
                        setMenuId(prompt.id);
                        setMenuPosition({ x: rect.right, y: rect.bottom + 4 });
                      }}
                    >
                      <MoreHorizontal size={14} />
                    </IconButton>
                  </Flex>
                </Flex>
              </div>
            ))}
          </Flex>
        )}
      </div>
    </div>
  );

  if (isLoading || isAgentSettingsLockLoading)
    return (
      <Flex
        align="center"
        justify="center"
        className="quick-prompts-list-empty"
      >
        <Spinner size={18} />
      </Flex>
    );
  if (error)
    return (
      <Flex
        align="center"
        justify="center"
        className="quick-prompts-list-empty"
      >
        <Text color="red">{t("settingsExtra.quickPrompts.loadFailed")}</Text>
      </Flex>
    );
  const detailContent = selectedPrompt ? (
    <QuickPromptEditor
      key={selectedPrompt.id}
      prompt={selectedPrompt}
      isLocked={isAgentSettingsLocked}
      onSave={(command, content) =>
        update.mutateAsync({ prompt: selectedPrompt, command, content })
      }
    />
  ) : (
    <Box className="skills-settings-empty-state">
      <Text
        size="2"
        color="gray"
      >
        {t("settingsExtra.quickPrompts.select")}
      </Text>
    </Box>
  );

  return (
    <Flex
      direction="column"
      className="skills-settings skills-settings--settings"
    >
      <AgentSettingsLockNotice isLocked={isAgentSettingsLocked} />
      {isMobile ? (
        <Box className="settings-dialog-mobile-page-stack">
          <AnimatePresence
            initial={false}
            custom={mobileDirection}
            mode="sync"
          >
            {mobilePage === "list" ? (
              <MotionBox
                key="quick-prompts-list"
                custom={mobileDirection}
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
                key="quick-prompts-detail"
                custom={mobileDirection}
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
      ) : (
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
      )}
      <ContextMenu
        position={menuPosition}
        items={
          !menuId || isAgentSettingsLocked
            ? []
            : [
                {
                  id: "copy",
                  label: t("settingsExtra.rules.copyToScope"),
                  icon: Copy,
                  onClick: () => {
                    setCopyId(menuId);
                    setTargetScope(availableScopes[0] ? scopeValue(availableScopes[0]) : "global");
                    closeMenu();
                  },
                },
                {
                  id: "delete",
                  label: t("common.delete"),
                  icon: Trash2,
                  danger: true,
                  onClick: () => {
                    setDeleteId(menuId);
                    closeMenu();
                  },
                },
              ]
        }
        onClose={closeMenu}
      />
      <Dialog.Root
        open={deleteId !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteId(null);
        }}
      >
        <Dialog.Content maxWidth="420px">
          <Dialog.Title>{t("settingsExtra.quickPrompts.deleteTitle")}</Dialog.Title>
          <Dialog.Description
            size="2"
            mt="2"
          >
            {t("settingsExtra.quickPrompts.deleteConfirm")}
          </Dialog.Description>
          <Flex
            justify="end"
            gap="2"
            mt="4"
          >
            <Button
              variant="soft"
              color="gray"
              onClick={() => setDeleteId(null)}
            >
              {t("common.cancel")}
            </Button>
            <Button
              color="red"
              disabled={isAgentSettingsLocked || remove.isPending}
              onClick={() => {
                if (deleteId) remove.mutate(deleteId);
              }}
            >
              {t("common.delete")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
      <Dialog.Root
        open={copyId !== null}
        onOpenChange={(open) => {
          if (!open) setCopyId(null);
        }}
      >
        <Dialog.Content maxWidth="480px">
          <Dialog.Title>{t("settingsExtra.rules.copyToScope")}</Dialog.Title>
          <Dialog.Description
            size="2"
            mt="2"
          >
            {t("settingsExtra.quickPrompts.copyDescription")}
          </Dialog.Description>
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
                {t("settingsExtra.quickPrompts.command")}
              </Text>
              <Text
                size="2"
                mt="1"
                as="div"
                color="gray"
              >
                {copyPrompt?.command}
              </Text>
            </Box>
            <Box>
              <Text
                size="2"
                weight="medium"
              >
                {t("settingsExtra.quickPrompts.content")}
              </Text>
              <Text
                size="2"
                mt="1"
                as="div"
                color="gray"
                className="rules-settings-copy-preview"
              >
                {copyPrompt?.content || t("settingsExtra.rules.emptyContent")}
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
              onClick={() => setCopyId(null)}
            >
              {t("common.cancel")}
            </Button>
            <Button
              disabled={!availableScopes.length || isAgentSettingsLocked || copy.isPending}
              onClick={() => copy.mutate()}
            >
              {t("settingsExtra.rules.copyAction")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
    </Flex>
  );
}

function QuickPromptEditor({
  prompt,
  isLocked,
  onSave,
}: {
  prompt: QuickPrompt;
  isLocked: boolean;
  onSave: (command: string, content: string) => Promise<unknown>;
}) {
  const { t } = useTranslation();
  const [form, setForm] = useState({ command: prompt.command, content: prompt.content });
  const [saved, setSaved] = useState(() => JSON.stringify(form));
  const [isSaving, setIsSaving] = useState(false);
  const tokenCount = useMemo(() => countTokens(form.content), [form.content]);
  const canSave =
    !isLocked &&
    !isSaving &&
    JSON.stringify(form) !== saved &&
    /^[^\s/]+$/.test(form.command.trim());
  const handleSave = async () => {
    if (!canSave) return;
    const current = JSON.stringify(form);
    setIsSaving(true);
    try {
      await onSave(form.command, form.content);
      setSaved(current);
    } catch {
      return;
    } finally {
      setIsSaving(false);
    }
  };
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
              {t("settingsExtra.quickPrompts.command")}
            </Text>
            <TextField.Root
              mt="2"
              value={form.command}
              onChange={(event) => setForm({ ...form, command: event.target.value })}
              placeholder={t("settingsExtra.quickPrompts.commandPlaceholder")}
              disabled={isLocked}
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
                {t("settingsExtra.quickPrompts.content")}
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
              onChange={(event) => setForm({ ...form, content: event.target.value })}
              placeholder={t("settingsExtra.quickPrompts.contentPlaceholder")}
              rows={18}
              disabled={isLocked}
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

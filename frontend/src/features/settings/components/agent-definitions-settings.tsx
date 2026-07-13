import {
  Box,
  Button,
  Checkbox,
  Flex,
  Switch,
  ScrollArea,
  Text,
  TextArea,
  TextField,
  Dialog,
  IconButton,
  Select,
  Badge,
} from "@radix-ui/themes";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  Copy,
  Crown,
  ExternalLink,
  MoreHorizontal,
  Plus,
  RefreshCw,
  RotateCcw,
  Trash2,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, useCallback, useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { ModelIdSelect, type ModelIdSelectOption } from "@/components";
import { ContextMenu, type ContextMenuItem, toast, ConfirmDialog, Spinner } from "@/components";
import { fetchSkills } from "@/lib/api-client";
import type { Skill } from "@/lib/skill.types";
import { useLlmModelOptions } from "@/lib/use-llm-model-options";

import {
  AGENT_DEFINITION_MENU_ACTIONS,
  getAgentDefinitionMenuActions,
} from "../lib/agent-definition-menu";
import {
  fetchAgentToolCategories,
  fetchAgentDefinitions,
  createAgentDefinition,
  updateAgentDefinition,
  resetAgentDefinition,
  deleteAgentDefinition,
} from "../lib/agent-definitions-api";
import type {
  AgentToolCategoryResponse,
  AgentDefinitionResponse,
  AgentDefinitionCreateRequest,
} from "../lib/agent-definitions.types";
import {
  getAgentKindLabel,
  getAgentKindOptions,
  SYSTEM_DEFAULT_MODEL_REFERENCE,
  SYSTEM_LIGHT_MODEL_REFERENCE,
} from "../lib/agent-definitions.types";
import { fetchSettings } from "../lib/settings-api";
import { AgentSettingsLockNotice } from "./agent-settings-lock-notice";

const LIST_WIDTH = 280;
const SUBAGENT_RESTRICTED_TOOL_CATEGORIES = new Set(["orchestration", "interaction"]);
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

interface AgentListMenuState {
  key: string;
  position: { x: number; y: number };
}

function getEffectiveModelSelection(modelId: string | null): string {
  if (!modelId) return SYSTEM_DEFAULT_MODEL_REFERENCE;
  return modelId;
}

function getEnabledToolCategoriesForAgent(
  kind: "primary" | "subagent",
  categories: string[],
): string[] {
  if (kind !== "subagent") return categories;
  return categories.filter((category) => !SUBAGENT_RESTRICTED_TOOL_CATEGORIES.has(category));
}

function buildAgentModelOptions(
  llmModelOptions: ModelIdSelectOption[],
  t: (key: string) => string,
): ModelIdSelectOption[] {
  return [
    {
      value: SYSTEM_DEFAULT_MODEL_REFERENCE,
      id: t("settings.agentsFollowSystemSetting"),
      name: t("settings.agentsSystemDefaultModel"),
      taskType: "llm",
    },
    {
      value: SYSTEM_LIGHT_MODEL_REFERENCE,
      id: t("settings.agentsFollowSystemSetting"),
      name: t("settings.agentsSystemLightModel"),
      taskType: "llm",
    },
    ...llmModelOptions,
  ];
}

interface AgentFormProps {
  def: AgentDefinitionResponse;
  definitions: AgentDefinitionResponse[];
  llmModelOptions: ModelIdSelectOption[];
  hasLlmModels: boolean;
  toolCategoryOptions: AgentToolCategoryResponse[];
  skills: Skill[];
  onCloseSettings?: () => void;
  onUpdated: () => void;
  isAgentSettingsLocked: boolean;
}

function AgentForm({
  def,
  definitions,
  llmModelOptions,
  hasLlmModels,
  toolCategoryOptions,
  skills,
  onCloseSettings,
  onUpdated,
  isAgentSettingsLocked,
}: AgentFormProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const fieldLabelStyle = useMemo(() => ({ fontSize: 14 }), []);

  const [formDisplayName, setFormDisplayName] = useState(def.display_name);
  const [formDescription, setFormDescription] = useState(def.description);
  const [formModelId, setFormModelId] = useState(getEffectiveModelSelection(def.model_id));
  const [formEnabledToolCategories, setFormEnabledToolCategories] = useState<string[]>([
    ...getEnabledToolCategoriesForAgent(def.kind, def.enabled_tool_categories),
  ]);
  const [formEnabledSkills, setFormEnabledSkills] = useState<string[]>([...def.enabled_skills]);
  const [formDelegatableAgents, setFormDelegatableAgents] = useState<string[]>([
    ...def.delegatable_agents,
  ]);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  const allSubagents = useMemo(
    () => definitions.filter((d) => d.kind === "subagent" && d.enabled),
    [definitions],
  );

  const delegatableOptions = useMemo(
    () =>
      allSubagents
        .filter((d) => d.key !== def.key)
        .map((d) => ({
          value: d.key,
          label: d.display_name || d.key,
        })),
    [allSubagents, def.key],
  );

  const hasFormChanges = useMemo(() => {
    return (
      formDisplayName !== def.display_name ||
      formDescription !== def.description ||
      formModelId !== getEffectiveModelSelection(def.model_id) ||
      JSON.stringify(formEnabledToolCategories) !==
        JSON.stringify(getEnabledToolCategoriesForAgent(def.kind, def.enabled_tool_categories)) ||
      JSON.stringify(formEnabledSkills) !== JSON.stringify(def.enabled_skills) ||
      JSON.stringify(formDelegatableAgents) !== JSON.stringify(def.delegatable_agents)
    );
  }, [
    def,
    formDescription,
    formDisplayName,
    formModelId,
    formEnabledToolCategories,
    formEnabledSkills,
    formDelegatableAgents,
  ]);

  const isPrimary = def.kind === "primary";
  const selectableToolCategoryOptions = useMemo(
    () =>
      toolCategoryOptions.filter(
        (option) => def.kind !== "subagent" || !SUBAGENT_RESTRICTED_TOOL_CATEGORIES.has(option.key),
      ),
    [def.kind, toolCategoryOptions],
  );

  const updateMutation = useMutation({
    mutationFn: async () => {
      return updateAgentDefinition(def.key, {
        display_name: formDisplayName,
        description: formDescription,
        model_id: formModelId,
        enabled_tool_categories: formEnabledToolCategories,
        enabled_skills: formEnabledSkills,
        delegatable_agents: formDelegatableAgents,
      });
    },
    onSuccess: () => {
      onUpdated();
      toast.success(t("common.saveSuccess"));
    },
    onError: () => toast.error(t("settings.agentsSaveFailed")),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteAgentDefinition(def.key),
    onSuccess: () => {
      onUpdated();
      setConfirmDeleteOpen(false);
      toast.success(t("settings.agentsDeleteSuccess"));
    },
    onError: () => toast.error(t("settings.agentsDeleteFailed")),
  });

  const handleGoToPromptChain = useCallback(() => {
    onCloseSettings?.();
    const params = new URLSearchParams({
      prompt: `${def.source === "builtin" ? "builtin-agent" : "custom-agent"}--${def.key}`,
    });
    navigate(`/prompt-chains?${params.toString()}`);
  }, [def.key, def.source, navigate, onCloseSettings]);

  const handleToggleDelegatable = useCallback((key: string) => {
    setFormDelegatableAgents((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  }, []);

  const handleToggleToolCategory = useCallback((key: string) => {
    setFormEnabledToolCategories((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key],
    );
  }, []);

  const handleToggleEnabledSkill = useCallback((skillId: string) => {
    setFormEnabledSkills((prev) =>
      prev.includes(skillId) ? prev.filter((id) => id !== skillId) : [...prev, skillId],
    );
  }, []);

  const selectableSkills = useMemo(() => skills.filter((skill) => skill.name.trim()), [skills]);

  return (
    <Flex
      direction="column"
      gap="5"
      key={def.key}
      className="agent-definition-form"
    >
      <Flex
        direction="column"
        gap="1"
      >
        <Text
          size="1"
          weight="medium"
          style={fieldLabelStyle}
        >
          {t("settings.agentsDisplayName")}
        </Text>
        <TextField.Root
          value={formDisplayName}
          onChange={(e) => setFormDisplayName(e.target.value)}
          placeholder={t("settings.agentsDisplayNamePlaceholder")}
          disabled={isAgentSettingsLocked}
        />
      </Flex>

      <Flex
        direction="column"
        gap="1"
      >
        <Text
          size="1"
          weight="medium"
          style={fieldLabelStyle}
        >
          {t("settings.agentsFieldDescription")}
        </Text>
        <TextArea
          value={formDescription}
          onChange={(event) => setFormDescription(event.target.value)}
          rows={3}
          placeholder={t("settings.agentsDescriptionPlaceholder")}
          disabled={isAgentSettingsLocked}
        />
      </Flex>

      <Flex
        direction="column"
        gap="1"
      >
        <Text
          size="1"
          weight="medium"
          style={fieldLabelStyle}
        >
          {t("settings.agentsModelId")}
        </Text>
        <ModelIdSelect
          value={formModelId}
          models={llmModelOptions}
          onChange={setFormModelId}
          editable={false}
          allowCustomValue={false}
          disabled={isAgentSettingsLocked || !hasLlmModels}
          triggerStyle={{ width: "100%" }}
        />
      </Flex>

      <Flex
        direction="column"
        gap="1"
      >
        <Text
          size="1"
          weight="medium"
          style={fieldLabelStyle}
        >
          {t("settings.agentsToolCategories")}
        </Text>
        {selectableToolCategoryOptions.length === 0 ? (
          <Text
            size="2"
            color="gray"
          >
            {t("settings.agentsNoTools")}
          </Text>
        ) : (
          <Flex
            wrap="wrap"
            gap="2"
          >
            {selectableToolCategoryOptions.map((opt) => (
              <label
                key={opt.key}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "4px 10px",
                  borderRadius: 6,
                  border: "1px solid var(--gray-a5)",
                  cursor: isAgentSettingsLocked ? "not-allowed" : "pointer",
                  fontSize: 13,
                }}
              >
                <Checkbox
                  checked={formEnabledToolCategories.includes(opt.key)}
                  disabled={isAgentSettingsLocked}
                  onCheckedChange={() => handleToggleToolCategory(opt.key)}
                  style={{ margin: 0 }}
                />
                {opt.name}
              </label>
            ))}
          </Flex>
        )}
      </Flex>

      <Flex
        direction="column"
        gap="1"
      >
        <Text
          size="1"
          weight="medium"
          style={fieldLabelStyle}
        >
          {t("settings.agentsEnabledSkills")}
        </Text>
        {selectableSkills.length === 0 ? (
          <Text
            size="2"
            color="gray"
          >
            {t("settings.agentsNoSkills")}
          </Text>
        ) : (
          <Flex
            wrap="wrap"
            gap="2"
          >
            {selectableSkills.map((skill) => {
              const disabled = isAgentSettingsLocked || !skill.isEnabled || !skill.isComplete;
              return (
                <label
                  key={skill.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "4px 10px",
                    borderRadius: 6,
                    border: "1px solid var(--gray-a5)",
                    cursor: disabled ? "not-allowed" : "pointer",
                    opacity: disabled ? 0.6 : 1,
                    fontSize: 13,
                  }}
                  title={disabled ? t("settings.agentsSkillUnavailable") : skill.name}
                >
                  <Checkbox
                    checked={formEnabledSkills.includes(skill.id)}
                    disabled={disabled}
                    onCheckedChange={() => handleToggleEnabledSkill(skill.id)}
                    style={{ margin: 0 }}
                  />
                  {skill.name || t("settingsExtra.skills.untitled")}
                </label>
              );
            })}
          </Flex>
        )}
      </Flex>

      {isPrimary && (
        <Flex
          direction="column"
          gap="2"
        >
          <Text
            size="1"
            weight="medium"
            style={fieldLabelStyle}
          >
            {t("settings.agentsDelegatableAgents")}
          </Text>
          {delegatableOptions.length === 0 ? (
            <Text
              size="2"
              color="gray"
            >
              {t("settings.agentsNoDelegatableAgents")}
            </Text>
          ) : (
            <Flex
              wrap="wrap"
              gap="2"
            >
              {delegatableOptions.map((opt) => (
                <label
                  key={opt.value}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "4px 10px",
                    borderRadius: 6,
                    border: "1px solid var(--gray-a5)",
                    cursor: isAgentSettingsLocked ? "not-allowed" : "pointer",
                    fontSize: 13,
                  }}
                >
                  <Checkbox
                    checked={formDelegatableAgents.includes(opt.value)}
                    disabled={isAgentSettingsLocked}
                    onCheckedChange={() => handleToggleDelegatable(opt.value)}
                    style={{ margin: 0 }}
                  />
                  {opt.label}
                </label>
              ))}
            </Flex>
          )}
        </Flex>
      )}

      <Flex
        direction="column"
        gap="1"
      >
        <Text
          size="1"
          weight="medium"
          style={fieldLabelStyle}
        >
          {t("settings.agentsPromptChain")}
        </Text>
        <Flex
          align="center"
          gap="1"
          wrap="wrap"
        >
          <Text
            size="2"
            color="gray"
          >
            {t("settings.agentsPromptChainLocationPrefix", { agent: def.key })}
          </Text>
          <button
            type="button"
            onClick={handleGoToPromptChain}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: 0,
              border: "none",
              background: "transparent",
              color: "var(--accent-11)",
              textDecoration: "underline",
              cursor: "pointer",
              font: "inherit",
            }}
          >
            <Text
              size="2"
              style={{ color: "inherit" }}
            >
              {t("settings.agentsPromptChainAction")}
            </Text>
            <ExternalLink size={14} />
          </button>
        </Flex>
      </Flex>

      <Flex
        direction="column"
        gap="2"
        style={{ marginTop: 8 }}
      >
        <Button
          size="2"
          disabled={isAgentSettingsLocked || !hasFormChanges || updateMutation.isPending}
          onClick={() => updateMutation.mutate()}
          style={{ alignSelf: "flex-start" }}
        >
          {updateMutation.isPending ? t("common.loading") : t("common.save")}
        </Button>
      </Flex>

      <ConfirmDialog
        open={confirmDeleteOpen}
        onOpenChange={(open) => !open && setConfirmDeleteOpen(false)}
        title={t("settings.agentsDelete")}
        description={`${t("settings.agentsDeleteConfirmPrefix")}「${def.display_name}」${t("settings.agentsDeleteConfirmSuffix")}`}
        onConfirm={() => deleteMutation.mutate()}
        confirmText={t("common.delete")}
        cancelText={t("common.cancel")}
        loading={deleteMutation.isPending}
      />
    </Flex>
  );
}

interface AgentDefinitionsSettingsProps {
  onCloseSettings?: () => void;
  mobilePage?: "list" | "detail";
  mobileDirection?: 1 | -1;
  onMobileDetailTitleChange?: (title: string | null) => void;
  onMobilePageChange?: (page: "list" | "detail") => void;
  isAgentSettingsLocked: boolean;
  isAgentSettingsLockLoading: boolean;
}

export function AgentDefinitionsSettings({
  onCloseSettings,
  mobilePage,
  mobileDirection: controlledMobileDirection,
  onMobileDetailTitleChange,
  onMobilePageChange,
  isAgentSettingsLocked,
  isAgentSettingsLockLoading,
}: AgentDefinitionsSettingsProps) {
  const { t } = useTranslation();
  const agentKindOptions = getAgentKindOptions();
  const queryClient = useQueryClient();

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [createMode, setCreateMode] = useState<"create" | "copy">("create");
  const [copySource, setCopySource] = useState<AgentDefinitionResponse | null>(null);
  const [newKind, setNewKind] = useState<"primary" | "subagent">("primary");
  const [newKey, setNewKey] = useState("");
  const [newDisplayName, setNewDisplayName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [menuState, setMenuState] = useState<AgentListMenuState | null>(null);
  const [confirmResetKey, setConfirmResetKey] = useState<string | null>(null);
  const [confirmDeleteKey, setConfirmDeleteKey] = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(false);
  const [internalMobilePage, setInternalMobilePage] = useState<"list" | "detail">("list");
  const [internalMobileDirection, setInternalMobileDirection] = useState<1 | -1>(1);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const {
    data: definitions = [],
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["agent-definitions"],
    queryFn: fetchAgentDefinitions,
    staleTime: 0,
    refetchOnMount: "always",
  });

  const {
    data: toolCategoryOptions = [],
    isLoading: isToolCategoriesLoading,
    isFetching: isToolCategoriesFetching,
  } = useQuery({
    queryKey: ["agent-tool-categories"],
    queryFn: fetchAgentToolCategories,
    staleTime: 0,
    refetchOnMount: "always",
  });

  const {
    data: skillsData,
    isLoading: isSkillsLoading,
    isFetching: isSkillsFetching,
  } = useQuery({
    queryKey: ["skills"],
    queryFn: () => fetchSkills({ page: 1, pageSize: 100 }),
    staleTime: 0,
    refetchOnMount: "always",
  });
  const skills = useMemo(() => skillsData?.items ?? [], [skillsData?.items]);

  const {
    data: settings,
    isLoading: isSettingsLoading,
    isFetching: isSettingsFetching,
  } = useQuery({
    queryKey: ["settings"],
    queryFn: fetchSettings,
  });

  const { options: llmModelOptions, isLoading: isModelOptionsLoading } = useLlmModelOptions();
  const hasLlmModels = llmModelOptions.length > 0;
  const modelOptions = useMemo(
    () => buildAgentModelOptions(llmModelOptions, t),
    [llmModelOptions, t],
  );

  const effectiveSelectedKey = useMemo(() => {
    if (selectedKey && definitions.some((item) => item.key === selectedKey)) {
      return selectedKey;
    }
    return definitions[0]?.key ?? null;
  }, [definitions, selectedKey]);

  const selectedDef = useMemo(
    () => definitions.find((d) => d.key === effectiveSelectedKey) ?? null,
    [definitions, effectiveSelectedKey],
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

  const isContentLoading =
    isLoading ||
    isFetching ||
    isToolCategoriesLoading ||
    isToolCategoriesFetching ||
    isSkillsLoading ||
    isSkillsFetching ||
    isSettingsLoading ||
    isSettingsFetching ||
    isModelOptionsLoading ||
    isAgentSettingsLockLoading ||
    !settings;

  useEffect(() => {
    onMobileDetailTitleChange?.(selectedDef?.display_name || null);
  }, [onMobileDetailTitleChange, selectedDef]);

  const orderedDefinitions = useMemo(
    () =>
      [...definitions].sort((left, right) => {
        if (left.source === right.source) return 0;
        return left.source === "builtin" ? -1 : 1;
      }),
    [definitions],
  );

  const menuTarget = useMemo(
    () => definitions.find((item) => item.key === menuState?.key) ?? null,
    [definitions, menuState],
  );

  const resetTarget = useMemo(
    () => definitions.find((item) => item.key === confirmResetKey) ?? null,
    [confirmResetKey, definitions],
  );

  const deleteTarget = useMemo(
    () => definitions.find((item) => item.key === confirmDeleteKey) ?? null,
    [confirmDeleteKey, definitions],
  );

  const invalidateDefs = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["agent-definitions"] });
  }, [queryClient]);

  const closeCreateDialog = useCallback(() => {
    setIsCreating(false);
    setCreateMode("create");
    setCopySource(null);
    setNewKind("primary");
    setNewKey("");
    setNewDisplayName("");
    setNewDescription("");
  }, []);

  useEffect(() => {
    if (!isAgentSettingsLocked) return;
    closeCreateDialog();
    setMenuState(null);
    setConfirmResetKey(null);
    setConfirmDeleteKey(null);
  }, [closeCreateDialog, isAgentSettingsLocked]);

  const openCreateDialog = useCallback(() => {
    if (isAgentSettingsLocked) return;
    setCreateMode("create");
    setCopySource(null);
    setNewKind("primary");
    setNewKey("");
    setNewDisplayName("");
    setNewDescription("");
    setIsCreating(true);
  }, [isAgentSettingsLocked]);

  const openCopyDialog = useCallback(
    (def: AgentDefinitionResponse) => {
      if (isAgentSettingsLocked) return;
      setCreateMode("copy");
      setCopySource(def);
      setNewKind(def.kind);
      setNewKey(`${def.key}-copy`.replace(/[^a-z0-9-]/g, "").slice(0, 50));
      setNewDisplayName(`${def.display_name} ${t("settings.agentsCopySuffix")}`);
      setNewDescription(def.description);
      setIsCreating(true);
    },
    [isAgentSettingsLocked, t],
  );

  const createMutation = useMutation({
    mutationFn: async () => {
      const sourceDefinition = copySource;
      const data: AgentDefinitionCreateRequest = {
        key: newKey.trim(),
        display_name: newDisplayName,
        description: newDescription,
        kind: newKind,
        prompt_agent_name: newKey.trim(),
        model_id: sourceDefinition?.model_id ?? SYSTEM_DEFAULT_MODEL_REFERENCE,
        enabled_tool_categories: getEnabledToolCategoriesForAgent(
          newKind,
          sourceDefinition?.enabled_tool_categories ?? [],
        ),
        enabled_skills: sourceDefinition?.enabled_skills ?? [],
        metadata: sourceDefinition?.metadata ?? {},
        delegatable_agents: sourceDefinition?.delegatable_agents ?? [],
      };
      const created = await createAgentDefinition(data);
      if (sourceDefinition && sourceDefinition.enabled === false) {
        return updateAgentDefinition(created.key, { enabled: false });
      }
      return created;
    },
    onSuccess: (result) => {
      invalidateDefs();
      closeCreateDialog();
      setSelectedKey(result.key);
      if (isMobile) handleMobilePageChange("detail");
      toast.success(
        createMode === "copy" ? t("settings.agentsCopySuccess") : t("settings.agentsCreateSuccess"),
      );
    },
    onError: () =>
      toast.error(
        createMode === "copy" ? t("settings.agentsCopyFailed") : t("settings.agentsCreateFailed"),
      ),
  });

  const resetMutation = useMutation({
    mutationFn: (key: string) => resetAgentDefinition(key),
    onSuccess: (result: AgentDefinitionResponse) => {
      invalidateDefs();
      setConfirmResetKey(null);
      setSelectedKey(result.key);
      toast.success(t("settings.agentsResetSuccess"));
    },
    onError: () => toast.error(t("settings.agentsResetFailed")),
  });

  const deleteMutation = useMutation({
    mutationFn: (key: string) => deleteAgentDefinition(key),
    onSuccess: () => {
      invalidateDefs();
      setConfirmDeleteKey(null);
      toast.success(t("settings.agentsDeleteSuccess"));
    },
    onError: () => toast.error(t("settings.agentsDeleteFailed")),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      updateAgentDefinition(key, { enabled }),
    onMutate: async ({ key, enabled }) => {
      await queryClient.cancelQueries({ queryKey: ["agent-definitions"] });
      const previous = queryClient.getQueryData<AgentDefinitionResponse[]>(["agent-definitions"]);

      if (previous) {
        queryClient.setQueryData<AgentDefinitionResponse[]>(
          ["agent-definitions"],
          previous.map((item) => (item.key === key ? { ...item, enabled } : item)),
        );
      }

      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["agent-definitions"], context.previous);
      }
      toast.error(t("common.error"));
    },
    onSuccess: (updatedDef) => {
      queryClient.setQueryData<AgentDefinitionResponse[]>(["agent-definitions"], (current) => {
        if (!current) return current;
        return current.map((item) => (item.key === updatedDef.key ? updatedDef : item));
      });
      toast.success(updatedDef.enabled ? t("worldInfo.enabled") : t("worldInfo.disabled"));
    },
    onSettled: () => {
      invalidateDefs();
    },
  });

  const openMenuAt = useCallback(
    (key: string, position: { x: number; y: number }) => {
      if (isAgentSettingsLocked) return;
      setMenuState({ key, position });
    },
    [isAgentSettingsLocked],
  );

  const closeMenu = useCallback(() => {
    setMenuState(null);
  }, []);

  const menuItems = useMemo<ContextMenuItem[]>(() => {
    if (!menuTarget || isAgentSettingsLocked) return [];

    const actions = getAgentDefinitionMenuActions(menuTarget);
    const items: ContextMenuItem[] = [];

    if (actions.includes(AGENT_DEFINITION_MENU_ACTIONS.copy)) {
      items.push({
        id: "copy",
        label: t("settings.agentsCopy"),
        icon: Copy,
        onClick: () => {
          openCopyDialog(menuTarget);
          closeMenu();
        },
      });
    }

    if (actions.includes(AGENT_DEFINITION_MENU_ACTIONS.delete)) {
      items.push({
        id: "delete",
        label: t("settings.agentsDelete"),
        icon: Trash2,
        danger: true,
        onClick: () => {
          setSelectedKey(menuTarget.key);
          setConfirmDeleteKey(menuTarget.key);
          closeMenu();
        },
      });
    }

    if (actions.includes(AGENT_DEFINITION_MENU_ACTIONS.reset)) {
      items.push({
        id: "reset",
        label: t("settings.agentsReset"),
        icon: RotateCcw,
        onClick: () => {
          setSelectedKey(menuTarget.key);
          setConfirmResetKey(menuTarget.key);
          closeMenu();
        },
      });
    }

    return items;
  }, [
    closeMenu,
    menuTarget,
    openCopyDialog,
    setConfirmDeleteKey,
    setConfirmResetKey,
    setSelectedKey,
    t,
    isAgentSettingsLocked,
  ]);

  const renderAgentListItem = (def: AgentDefinitionResponse) => (
    <div
      key={def.key}
      role="button"
      tabIndex={0}
      className={`agent-definition-item${effectiveSelectedKey === def.key ? " agent-definition-item--active" : ""}${menuState?.key === def.key ? " agent-definition-item--menu-open" : ""}`}
      onClick={() => {
        setSelectedKey(def.key);
        if (isMobile) handleMobilePageChange("detail");
      }}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          setSelectedKey(def.key);
          if (isMobile) handleMobilePageChange("detail");
        }
      }}
      onContextMenu={(event) => {
        event.preventDefault();
        openMenuAt(def.key, { x: event.clientX, y: event.clientY });
      }}
    >
      <Flex
        direction="column"
        gap="1"
        className="agent-definition-item-content"
      >
        <Flex
          align="start"
          justify="between"
          gap="2"
          className="agent-definition-item-row"
        >
          <Flex
            align="center"
            gap="2"
            className="agent-definition-item-title-row"
          >
            <span
              className="agent-definition-kind-icon"
              aria-label={getAgentKindLabel(def.kind)}
              title={getAgentKindLabel(def.kind)}
            >
              {def.kind === "primary" ? <Crown size={14} /> : <Bot size={14} />}
            </span>
            <Text
              size="2"
              truncate
              weight={effectiveSelectedKey === def.key ? "medium" : "regular"}
            >
              {def.display_name}
            </Text>
            {def.source === "builtin" ? (
              <Badge
                size="1"
                variant="soft"
                color="green"
              >
                {t("settings.agentsBuiltin")}
              </Badge>
            ) : null}
          </Flex>

          <Flex
            align="center"
            gap="1"
            className="agent-definition-item-actions"
          >
            <Switch
              size="1"
              checked={def.enabled}
              disabled={isAgentSettingsLocked || toggleMutation.isPending}
              onClick={(event) => event.stopPropagation()}
              onCheckedChange={(checked) => {
                void toggleMutation.mutateAsync({ key: def.key, enabled: checked === true });
              }}
            />
            <IconButton
              type="button"
              variant="ghost"
              color="gray"
              size="1"
              className="agent-definition-item-menu"
              aria-label={t("settings.agentsMenu")}
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                const rect = event.currentTarget.getBoundingClientRect();
                openMenuAt(def.key, { x: rect.right, y: rect.bottom + 4 });
              }}
              disabled={isAgentSettingsLocked}
            >
              <MoreHorizontal size={14} />
            </IconButton>
          </Flex>
        </Flex>
        <Text
          size="1"
          color="gray"
          className="agent-definition-item-description"
        >
          {def.description || t("settings.agentsNoDescription")}
        </Text>
      </Flex>
    </div>
  );

  const listContent = (
    <Box
      className="agent-definitions-list-panel"
      style={isMobile ? undefined : { width: LIST_WIDTH }}
    >
      <Box className="agent-definitions-list-header">
        <Flex
          align="center"
          justify="between"
          gap="2"
          className="agent-definitions-list-header-row"
        >
          <Text
            size="2"
            weight="medium"
            className="agent-definitions-list-count"
          >
            {t("settings.agentsTotalCount", { count: definitions.length })}
          </Text>
          <Flex
            align="center"
            gap="1"
            className="agent-definitions-list-actions"
          >
            <IconButton
              size="2"
              variant="ghost"
              color="gray"
              aria-label={t("settings.agentsNewAgent")}
              onClick={openCreateDialog}
              disabled={isAgentSettingsLocked}
            >
              <Plus size={14} />
            </IconButton>
            <IconButton
              size="2"
              variant="ghost"
              color="gray"
              aria-label={t("common.refresh")}
              onClick={() => void refetch()}
              disabled={isFetching}
            >
              <RefreshCw
                size={14}
                className={isFetching ? "animate-spin" : undefined}
              />
            </IconButton>
          </Flex>
        </Flex>
      </Box>

      <ScrollArea style={{ flex: 1 }}>
        {isLoading ? (
          <Flex
            align="center"
            justify="center"
            style={{ height: 100 }}
          >
            <Text
              size="2"
              color="gray"
            >
              {t("common.loading")}
            </Text>
          </Flex>
        ) : (
          <Flex
            direction="column"
            gap="2"
            className="agent-definitions-list-body"
          >
            {orderedDefinitions.map(renderAgentListItem)}

            {definitions.length === 0 ? (
              <Flex
                align="center"
                justify="center"
                style={{ padding: 24 }}
              >
                <Text
                  size="2"
                  color="gray"
                >
                  {t("settings.agentsEmpty")}
                </Text>
              </Flex>
            ) : null}
          </Flex>
        )}
      </ScrollArea>
    </Box>
  );

  const detailContent = !selectedDef ? (
    <Flex
      direction="column"
      align="center"
      justify="center"
      gap="2"
      className="agent-definitions-empty-state"
    >
      <Bot
        size={32}
        style={{ opacity: 0.3 }}
      />
      <Text
        size="2"
        color="gray"
      >
        {t("settings.agentsSelectHint")}
      </Text>
    </Flex>
  ) : (
    <AgentForm
      key={selectedDef.key}
      def={selectedDef}
      definitions={definitions}
      llmModelOptions={modelOptions}
      hasLlmModels={hasLlmModels}
      toolCategoryOptions={toolCategoryOptions}
      skills={skills}
      onCloseSettings={onCloseSettings}
      onUpdated={invalidateDefs}
      isAgentSettingsLocked={isAgentSettingsLocked}
    />
  );

  return (
    <>
      {isContentLoading ? (
        <Flex
          align="center"
          justify="center"
          style={{ height: "100%" }}
        >
          <Spinner size={18} />
        </Flex>
      ) : isMobile ? (
        <Flex
          direction="column"
          className="agent-definitions-settings-content"
        >
          <AgentSettingsLockNotice isLocked={isAgentSettingsLocked} />
          <Flex className="agent-definitions-layout agent-definitions-layout--mobile">
            <Box className="settings-dialog-mobile-page-stack">
              <AnimatePresence
                initial={false}
                custom={currentMobileDirection}
                mode="sync"
              >
                {currentMobilePage === "list" ? (
                  <MotionBox
                    key="agents-mobile-list"
                    custom={currentMobileDirection}
                    variants={mobilePageVariants}
                    initial="enter"
                    animate="center"
                    exit="exit"
                    transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                    className="settings-dialog-mobile-page"
                  >
                    <Box className="settings-dialog-mobile-page-padding">
                      <Box className="settings-dialog-mobile-page-content">{listContent}</Box>
                    </Box>
                  </MotionBox>
                ) : (
                  <MotionBox
                    key="agents-mobile-detail"
                    custom={currentMobileDirection}
                    variants={mobilePageVariants}
                    initial="enter"
                    animate="center"
                    exit="exit"
                    transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                    className="settings-dialog-mobile-page"
                  >
                    <Box className="agent-definitions-detail-panel agent-definitions-detail-panel--mobile">
                      {detailContent}
                    </Box>
                  </MotionBox>
                )}
              </AnimatePresence>
            </Box>
          </Flex>
        </Flex>
      ) : (
        <Flex
          direction="column"
          className="agent-definitions-settings-content"
        >
          <AgentSettingsLockNotice isLocked={isAgentSettingsLocked} />
          <Flex className="agent-definitions-layout">
            {listContent}

            <Box className="agent-definitions-detail-panel">{detailContent}</Box>
          </Flex>
        </Flex>
      )}

      <ContextMenu
        position={menuState?.position ?? null}
        items={menuItems}
        onClose={closeMenu}
      />

      <Dialog.Root
        open={isCreating}
        onOpenChange={(open) => (!open ? closeCreateDialog() : setIsCreating(true))}
      >
        <Dialog.Content style={{ maxWidth: 420 }}>
          <Dialog.Title>
            {createMode === "copy" ? t("settings.agentsCopy") : t("settings.agentsNewAgent")}
          </Dialog.Title>
          <Flex
            direction="column"
            gap="3"
            style={{ marginTop: 12 }}
          >
            <Flex
              direction="column"
              gap="1"
            >
              <Text
                size="1"
                weight="medium"
              >
                {t("settings.agentsKey")}
              </Text>
              <TextField.Root
                value={newKey}
                onChange={(event) =>
                  setNewKey(event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ""))
                }
                placeholder={t("settings.agentsKeyPlaceholder")}
                disabled={isAgentSettingsLocked}
              />
            </Flex>

            <Flex
              direction="column"
              gap="1"
            >
              <Text
                size="1"
                weight="medium"
              >
                {t("settings.agentsDisplayName")}
              </Text>
              <TextField.Root
                value={newDisplayName}
                onChange={(event) => setNewDisplayName(event.target.value)}
                placeholder={t("settings.agentsDisplayNamePlaceholder")}
                disabled={isAgentSettingsLocked}
              />
            </Flex>

            <Flex
              direction="column"
              gap="1"
            >
              <Text
                size="1"
                weight="medium"
              >
                {t("settings.agentsFieldDescription")}
              </Text>
              <TextArea
                value={newDescription}
                onChange={(event) => setNewDescription(event.target.value)}
                rows={3}
                placeholder={t("settings.agentsDescriptionPlaceholder")}
                disabled={isAgentSettingsLocked}
              />
            </Flex>

            <Flex
              direction="column"
              gap="1"
            >
              <Text
                size="1"
                weight="medium"
              >
                {t("settings.agentsKind")}
              </Text>
              <Select.Root
                value={newKind}
                onValueChange={(value) => setNewKind(value as "primary" | "subagent")}
                disabled={isAgentSettingsLocked}
              >
                <Select.Trigger style={{ width: "100%" }} />
                <Select.Content>
                  {agentKindOptions.map((opt) => (
                    <Select.Item
                      key={opt.value}
                      value={opt.value}
                    >
                      {opt.label}
                    </Select.Item>
                  ))}
                </Select.Content>
              </Select.Root>
            </Flex>
          </Flex>

          <Flex
            gap="2"
            justify="end"
            style={{ marginTop: 20 }}
          >
            <Button
              variant="soft"
              color="gray"
              onClick={closeCreateDialog}
            >
              {t("common.cancel")}
            </Button>
            <Button
              disabled={
                isAgentSettingsLocked ||
                !newKey.trim() ||
                !newDisplayName.trim() ||
                createMutation.isPending
              }
              onClick={() => createMutation.mutate()}
            >
              {createMutation.isPending
                ? t("common.loading")
                : t(createMode === "copy" ? "settings.agentsCopy" : "common.create")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>

      <ConfirmDialog
        open={Boolean(resetTarget)}
        onOpenChange={(open) => !open && setConfirmResetKey(null)}
        title={t("settings.agentsReset")}
        description={t("settings.agentsResetConfirm")}
        onConfirm={() => resetTarget && resetMutation.mutate(resetTarget.key)}
        confirmText={t("settings.agentsReset")}
        cancelText={t("common.cancel")}
        loading={resetMutation.isPending}
      />

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        onOpenChange={(open) => !open && setConfirmDeleteKey(null)}
        title={t("settings.agentsDelete")}
        description={
          deleteTarget
            ? `${t("settings.agentsDeleteConfirmPrefix")}「${deleteTarget.display_name}」${t("settings.agentsDeleteConfirmSuffix")}`
            : ""
        }
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.key)}
        confirmText={t("common.delete")}
        cancelText={t("common.cancel")}
        loading={deleteMutation.isPending}
      />
    </>
  );
}

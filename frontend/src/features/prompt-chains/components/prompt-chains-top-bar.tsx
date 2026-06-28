/**
 * PromptChainsTopBar Component
 *
 * 提示词链页面顶栏：面包屑导航 + 版本选择器 + 保存按钮
 */

import { forwardRef, useState, type ReactNode } from "react";
import { Box, Flex, Button, Text, IconButton, Tooltip } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import { GitBranch, Save, Settings, Play, TriangleAlert, RotateCcw } from "lucide-react";
import { LabeledSelect, SimpleSelect } from "@/components/select";
import { VersionListDialog } from "./version-list-dialog";
import { SaveConfirmDialog } from "./save-confirm-dialog";
import { WorkDirDialog } from "./work-dir-dialog";
import { ResetConfirmDialog } from "./reset-confirm-dialog";
import type { PromptChainVersion, PromptChainsMetadata } from "@/lib/prompt-chain.types";

interface PromptChainsTopBarProps {
  leadingSlot?: ReactNode;
  entrySidebarTrigger?: ReactNode;
  metadata: PromptChainsMetadata | null;
  selectedMode: string | null;
  selectedTask: string | null;
  selectedAgent: string | null;
  onModeChange: (mode: string | null) => void;
  onTaskChange: (task: string | null) => void;
  onAgentChange: (agent: string | null) => void;
  currentVersion: PromptChainVersion | null;
  versions: PromptChainVersion[];
  onVersionSelect: (versionId: string) => void;
  onSave: (note?: string) => void;
  onCompile: () => void;
  onReset: () => void;
  isLoading: boolean;
  isCompiling: boolean;
  isResetting: boolean;
  isSaving: boolean;
  hasUnsavedChanges: boolean;
  isDefault: boolean;
  workDir?: { projectId: string | null; chapterId: string | null };
  onWorkDirChange?: (projectId: string | null, chapterId: string | null) => void;
  modeName: string;
  taskName: string;
  agentName: string | null;
  isMobile?: boolean;
}

export const PromptChainsTopBar = forwardRef<HTMLDivElement, PromptChainsTopBarProps>(function PromptChainsTopBar({
  leadingSlot,
  entrySidebarTrigger,
  metadata,
  selectedMode,
  selectedTask,
  selectedAgent,
  onModeChange,
  onTaskChange,
  onAgentChange,
  currentVersion,
  versions,
  onVersionSelect,
  onSave,
  onCompile,
  onReset,
  isLoading,
  isCompiling,
  isResetting,
  isSaving,
  hasUnsavedChanges,
  isDefault,
  workDir,
  onWorkDirChange,
  modeName,
  taskName,
  agentName,
  isMobile = false,
}: PromptChainsTopBarProps, ref) {
  const { t } = useTranslation();
  const [versionDialogOpen, setVersionDialogOpen] = useState(false);
  const [saveConfirmDialogOpen, setSaveConfirmDialogOpen] = useState(false);
  const [workDirDialogOpen, setWorkDirDialogOpen] = useState(false);
  const [resetConfirmDialogOpen, setResetConfirmDialogOpen] = useState(false);

  // 从元数据生成模式选项
  const modeOptions = metadata?.modes.map(mode => ({
    value: mode.value,
    label: t(`promptChains.${mode.value}ModeLabel`),
  })) || [];
  
  // 根据选择的模式动态生成任务选项
  const taskOptions = selectedMode && metadata
    ? (metadata.modes.find(m => m.value === selectedMode)?.tasks.map(task => ({
        value: task.value,
        label: t(`promptChains.${task.value}TaskLabel`),
      })) || [])
    : [];

  // 根据选择的模式和任务动态生成 agent 选项
  const agentOptions = selectedMode && selectedTask && metadata
    ? (metadata.modes
        .find(m => m.value === selectedMode)
        ?.tasks.find(tk => tk.value === selectedTask)
        ?.agents.map(agent => ({
          value: agent.value,
          label: t(`promptChains.${agent.value}AgentLabel`, { defaultValue: agent.value }),
        })) || [])
    : [];
  
  // 是否显示 agent 选择器(有可用的 agent 选项)
  const showAgentSelector = agentOptions.length > 0;

  // 版本显示文本：默认状态显示"默认"，否则显示版本号
  const versionLabel = isDefault
    ? t("promptChains.default")
    : currentVersion
      ? `v${currentVersion.versionNumber}`
      : t("common.loading");

  // 是否显示版本和保存按钮（需要完成导航选择）
  const showVersionControls = selectedMode && selectedTask;

  // 工作目录是否已设置
  const isWorkDirSet = !!workDir?.projectId;

  // 编译按钮是否可用：必须设置工作目录 + 没有未保存的更改
  const canCompile = isWorkDirSet && !hasUnsavedChanges && !isLoading && !isCompiling && !!currentVersion;

  const breadcrumbContent = isMobile ? (
    <Flex align="center" gap="2" wrap="nowrap">
      <Box style={{ minWidth: 132, flexShrink: 0 }}>
        <SimpleSelect
          value={selectedMode || undefined}
          options={modeOptions}
          onChange={(value) => {
            onModeChange(value || null);
            onTaskChange(null);
            onAgentChange(null);
          }}
          placeholder={t("promptChains.modePlaceholder")}
          size="2"
          triggerStyle={{ width: "100%" }}
        />
      </Box>

      {selectedMode && (
        <>
          <Text size="2" color="gray" style={{ flexShrink: 0 }}>
            /
          </Text>
          <Box style={{ minWidth: 132, flexShrink: 0 }}>
            <SimpleSelect
              value={selectedTask || undefined}
              options={taskOptions}
              onChange={(value) => {
                onTaskChange(value || null);
                onAgentChange(null);
              }}
              placeholder={t("promptChains.taskPlaceholder")}
              size="2"
              triggerStyle={{ width: "100%" }}
            />
          </Box>
        </>
      )}

      {selectedTask && showAgentSelector && (
        <>
          <Text size="2" color="gray" style={{ flexShrink: 0 }}>
            /
          </Text>
          <Box style={{ minWidth: 132, flexShrink: 0 }}>
            <SimpleSelect
              value={selectedAgent || undefined}
              options={agentOptions}
              onChange={(value) => onAgentChange(value || null)}
              placeholder={t("promptChains.agentPlaceholder")}
              size="2"
              triggerStyle={{ width: "100%" }}
            />
          </Box>
        </>
      )}
    </Flex>
  ) : (
    <Flex gap="3" align="center">
      <LabeledSelect
        label={t("promptChains.mode")}
        value={selectedMode || undefined}
        options={modeOptions}
        onChange={(value) => {
          onModeChange(value || null);
          onTaskChange(null);
          onAgentChange(null);
        }}
        placeholder={t("promptChains.modePlaceholder")}
        size="2"
        layout="horizontal"
        gap="2"
      />

      {selectedMode && (
        <>
          <Text size="2" color="gray">
            /
          </Text>
          <LabeledSelect
            label={t("promptChains.task")}
            value={selectedTask || undefined}
            options={taskOptions}
            onChange={(value) => {
              onTaskChange(value || null);
              onAgentChange(null);
            }}
            placeholder={t("promptChains.taskPlaceholder")}
            size="2"
            layout="horizontal"
            gap="2"
          />
        </>
      )}

      {selectedTask && showAgentSelector && (
        <>
          <Text size="2" color="gray">
            /
          </Text>
          <LabeledSelect
            label={t("promptChains.agent")}
            value={selectedAgent || undefined}
            options={agentOptions}
            onChange={(value) => onAgentChange(value || null)}
            placeholder={t("promptChains.agentPlaceholder")}
            size="2"
            layout="horizontal"
            gap="2"
          />
        </>
      )}
    </Flex>
  );

  const versionContent = isMobile ? (
    currentVersion ? (
      <Tooltip content={isDefault ? t("promptChains.default") : versionLabel}>
        <IconButton
          variant="ghost"
          size="2"
          onClick={() => setVersionDialogOpen(true)}
          disabled={isLoading}
        >
          <GitBranch size={16} />
        </IconButton>
      </Tooltip>
    ) : null
  ) : currentVersion && !isDefault ? (
    <Button
      variant="soft"
      size="2"
      onClick={() => setVersionDialogOpen(true)}
      disabled={isLoading}
    >
      {versionLabel}
      {currentVersion.versionHash && (
        <Text size="1" color="gray" ml="1">
          ({currentVersion.versionHash})
        </Text>
      )}
    </Button>
  ) : currentVersion && isDefault ? (
    <Text size="2">{t("promptChains.default")}</Text>
  ) : null;

  return (
    <>
      <Box
        ref={ref}
        py="3"
        px={isMobile ? "4" : "6"}
        style={{
          borderBottom: "1px solid var(--gray-a5)",
          background: "var(--color-background)",
        }}
      >
        {isMobile ? (
          <Flex direction="column" gap="2">
            <Flex align="center" gap="2">
              {leadingSlot}
              <Box
                style={{
                  flex: 1,
                  minWidth: 0,
                  overflowX: "auto",
                  overflowY: "hidden",
                  scrollbarWidth: "none",
                }}
              >
                {breadcrumbContent}
              </Box>
            </Flex>

            {showVersionControls && (
              <Flex align="center" justify="between" gap="3">
                <Flex align="center" gap="2" wrap="nowrap" style={{ minWidth: 0 }}>
                  {entrySidebarTrigger}
                  <Text
                    size="1"
                    color={hasUnsavedChanges ? "amber" : "gray"}
                    style={{ flexShrink: 0, whiteSpace: "nowrap" }}
                  >
                    {hasUnsavedChanges ? t("promptChains.unsavedChanges") : t("promptChains.saved")}
                  </Text>
                </Flex>

                <Flex align="center" gap="1" wrap="nowrap" style={{ minWidth: 0, overflowX: "auto", overflowY: "hidden" }}>
                  {(!isDefault || hasUnsavedChanges) && (
                    <Tooltip content={t("promptChains.resetToDefault")}>
                      <IconButton
                        variant="ghost"
                        size="2"
                        onClick={() => setResetConfirmDialogOpen(true)}
                        disabled={isLoading || isResetting || isSaving}
                      >
                        <RotateCcw size={16} />
                      </IconButton>
                    </Tooltip>
                  )}

                  <Tooltip content={isWorkDirSet ? t("promptChains.workDirSettings") : t("promptChains.workDirNotSet")}>
                    <IconButton
                      variant="ghost"
                      size="2"
                      color={isWorkDirSet ? undefined : "red"}
                      onClick={() => setWorkDirDialogOpen(true)}
                    >
                      {isWorkDirSet ? <Settings size={16} /> : <TriangleAlert size={16} />}
                    </IconButton>
                  </Tooltip>

                  {versionContent}

                  <Tooltip content={t("promptChains.save")}>
                    <IconButton
                      variant="ghost"
                      size="2"
                      onClick={() => setSaveConfirmDialogOpen(true)}
                      disabled={isLoading || isResetting || isSaving || !currentVersion || !hasUnsavedChanges}
                    >
                      <Save size={16} />
                    </IconButton>
                  </Tooltip>

                  <Tooltip content={
                    !isWorkDirSet
                      ? t("promptChains.compileRequiresWorkDir")
                      : hasUnsavedChanges
                        ? t("promptChains.compileRequiresSave")
                        : t("promptChains.compile")
                  }>
                    <IconButton
                      variant="ghost"
                      size="2"
                      onClick={onCompile}
                      disabled={!canCompile}
                    >
                      <Play size={16} />
                    </IconButton>
                  </Tooltip>
                </Flex>
              </Flex>
            )}
          </Flex>
        ) : (
          <Flex justify="between" align="center">
            <Flex gap="3" align="center">
              {leadingSlot}
              {breadcrumbContent}
            </Flex>

            {showVersionControls && (
              <Flex gap="3" align="center">
                {hasUnsavedChanges && (
                  <Text size="1" color="amber">
                    存在未提交的本地修改
                  </Text>
                )}

                {(!isDefault || hasUnsavedChanges) && (
                  <Tooltip content={t("promptChains.resetToDefault")}>
                    <IconButton
                      variant="ghost"
                      size="2"
                      onClick={() => setResetConfirmDialogOpen(true)}
                      disabled={isLoading || isResetting || isSaving}
                    >
                      <RotateCcw size={16} />
                    </IconButton>
                  </Tooltip>
                )}

                <Tooltip content={isWorkDirSet ? t("promptChains.workDirSettings") : t("promptChains.workDirNotSet")}>
                  <IconButton
                    variant="ghost"
                    size="2"
                    color={isWorkDirSet ? undefined : "red"}
                    onClick={() => setWorkDirDialogOpen(true)}
                  >
                    {isWorkDirSet ? <Settings size={16} /> : <TriangleAlert size={16} />}
                  </IconButton>
                </Tooltip>

                {versionContent && (
                  <Flex align="center" gap="2">
                    <Text size="2" color="gray">
                      {t("promptChains.version")}
                    </Text>
                    {versionContent}
                  </Flex>
                )}

                <Tooltip content={t("promptChains.save")}>
                  <IconButton
                    variant="ghost"
                    size="2"
                    onClick={() => setSaveConfirmDialogOpen(true)}
                    disabled={isLoading || isResetting || isSaving || !currentVersion || !hasUnsavedChanges}
                  >
                    <Save size={16} />
                  </IconButton>
                </Tooltip>

                <Tooltip content={
                  !isWorkDirSet
                    ? t("promptChains.compileRequiresWorkDir")
                    : hasUnsavedChanges
                      ? t("promptChains.compileRequiresSave")
                      : t("promptChains.compile")
                }>
                  <IconButton
                    variant="ghost"
                    size="2"
                    onClick={onCompile}
                    disabled={!canCompile}
                  >
                    <Play size={16} />
                  </IconButton>
                </Tooltip>
              </Flex>
            )}
          </Flex>
        )}
      </Box>

      {/* 版本列表弹窗 */}
      <VersionListDialog
        open={versionDialogOpen}
        onOpenChange={setVersionDialogOpen}
        versions={versions}
        currentVersionId={currentVersion?.id || null}
        onSelectVersion={(versionId) => {
          onVersionSelect(versionId);
          setVersionDialogOpen(false);
        }}
        modeName={modeName}
        taskName={taskName}
        agentName={agentName}
      />

      {/* 保存确认弹窗 */}
      <SaveConfirmDialog
        open={saveConfirmDialogOpen}
        onOpenChange={setSaveConfirmDialogOpen}
        currentVersion={currentVersion}
        versions={versions}
        onConfirm={() => onSave()}
      />

      {/* Work Dir设置弹窗 */}
      <WorkDirDialog
        open={workDirDialogOpen}
        onOpenChange={setWorkDirDialogOpen}
        currentProjectId={workDir?.projectId || null}
        currentChapterId={workDir?.chapterId || null}
        onConfirm={(projectId, chapterId) => {
          onWorkDirChange?.(projectId, chapterId);
        }}
      />

      {/* 重置确认弹窗 */}
      <ResetConfirmDialog
        open={resetConfirmDialogOpen}
        onOpenChange={setResetConfirmDialogOpen}
        onConfirm={() => {
          setSaveConfirmDialogOpen(false);
          onReset();
          setResetConfirmDialogOpen(false);
        }}
        isLoading={isResetting}
      />
    </>
  );
});

/**
 * World Info Selector
 *
 * 世界书选择器，用于选择、创建和编辑世界书。
 */

import { useState } from "react";
import {
  Box,
  Flex,
  Text,
  Button,
  Dialog,
  TextField,
  IconButton,
  Tooltip,
} from "@radix-ui/themes";
import { Plus, Settings, Upload } from "lucide-react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import {
  fetchWorldInfoList,
  createWorldInfo,
  updateWorldInfo,
  fetchProjects,
} from "@/lib/api-client";
import { AnimatePresence, motion } from "motion/react";
import { SimpleSelect } from "@/components/select";
import { ProjectSelectField } from "./project-select-field";
import { ImportWorldInfoDialog } from "./import-world-info-dialog";

const MotionBox = motion.create(Box);

interface WorldInfoSelectorProps {
  /** 当前选中的世界书 ID */
  value: string | null;
  /** 选择世界书时的回调 */
  onChange: (worldInfoId: string) => void;
  isMobile?: boolean;
  appSidebarTrigger?: ReactNode;
  entrySidebarTrigger?: ReactNode;
}

export function WorldInfoSelector({
  value,
  onChange,
  isMobile = false,
  appSidebarTrigger,
  entrySidebarTrigger,
}: WorldInfoSelectorProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  // 创建对话框状态
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");

  // 设置对话框状态
  const [settingsDialogOpen, setSettingsDialogOpen] = useState(false);
  const [editName, setEditName] = useState("");
  const [editProjectId, setEditProjectId] = useState<string>("");
  const [importDialogOpen, setImportDialogOpen] = useState(false);

  // 获取世界书列表
  const { data: worldInfoList, isLoading: worldInfoLoading } = useQuery({
    queryKey: ["world-info-list"],
    queryFn: () => fetchWorldInfoList({ page: 1, pageSize: 100 }),
  });

  // 获取项目列表
  const { data: projectsList } = useQuery({
    queryKey: ["projects"],
    queryFn: () => fetchProjects({ page: 1, pageSize: 100 }),
  });

  // 创建世界书
  const createMutation = useMutation({
    mutationFn: () =>
      createWorldInfo({
        name: newName,
        projectId: selectedProjectId || undefined,
      }),
    onSuccess: (newWorldInfo) => {
      queryClient.invalidateQueries({ queryKey: ["world-info-list"] });
      onChange(newWorldInfo.id);
      setCreateDialogOpen(false);
      setNewName("");
      setSelectedProjectId("");
    },
  });

  // 更新世界书
  const updateMutation = useMutation({
    mutationFn: () => {
      const currentWorldInfo = worldInfoItems.find((w) => w.id === value);
      const currentProjectId = currentWorldInfo?.projectId;

      // 判断是否需要解绑
      const unbindProject = Boolean(currentProjectId && !editProjectId);
      // 判断是否需要绑定新项目
      const newProjectId =
        editProjectId && editProjectId !== currentProjectId
          ? editProjectId
          : undefined;

      return updateWorldInfo(value!, {
        name: editName !== currentWorldInfo?.name ? editName : undefined,
        projectId: newProjectId,
        unbindProject,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["world-info-list"] });
      setSettingsDialogOpen(false);
    },
  });

  const worldInfoItems = worldInfoList?.items ?? [];
  const selectedWorldInfo = worldInfoItems.find((w) => w.id === value);
  const currentWorldInfoProjectId = selectedWorldInfo?.projectId;
  const boundProjectIds = new Set(
    worldInfoItems
      .filter((w) => w.projectId && w.id !== value)
      .map((w) => w.projectId as string)
  );
  const availableProjects =
    projectsList?.items.filter((p) => !boundProjectIds.has(p.id)) ?? [];
  const editableProjects =
    projectsList?.items.filter(
      (p) => !boundProjectIds.has(p.id) || p.id === currentWorldInfoProjectId
    ) ?? [];

  // 获取项目名称
  const getProjectName = (projectId: string | null) => {
    if (!projectId || !projectsList?.items) return null;
    const project = projectsList.items.find((p) => p.id === projectId);
    return project?.title ?? null;
  };

  // 打开设置对话框时初始化数据
  const handleOpenSettings = () => {
    if (selectedWorldInfo) {
      setEditName(selectedWorldInfo.name);
      setEditProjectId(selectedWorldInfo.projectId ?? "");
    }
    setSettingsDialogOpen(true);
  };

  /** 处理创建 */
  const handleCreate = () => {
    if (newName.trim()) {
      createMutation.mutate();
    }
  };

  /** 处理更新 */
  const handleUpdate = () => {
    if (editName.trim()) {
      updateMutation.mutate();
    }
  };

  return (
    <>
      <Box px="4" py="3" style={{ borderBottom: "1px solid var(--gray-a4)" }}>
        {isMobile ? (
          <Flex direction="column" gap="2">
            <Flex align="center" gap="2">
              {appSidebarTrigger}

              <Box style={{ flex: 1, minWidth: 0 }}>
                <SimpleSelect
                  value={value ?? undefined}
                  options={worldInfoItems.map((worldInfo) => ({
                    value: worldInfo.id,
                    label: worldInfo.name,
                    suffix: worldInfo.projectId ? (
                      <Text size="1" color="gray">
                        {" "}
                        ({t("worldInfo.boundToProject")})
                      </Text>
                    ) : undefined,
                  }))}
                  onChange={onChange}
                  placeholder={
                    worldInfoLoading
                      ? "..."
                      : worldInfoItems.length === 0
                        ? t("worldInfo.noWorldInfo")
                        : t("worldInfo.selectWorldInfo")
                  }
                  disabled={worldInfoLoading || worldInfoItems.length === 0}
                  triggerStyle={{ width: "100%", minWidth: 0 }}
                />
              </Box>

              <Tooltip content={t("worldInfo.createWorldInfo")}>
                <IconButton variant="ghost" size="2" onClick={() => setCreateDialogOpen(true)}>
                  <Plus size={16} />
                </IconButton>
              </Tooltip>

              <Tooltip content={t("common.import")}>
                <IconButton
                  variant="ghost"
                  size="2"
                  onClick={() => setImportDialogOpen(true)}
                  disabled={!selectedWorldInfo}
                >
                  <Upload size={16} />
                </IconButton>
              </Tooltip>
            </Flex>

            <AnimatePresence initial={false}>
              {selectedWorldInfo && (
                <MotionBox
                  key="mobile-world-info-secondary-row"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
                  style={{ overflow: "hidden" }}
                >
                  <Flex align="center" gap="2" wrap="wrap" pt="2">
                    {entrySidebarTrigger}

                    <Text size="2" color="gray" style={{ flex: 1, minWidth: 0 }} truncate>
                      {selectedWorldInfo.projectId
                        ? `${t("worldInfo.boundToProject")}: ${getProjectName(selectedWorldInfo.projectId)}`
                        : t("worldInfo.notBound")}
                    </Text>

                    <Button variant="ghost" size="2" onClick={handleOpenSettings}>
                      <Settings size={16} />
                      {t("worldInfo.settings")}
                    </Button>
                  </Flex>
                </MotionBox>
              )}
            </AnimatePresence>
          </Flex>
        ) : (
          <Flex align="center" gap="3">
            <SimpleSelect
              value={value ?? undefined}
              options={worldInfoItems.map((worldInfo) => ({
                value: worldInfo.id,
                label: worldInfo.name,
                suffix: worldInfo.projectId ? (
                  <Text size="1" color="gray">
                    {" "}
                    ({t("worldInfo.boundToProject")})
                  </Text>
                ) : undefined,
              }))}
              onChange={onChange}
              placeholder={
                worldInfoLoading
                  ? "..."
                  : worldInfoItems.length === 0
                    ? t("worldInfo.noWorldInfo")
                    : t("worldInfo.selectWorldInfo")
              }
              disabled={worldInfoLoading || worldInfoItems.length === 0}
              triggerStyle={{ minWidth: 200 }}
            />

            {selectedWorldInfo && (
              <Text size="2" color="gray">
                {selectedWorldInfo.projectId
                  ? `${t("worldInfo.boundToProject")}: ${getProjectName(
                      selectedWorldInfo.projectId
                    )}`
                  : t("worldInfo.notBound")}
              </Text>
            )}

            {selectedWorldInfo && (
              <Tooltip content={t("worldInfo.settings")}>
                <IconButton variant="ghost" size="2" onClick={handleOpenSettings}>
                  <Settings size={16} />
                </IconButton>
              </Tooltip>
            )}

            <Button
              variant="soft"
              size="2"
              onClick={() => setCreateDialogOpen(true)}
            >
              <Plus size={16} />
              {t("worldInfo.createWorldInfo")}
            </Button>

            <Button
              variant="soft"
              size="2"
              onClick={() => setImportDialogOpen(true)}
              disabled={!selectedWorldInfo}
            >
              <Upload size={16} />
              {t("common.import")}
            </Button>
          </Flex>
        )}
      </Box>

      <ImportWorldInfoDialog
        open={importDialogOpen}
        worldInfoId={value}
        onOpenChange={setImportDialogOpen}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["world-info-entries", value] });
        }}
      />

      {/* 创建世界书对话框 */}
      <Dialog.Root open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <Dialog.Content style={{ maxWidth: 450 }}>
          <Dialog.Title>{t("worldInfo.createWorldInfo")}</Dialog.Title>
          <Dialog.Description size="2" mb="4">
            {t("worldInfo.createWorldInfoDesc")}
          </Dialog.Description>

          <Flex direction="column" gap="3">
            {/* 名称输入 */}
            <Box>
              <Text as="label" size="2" weight="medium" mb="1">
                {t("worldInfo.worldInfoName")}
              </Text>
              <TextField.Root
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder={t("worldInfo.worldInfoNamePlaceholder")}
              />
            </Box>

            {/* 项目选择 */}
            <ProjectSelectField
              label={`${t("worldInfo.bindProject")} (${t("common.optional")})`}
              projects={availableProjects}
              value={selectedProjectId}
              onChange={setSelectedProjectId}
              showNoneOption={true}
              placeholder={t("worldInfo.selectProjectOptional")}
            />
          </Flex>

          <Flex gap="3" mt="4" justify="end">
            <Dialog.Close>
              <Button variant="soft" color="gray">
                {t("common.cancel")}
              </Button>
            </Dialog.Close>
            <Button
              onClick={handleCreate}
              disabled={!newName.trim() || createMutation.isPending}
            >
              {t("common.create")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>

      {/* 设置世界书对话框 */}
      <Dialog.Root
        open={settingsDialogOpen}
        onOpenChange={setSettingsDialogOpen}
      >
        <Dialog.Content style={{ maxWidth: 450 }}>
          <Dialog.Title>{t("worldInfo.settings")}</Dialog.Title>
          <Dialog.Description size="2" mb="4">
            {t("worldInfo.settingsDesc")}
          </Dialog.Description>

          <Flex direction="column" gap="3">
            {/* 名称输入 */}
            <Box>
              <Text as="label" size="2" weight="medium" mb="1">
                {t("worldInfo.worldInfoName")}
              </Text>
              <TextField.Root
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                placeholder={t("worldInfo.worldInfoNamePlaceholder")}
              />
            </Box>

            {/* 项目绑定 */}
            <ProjectSelectField
              label={t("worldInfo.bindProject")}
              projects={editableProjects}
              value={editProjectId}
              onChange={setEditProjectId}
              showNoneOption={true}
              placeholder={t("worldInfo.selectProjectOptional")}
            />
          </Flex>

          <Flex gap="3" mt="4" justify="end">
            <Dialog.Close>
              <Button variant="soft" color="gray">
                {t("common.cancel")}
              </Button>
            </Dialog.Close>
            <Button
              onClick={handleUpdate}
              disabled={!editName.trim() || updateMutation.isPending}
            >
              {t("common.save")}
            </Button>
          </Flex>
        </Dialog.Content>
      </Dialog.Root>
    </>
  );
}

/**
 * WorkDirDialog - Work Dir 设置对话框
 *
 * 用于设置提示词链编译时使用的项目和章节。
 */

import { useState, useEffect, useMemo, useCallback } from "react";
import { Dialog, Flex, Button, Box, Text } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import { Settings } from "lucide-react";
import { LabeledSelect } from "@/components";
import { fetchProjects, fetchChapters } from "@/lib/api-client";
import type { Project } from "@/lib/project.types";
import type { ChapterListItem } from "@/lib/chapter.types";

interface WorkDirDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentProjectId: string | null;
  currentChapterId: string | null;
  onConfirm: (projectId: string | null, chapterId: string | null) => void;
}

export function WorkDirDialog({
  open,
  onOpenChange,
  currentProjectId,
  currentChapterId,
  onConfirm,
}: WorkDirDialogProps) {
  const { t } = useTranslation();

  const [projects, setProjects] = useState<Project[]>([]);
  const [chapters, setChapters] = useState<ChapterListItem[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(
    currentProjectId
  );
  const [selectedChapterId, setSelectedChapterId] = useState<string | null>(
    currentChapterId
  );
  const [loading, setLoading] = useState(false);

  const loadProjects = useCallback(async () => {
    try {
      const response = await fetchProjects();
      setProjects(response.items);
    } catch (err) {
      console.error("Failed to fetch projects:", err);
      setProjects([]);
    }
  }, []);

  const loadChapters = useCallback(async (projectId: string) => {
    setLoading(true);
    try {
      const response = await fetchChapters(projectId);
      setChapters(response.volumes.flatMap((volume) => volume.chapters));
    } catch (err) {
      console.error("Failed to fetch chapters:", err);
      setChapters([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // 转换项目为 SelectOption
  const projectOptions = useMemo(() => {
    return projects.map((p) => ({
      value: p.id,
      label: p.title,
    }));
  }, [projects]);

  // 转换章节为 SelectOption
  const chapterOptions = useMemo(() => {
    const list = chapters.map((c) => ({
      value: String(c.order),
      label: `${c.order}. ${c.title}`,
    }));
    return [
      { value: "latest", label: t("promptChains.latestChapter") },
      ...list,
    ];
  }, [chapters, t]);

  useEffect(() => {
    if (open) {
      queueMicrotask(() => {
        loadProjects();
      });
    }
  }, [open, loadProjects]);

  useEffect(() => {
    if (!selectedProjectId) return;
    queueMicrotask(() => {
      loadChapters(selectedProjectId);
    });
  }, [selectedProjectId, loadChapters]);

  const handleConfirm = () => {
    onConfirm(selectedProjectId, selectedChapterId);
    onOpenChange(false);
  };

  const handleOpenChange = (nextOpen: boolean) => {
    if (nextOpen) {
      setSelectedProjectId(currentProjectId);
      setSelectedChapterId(currentChapterId);
    }
    onOpenChange(nextOpen);
  };

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Content style={{ maxWidth: 450 }}>
        <Dialog.Title>
          <Flex align="center" gap="2">
            <Settings size={18} />
            {t("promptChains.workDirSettings")}
          </Flex>
        </Dialog.Title>

        <Dialog.Description size="2" color="gray" mb="4">
          {t("promptChains.workDirDescription")}
        </Dialog.Description>

        {/* 未设置工作目录时显示警告 */}
        {!currentProjectId && (
          <Box
            mb="4"
            p="3"
            style={{
              background: "var(--yellow-a3)",
              borderRadius: "var(--radius-2)",
              border: "1px solid var(--yellow-a6)",
            }}
          >
            <Text size="2" color="yellow">
              {t("promptChains.workDirWarning")}
            </Text>
          </Box>
        )}

        <Flex direction="column" gap="4">
          <LabeledSelect
            label={t("promptChains.project")}
            value={selectedProjectId || ""}
            options={projectOptions}
            onChange={(v) => {
              setSelectedProjectId(v || null);
              setSelectedChapterId(null);
              if (!v) setChapters([]);
            }}
            placeholder={t("promptChains.selectProject")}
          />

          <LabeledSelect
            label={t("promptChains.chapter")}
            value={selectedChapterId || "latest"}
            options={chapterOptions}
            onChange={(v) => setSelectedChapterId(v === "latest" ? null : v)}
            disabled={!selectedProjectId || loading}
            placeholder={t("promptChains.selectChapter")}
          />
        </Flex>

        <Flex gap="3" mt="4" justify="end">
          <Dialog.Close>
            <Button variant="soft" color="gray">
              {t("promptChains.cancel")}
            </Button>
          </Dialog.Close>
          <Button onClick={handleConfirm}>{t("promptChains.confirm")}</Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

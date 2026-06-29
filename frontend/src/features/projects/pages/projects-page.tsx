/**
 * ProjectsPage Component
 *
 * 项目列表主页面，整合所有项目管理功能。
 */

import { useState, useMemo } from "react";
import { Box, Container, Flex, Text, Grid } from "@radix-ui/themes";
import { BookOpen } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { useTranslation } from "react-i18next";
import Fuse from "fuse.js";
import { useQueryClient } from "@tanstack/react-query";
import { MobileAppSidebarTrigger } from "@/features/app-shell";
import {
  useProjects,
  useCreateProject,
  useUpdateProject,
  useDeleteProject,
  projectsQueryKey,
} from "../hooks/use-projects";
import { useProjectsStore } from "../store/use-projects-store";
import { ProjectCard } from "../components/project-card";
import { ProjectListItem } from "../components/project-list-item";
import { ProjectsToolbar } from "../components/projects-toolbar";
import { ProjectFormDialog } from "../components/project-form-dialog";
import { ImportDialog } from "../components/import-dialog";
import { ConfirmDialog, Spinner, toast } from "@/components";
import type { Project } from "@/lib/project.types";
import { getPinyin, getInitials } from "@/lib/pinyin-search";

const MotionBox = motion.create(Box);

export function ProjectsPage() {
  const { t } = useTranslation();

  // 查询项目列表
  const { data, isLoading, error } = useProjects();
  const createMutation = useCreateProject();
  const updateMutation = useUpdateProject();
  const deleteMutation = useDeleteProject();
  const queryClient = useQueryClient();

  // 本地 UI 状态
  const { viewMode, searchQuery, sortBy, sortOrder } = useProjectsStore();

  // 对话框状态
  const [formDialogOpen, setFormDialogOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deletingProject, setDeletingProject] = useState<Project | null>(null);
  const [importDialogOpen, setImportDialogOpen] = useState(false);

  const handleFormDialogOpenChange = (open: boolean) => {
    setFormDialogOpen(open);

    if (!open) {
      setEditingProject(null);
    }
  };

  const handleImportDialogOpenChange = (open: boolean) => {
    setImportDialogOpen(open);
  };

  // 提取 items 引用，避免 React Compiler 依赖推断问题
  const items = data?.items;

  // 为项目生成搜索索引
  interface SearchableProject {
    id: string;
    title: string;
    titlePinyin: string;
    titleInitials: string;
    description: string;
    descriptionPinyin: string;
    descriptionInitials: string;
    original: Project;
  }

  const searchableProjects = useMemo((): SearchableProject[] => {
    if (!items) return [];
    return items.map((p) => ({
      id: p.id,
      title: p.title,
      titlePinyin: getPinyin(p.title),
      titleInitials: getInitials(p.title),
      description: p.description ?? "",
      descriptionPinyin: getPinyin(p.description ?? ""),
      descriptionInitials: getInitials(p.description ?? ""),
      original: p,
    }));
  }, [items]);

  // 创建 Fuse 实例
  const fuse = useMemo(() => {
    return new Fuse(searchableProjects, {
      keys: [
        { name: "title", weight: 3 },
        { name: "titlePinyin", weight: 2 },
        { name: "titleInitials", weight: 2.5 },
        { name: "description", weight: 1 },
        { name: "descriptionPinyin", weight: 0.5 },
        { name: "descriptionInitials", weight: 0.8 },
      ],
      threshold: 0.1,
      ignoreLocation: true,
      distance: 50,
    });
  }, [searchableProjects]);

  // 过滤和排序项目
  const filteredProjects = useMemo(() => {
    if (!items) return [];

    let filtered: Project[];

    // 搜索过滤
    if (searchQuery.trim()) {
      const results = fuse.search(searchQuery);
      filtered = results.map((r) => r.item.original);
    } else {
      filtered = [...items];
    }

    // 排序
    filtered.sort((a, b) => {
      let comparison = 0;
      switch (sortBy) {
        case "updated_at":
          comparison =
            new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
          break;
        case "created_at":
          comparison =
            new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
          break;
        case "title":
          comparison = a.title.localeCompare(b.title, "zh-CN");
          break;
      }
      return sortOrder === "asc" ? -comparison : comparison;
    });

    return filtered;
  }, [items, searchQuery, sortBy, sortOrder, fuse]);

  // 处理创建/编辑
  const handleOpenCreate = () => {
    setEditingProject(null);
    setFormDialogOpen(true);
  };

  const handleOpenEdit = (project: Project) => {
    setEditingProject(project);
    setFormDialogOpen(true);
  };

  const handleFormSubmit = async (formData: {
    title: string;
    description?: string;
    cover?: File | null;
  }) => {
    try {
      if (editingProject) {
        await updateMutation.mutateAsync({
          projectId: editingProject.id,
          data: formData,
        });
        toast.success(t("projects.projectUpdated"));
      } else {
        await createMutation.mutateAsync(formData);
        toast.success(t("projects.projectCreated"));
      }
      setFormDialogOpen(false);
      setEditingProject(null);
    } catch {
      toast.error(
        editingProject ? t("projects.updateFailed") : t("projects.createFailed")
      );
    }
  };

  // 处理删除
  const handleOpenDelete = (project: Project) => {
    setDeletingProject(project);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!deletingProject) return;
    try {
      await deleteMutation.mutateAsync(deletingProject.id);
      toast.success(t("projects.projectDeleted"));
      setDeleteDialogOpen(false);
      setDeletingProject(null);
    } catch {
      toast.error(t("projects.deleteFailed"));
    }
  };

  return (
    <Box
      style={{
        height: "100%",
        minHeight: 0,
        overflowY: "auto",
        overflowX: "hidden",
        background: "var(--color-background)",
      }}
    >
      {/* 工具栏区域 */}
      <Container size="4" px="5">
        <Box style={{ borderBottom: "1px solid var(--gray-a5)" }}>
          <ProjectsToolbar
            leadingSlot={<MobileAppSidebarTrigger />}
            onCreateClick={handleOpenCreate}
            onImportClick={() => setImportDialogOpen(true)}
          />
        </Box>
      </Container>

      {/* 主内容区域 */}
      <Container size="4" py="6" px="5">
        {/* 加载状态 */}
        {isLoading && (
          <Flex justify="center" align="center" py="9">
            <Spinner size={18} />
          </Flex>
        )}

        {/* 错误状态 */}
        {error && (
          <Flex justify="center" align="center" py="9">
            <Text color="red">{t("common.error")}</Text>
          </Flex>
        )}

        {/* 空状态 */}
        {!isLoading && !error && filteredProjects.length === 0 && (
          <MotionBox
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            <Flex
              direction="column"
              align="center"
              justify="center"
              py="9"
              gap="4"
            >
              <Box
                style={{
                  padding: "24px",
                  borderRadius: "50%",
                  background: "var(--accent-a3)",
                }}
              >
                <BookOpen size={48} style={{ color: "var(--accent-11)" }} />
              </Box>
              <Text size="5" weight="medium" color="gray">
                {searchQuery
                  ? t("projects.noProjectsFound")
                  : t("projects.noProjects")}
              </Text>
              <Text size="2" color="gray">
                {searchQuery
                  ? t("projects.tryOtherSearch")
                  : t("projects.startCreating")}
              </Text>
            </Flex>
          </MotionBox>
        )}

        {/* 项目列表 */}
        {!isLoading && !error && filteredProjects.length > 0 && (
          <Box mt="5">
            <AnimatePresence mode="wait">
              {viewMode === "grid" ? (
                <Grid
                  key="grid"
                  columns={{ initial: "2", sm: "3", md: "4", lg: "5" }}
                  gap="7"
                >
                  {filteredProjects.map((project) => (
                    <ProjectCard
                      key={project.id}
                      project={project}
                      onEdit={handleOpenEdit}
                      onDelete={handleOpenDelete}
                    />
                  ))}
                </Grid>
              ) : (
                <Flex key="list" direction="column" gap="3">
                  {filteredProjects.map((project) => (
                    <ProjectListItem
                      key={project.id}
                      project={project}
                      onEdit={handleOpenEdit}
                      onDelete={handleOpenDelete}
                    />
                  ))}
                </Flex>
              )}
            </AnimatePresence>
          </Box>
        )}
      </Container>

      {/* 创建/编辑对话框 */}
      <ProjectFormDialog
        open={formDialogOpen}
        onOpenChange={handleFormDialogOpenChange}
        onSubmit={handleFormSubmit}
        project={editingProject}
        loading={createMutation.isPending || updateMutation.isPending}
      />

      {/* 删除确认对话框 */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={handleConfirmDelete}
        title={t("projects.deleteProject")}
        description={t("projects.deleteConfirmation", {
          title: deletingProject?.title ?? "",
        })}
        confirmText={t("common.delete")}
        confirmColor="red"
        loading={deleteMutation.isPending}
      />

      {/* 导入对话框 */}
      <ImportDialog
        open={importDialogOpen}
        onOpenChange={handleImportDialogOpenChange}
        onSuccess={() => {
          void queryClient.refetchQueries({ queryKey: projectsQueryKey });
        }}
      />
    </Box>
  );
}

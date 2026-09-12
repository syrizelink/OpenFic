/**
 * ProjectsPage Component
 *
 * Halaman utama daftar proyek, menyatukan seluruh fungsi pengelolaan proyek.
 */

import { Box, Button, Container, Flex, Text, Grid } from "@radix-ui/themes";
import { useQueryClient } from "@tanstack/react-query";
import { BookOpen, ChevronLeft, ChevronRight } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { ConfirmDialog, Spinner, toast } from "@/components";
import { MobileAppSidebarTrigger, useAppShell } from "@/features/app-shell";
import { useMobileSidebarSwipe } from "@/hooks/use-mobile-sidebar-swipe";
import type { Project } from "@/lib/project.types";

import { ImportDialog } from "../components/import-dialog";
import { ProjectCard } from "../components/project-card";
import { ProjectFormDialog } from "../components/project-form-dialog";
import { ProjectListItem } from "../components/project-list-item";
import { ProjectsToolbar } from "../components/projects-toolbar";
import {
  useProjects,
  useCreateProject,
  useUpdateProject,
  useDeleteProject,
  projectsQueryKey,
} from "../hooks/use-projects";
import { useProjectsStore } from "../store/use-projects-store";

const MotionBox = motion.create(Box);
const PROJECTS_PAGE_SIZE = 40;

function getVisiblePages(currentPage: number, totalPages: number): Array<number | "ellipsis"> {
  if (totalPages <= 6) return Array.from({ length: totalPages }, (_, index) => index + 1);
  if (currentPage <= 3) return [1, 2, 3, "ellipsis", totalPages - 1, totalPages];
  if (currentPage >= totalPages - 2)
    return [1, 2, "ellipsis", totalPages - 2, totalPages - 1, totalPages];
  return [1, "ellipsis", currentPage - 1, currentPage, currentPage + 1, "ellipsis", totalPages];
}

export function ProjectsPage() {
  const { t } = useTranslation();
  const { closeSidebar, isMobile, isSidebarOpen, openSidebar } = useAppShell();
  const mobileSidebarSwipeHandlers = useMobileSidebarSwipe({
    isEnabled: isMobile,
    isOpen: isSidebarOpen,
    onOpen: openSidebar,
    onClose: closeSidebar,
  });

  // Status UI lokal
  const { viewMode, searchQuery, sortBy, sortOrder } = useProjectsStore();
  const [currentPage, setCurrentPage] = useState(1);
  const hasMountedFilters = useRef(false);

  // Penomoran halaman, pencarian, dan pengurutan di sisi server
  const { data, isLoading, isFetching, error } = useProjects({
    page: currentPage,
    pageSize: PROJECTS_PAGE_SIZE,
    search: searchQuery.trim() || undefined,
    sortBy,
    sortOrder,
  });
  const createMutation = useCreateProject();
  const updateMutation = useUpdateProject();
  const deleteMutation = useDeleteProject();
  const queryClient = useQueryClient();

  // Status dialog
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

  const items = data?.items ?? [];
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PROJECTS_PAGE_SIZE));
  const activePage = Math.min(currentPage, totalPages);

  useEffect(() => {
    if (!hasMountedFilters.current) {
      hasMountedFilters.current = true;
      return;
    }
    setCurrentPage(1);
  }, [searchQuery, sortBy, sortOrder]);

  useEffect(() => {
    setCurrentPage((page) => Math.min(page, totalPages));
  }, [totalPages]);

  // Menangani pembuatan/penyuntingan
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
      toast.error(editingProject ? t("projects.updateFailed") : t("projects.createFailed"));
    }
  };

  // Menangani penghapusan
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
      {...mobileSidebarSwipeHandlers}
      className="projects-page mobile-sidebar-swipe-surface"
      style={{
        height: "100%",
        minHeight: 0,
        overflowY: "auto",
        overflowX: "hidden",
        background: "var(--color-background)",
      }}
    >
      {/* Area bilah alat */}
      <Container
        size="4"
        px="5"
      >
        <Box style={{ borderBottom: "1px solid var(--gray-a5)" }}>
          <ProjectsToolbar
            leadingSlot={<MobileAppSidebarTrigger />}
            onCreateClick={handleOpenCreate}
            onImportClick={() => setImportDialogOpen(true)}
          />
        </Box>
      </Container>

      {/* Area isi utama */}
      <Container
        size="4"
        py="6"
        px="5"
      >
        {/* Status memuat */}
        {isLoading && (
          <Flex
            justify="center"
            align="center"
            py="9"
          >
            <Spinner size={18} />
          </Flex>
        )}

        {/* Status galat */}
        {error && (
          <Flex
            justify="center"
            align="center"
            py="9"
          >
            <Text color="red">{t("common.error")}</Text>
          </Flex>
        )}

        {/* Status kosong */}
        {!isLoading && !error && items.length === 0 && (
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
                <BookOpen
                  size={48}
                  style={{ color: "var(--accent-11)" }}
                />
              </Box>
              <Text
                size="5"
                weight="medium"
                color="gray"
              >
                {searchQuery ? t("projects.noProjectsFound") : t("projects.noProjects")}
              </Text>
              <Text
                size="2"
                color="gray"
              >
                {searchQuery ? t("projects.tryOtherSearch") : t("projects.startCreating")}
              </Text>
            </Flex>
          </MotionBox>
        )}

        {/* Daftar proyek */}
        {!isLoading && !error && items.length > 0 && (
          <Box mt="5">
            <AnimatePresence mode="wait">
              {viewMode === "grid" ? (
                <Grid
                  key="grid"
                  columns={{ initial: "2", sm: "3", md: "4", lg: "5" }}
                  gap="7"
                >
                  {items.map((project) => (
                    <ProjectCard
                      key={project.id}
                      project={project}
                      onEdit={handleOpenEdit}
                      onDelete={handleOpenDelete}
                    />
                  ))}
                </Grid>
              ) : (
                <Flex
                  key="list"
                  direction="column"
                  gap="3"
                >
                  {items.map((project) => (
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
            {totalPages > 1 && (
              <Flex
                align="center"
                justify="center"
                gap="2"
                mt="7"
                pb="2"
                wrap="wrap"
                aria-label={t("projects.pageList")}
              >
                <Button
                  type="button"
                  variant="ghost"
                  color="gray"
                  size="2"
                  style={{ margin: 0 }}
                  disabled={activePage === 1 || isFetching}
                  aria-label={t("projects.previousPage")}
                  onClick={() => setCurrentPage(Math.max(1, activePage - 1))}
                >
                  <ChevronLeft
                    size={16}
                    aria-hidden="true"
                  />
                  {t("projects.previousPage")}
                </Button>
                {getVisiblePages(activePage, totalPages).map((page, index) =>
                  page === "ellipsis" ? (
                    <Flex
                      key={`ellipsis-${index}`}
                      align="center"
                      justify="center"
                      style={{ width: 32, height: 32, flexShrink: 0 }}
                    >
                      <Text
                        size="2"
                        color="gray"
                        aria-hidden="true"
                      >
                        …
                      </Text>
                    </Flex>
                  ) : (
                    <Box
                      key={page}
                      style={{ width: 32, height: 32, flexShrink: 0 }}
                    >
                      <Button
                        type="button"
                        variant={page === activePage ? "soft" : "ghost"}
                        size="2"
                        style={{ width: "100%", height: "100%", margin: 0, padding: 0 }}
                        disabled={page === activePage || isFetching}
                        aria-label={t("projects.page", { page })}
                        onClick={() => setCurrentPage(page)}
                      >
                        {page}
                      </Button>
                    </Box>
                  ),
                )}
                <Button
                  type="button"
                  variant="ghost"
                  color="gray"
                  size="2"
                  style={{ margin: 0 }}
                  disabled={activePage === totalPages || isFetching}
                  aria-label={t("projects.nextPage")}
                  onClick={() => setCurrentPage(Math.min(totalPages, activePage + 1))}
                >
                  {t("projects.nextPage")}
                  <ChevronRight
                    size={16}
                    aria-hidden="true"
                  />
                </Button>
              </Flex>
            )}
          </Box>
        )}
      </Container>

      {/* Dialog pembuatan/penyuntingan */}
      <ProjectFormDialog
        open={formDialogOpen}
        onOpenChange={handleFormDialogOpenChange}
        onSubmit={handleFormSubmit}
        project={editingProject}
        loading={createMutation.isPending || updateMutation.isPending}
      />

      {/* Dialog konfirmasi penghapusan */}
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

      {/* Dialog impor */}
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

/**
 * Projects Feature Module
 *
 * 项目管理功能模块导出。
 */

export { ProjectsPage } from "./pages/projects-page";
export {
  useProjects,
  useCreateProject,
  useUpdateProject,
  useDeleteProject,
} from "./hooks/use-projects";
export { useProjectsStore } from "./store/use-projects-store";
export type { ViewMode, SortBy, SortOrder } from "./store/use-projects-store";

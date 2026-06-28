/**
 * Project Types
 *
 * 项目相关的 TypeScript 类型定义，与后端 Schema 对应。
 */

/**
 * 项目实体
 */
export interface Project {
  id: string;
  title: string;
  description: string | null;
  wordCount: number;
  chapterCount: number;
  coverUrl: string | null;
  createdAt: string;
  updatedAt: string;
}

/**
 * 创建项目请求
 */
export interface ProjectCreate {
  title: string;
  description?: string | null;
  cover?: File | null;
}

/**
 * 更新项目请求
 */
export interface ProjectUpdate {
  title?: string | null;
  description?: string | null;
  cover?: File | null;
}

/**
 * 项目列表响应
 */
export interface ProjectListResponse {
  items: Project[];
  total: number;
  page: number;
  pageSize: number;
}

/**
 * 项目列表查询参数
 */
export interface ProjectListParams {
  page?: number;
  pageSize?: number;
}

/**
 * Local Database
 *
 * 使用 Dexie (IndexedDB) 存储所有本地用户数据。
 * 包括：项目最后访问章节、编辑器标签页状态、用户偏好设置等。
 */

import Dexie, { type EntityTable } from "dexie";

/**
 * 项目最后访问的章节记录
 */
interface ProjectLastChapter {
  projectId: string;
  chapterId: string;
  updatedAt: Date;
}

/**
 * 编辑器标签页记录（按项目存储）
 */
interface EditorTabRecord {
  id: string;
  chapterId?: string | null;
  refId?: string | null;
  type?: string;
  title: string;
  isLocked: boolean;
}

interface ProjectTabs {
  projectId: string;
  tabs: EditorTabRecord[];
  activeTabId: string | null;
  updatedAt: Date;
}

/**
 * 用户偏好设置
 */
interface UserPreference {
  key: string;
  value: string;
  updatedAt: Date;
}

/**
 * 提示词条目数据
 */
interface PromptEntryData {
  id?: string;
  uid?: string; // 跨版本追踪标识符
  name: string;
  role: "system" | "user" | "assistant";
  content: string;
  order_index: number;
  is_enabled: boolean;
  token_count: number;
}

/**
 * 提示词链Working Copy
 */
interface PromptChainWorkingCopy {
  chainId: string; // 提示词链ID（主键）
  baseVersionId: string; // 基于的版本ID
  entries: PromptEntryData[]; // 条目列表
  updatedAt: Date;
}

/**
 * 工作目录设置
 */
interface WorkDirSettings {
  id: string; // 固定为 "default"
  projectId: string | null;
  chapterId: string | null; // null 表示最新章节
  updatedAt: Date;
}

/**
 * OpenFic 本地数据库
 */
class OpenFicDB extends Dexie {
  projectLastChapters!: EntityTable<ProjectLastChapter, "projectId">;
  projectTabs!: EntityTable<ProjectTabs, "projectId">;
  userPreferences!: EntityTable<UserPreference, "key">;
  promptChainWorkingCopies!: EntityTable<PromptChainWorkingCopy, "chainId">;
  workDirSettings!: EntityTable<WorkDirSettings, "id">;

  constructor() {
    super("OpenFicDB");

    this.version(2).stores({
      // projectId 作为主键
      projectLastChapters: "projectId, updatedAt",
      // 项目标签页
      projectTabs: "projectId, updatedAt",
      // 用户偏好
      userPreferences: "key, updatedAt",
    });

    this.version(3).stores({
      projectLastChapters: "projectId, updatedAt",
      projectTabs: "projectId, updatedAt",
      userPreferences: "key, updatedAt",
      promptChainWorkingCopies: "chainId, updatedAt",
    });

    this.version(4).stores({
      projectLastChapters: "projectId, updatedAt",
      projectTabs: "projectId, updatedAt",
      userPreferences: "key, updatedAt",
      promptChainWorkingCopies: "chainId, updatedAt",
      workDirSettings: "id, updatedAt",
    });
  }
}

// 单例数据库实例
export const db = new OpenFicDB();

// ==================== 项目最后访问章节 ====================

/**
 * 获取项目最后访问的章节 ID
 */
export async function getLastChapterId(projectId: string): Promise<string | null> {
  try {
    const record = await db.projectLastChapters.get(projectId);
    return record?.chapterId ?? null;
  } catch {
    console.error("获取最后访问章节失败");
    return null;
  }
}

/**
 * 保存项目最后访问的章节 ID
 */
export async function setLastChapterId(projectId: string, chapterId: string): Promise<void> {
  try {
    await db.projectLastChapters.put({
      projectId,
      chapterId,
      updatedAt: new Date(),
    });
  } catch {
    console.error("保存最后访问章节失败");
  }
}

/**
 * 删除项目的最后访问记录（项目删除时调用）
 */
export async function deleteLastChapterId(projectId: string): Promise<void> {
  try {
    await db.projectLastChapters.delete(projectId);
  } catch {
    console.error("删除最后访问章节记录失败");
  }
}

// ==================== 编辑器标签页 ====================

/**
 * 获取项目的标签页状态
 */
export async function getProjectTabs(
  projectId: string,
): Promise<{ tabs: EditorTabRecord[]; activeTabId: string | null } | null> {
  try {
    const record = await db.projectTabs.get(projectId);
    if (!record) return null;
    return { tabs: record.tabs, activeTabId: record.activeTabId };
  } catch {
    console.error("获取项目标签页失败");
    return null;
  }
}

/**
 * 保存项目的标签页状态
 */
export async function setProjectTabs(
  projectId: string,
  tabs: EditorTabRecord[],
  activeTabId: string | null,
): Promise<void> {
  try {
    await db.projectTabs.put({
      projectId,
      tabs,
      activeTabId,
      updatedAt: new Date(),
    });
  } catch {
    console.error("保存项目标签页失败");
  }
}

/**
 * 删除项目的标签页记录（项目删除时调用）
 */
export async function deleteProjectTabs(projectId: string): Promise<void> {
  try {
    await db.projectTabs.delete(projectId);
  } catch {
    console.error("删除项目标签页记录失败");
  }
}

// ==================== 用户偏好设置 ====================

/**
 * 获取用户偏好
 */
export async function getPreference(key: string): Promise<string | null> {
  try {
    const record = await db.userPreferences.get(key);
    return record?.value ?? null;
  } catch {
    console.error("获取用户偏好失败");
    return null;
  }
}

/**
 * 保存用户偏好
 */
export async function setPreference(key: string, value: string): Promise<void> {
  try {
    await db.userPreferences.put({
      key,
      value,
      updatedAt: new Date(),
    });
  } catch {
    console.error("保存用户偏好失败");
  }
}

/**
 * 删除用户偏好
 */
export async function deletePreference(key: string): Promise<void> {
  try {
    await db.userPreferences.delete(key);
  } catch {
    console.error("删除用户偏好失败");
  }
}

// ==================== 提示词链Working Copy ====================

/**
 * 获取提示词链的Working Copy
 */
export async function getPromptChainWorkingCopy(
  chainId: string,
): Promise<PromptChainWorkingCopy | null> {
  try {
    const record = await db.promptChainWorkingCopies.get(chainId);
    return record ?? null;
  } catch {
    console.error("获取Working Copy失败");
    return null;
  }
}

/**
 * 保存提示词链的Working Copy
 */
export async function savePromptChainWorkingCopy(
  chainId: string,
  baseVersionId: string,
  entries: PromptEntryData[],
): Promise<void> {
  try {
    await db.promptChainWorkingCopies.put({
      chainId,
      baseVersionId,
      entries,
      updatedAt: new Date(),
    });
  } catch {
    console.error("保存Working Copy失败");
  }
}

/**
 * 删除提示词链的Working Copy
 */
export async function deletePromptChainWorkingCopy(chainId: string): Promise<void> {
  try {
    await db.promptChainWorkingCopies.delete(chainId);
  } catch {
    console.error("删除Working Copy失败");
  }
}

// ==================== 工作目录设置 ====================

/**
 * 获取工作目录设置
 */
export async function getWorkDirSettings(): Promise<{
  projectId: string | null;
  chapterId: string | null;
} | null> {
  try {
    const record = await db.workDirSettings.get("default");
    if (!record) return null;
    return { projectId: record.projectId, chapterId: record.chapterId };
  } catch {
    console.error("获取工作目录设置失败");
    return null;
  }
}

/**
 * 保存工作目录设置
 */
export async function saveWorkDirSettings(
  projectId: string | null,
  chapterId: string | null,
): Promise<void> {
  try {
    await db.workDirSettings.put({
      id: "default",
      projectId,
      chapterId,
      updatedAt: new Date(),
    });
  } catch {
    console.error("保存工作目录设置失败");
  }
}

// 导出类型
export type {
  EditorTabRecord,
  ProjectTabs,
  UserPreference,
  PromptEntryData,
  PromptChainWorkingCopy,
  WorkDirSettings,
};

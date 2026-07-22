/**
 * Local Database
 *
 * 使用 Dexie (IndexedDB) 存储所有本地用户数据。
 * 包括：项目最后访问章节、编辑器标签页状态、用户偏好设置等。
 */

import Dexie, { type EntityTable } from "dexie";

import {
  getRandomRecentProjectColor,
  insertRecentProject,
  type RecentProject,
} from "./recent-projects";

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

export type WritingWorkingCopyType = "chapter" | "note";

export interface WritingWorkingCopy {
  id: string;
  entityId: string;
  type: WritingWorkingCopyType;
  title: string;
  content: string;
  baseUpdatedAt: string;
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
  writingWorkingCopies!: EntityTable<WritingWorkingCopy, "id">;
  recentProjects!: EntityTable<RecentProject, "slot">;

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

    this.version(5).stores({
      projectLastChapters: "projectId, updatedAt",
      projectTabs: "projectId, updatedAt",
      userPreferences: "key, updatedAt",
      promptChainWorkingCopies: "chainId, updatedAt",
    });

    this.version(6).stores({
      projectLastChapters: "projectId, updatedAt",
      projectTabs: "projectId, updatedAt",
      userPreferences: "key, updatedAt",
      promptChainWorkingCopies: "chainId, updatedAt",
      recentProjects: "slot, projectId, openedAt",
    });

    this.version(7).stores({
      projectLastChapters: "projectId, updatedAt",
      projectTabs: "projectId, updatedAt",
      userPreferences: "key, updatedAt",
      promptChainWorkingCopies: "chainId, updatedAt",
      writingWorkingCopies: "id, entityId, type, updatedAt",
      recentProjects: "slot, projectId, openedAt",
    });
  }
}

// 单例数据库实例
export const db = new OpenFicDB();

const writingWorkingCopyOperations = new Map<string, Promise<void>>();

function enqueueWritingWorkingCopyOperation<T>(
  id: string,
  operation: () => Promise<T>,
): Promise<T> {
  const previous = writingWorkingCopyOperations.get(id) ?? Promise.resolve();
  const next = previous.then(operation);
  const settled = next.then(
    () => undefined,
    () => undefined,
  );
  writingWorkingCopyOperations.set(id, settled);
  void settled.finally(() => {
    if (writingWorkingCopyOperations.get(id) === settled) {
      writingWorkingCopyOperations.delete(id);
    }
  });
  return next;
}

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

// ==================== 最近项目 ====================

/**
 * 获取三个固定槽位中的最近项目记录。
 */
export async function getRecentProjects(): Promise<RecentProject[]> {
  try {
    return await db.recentProjects.orderBy("slot").toArray();
  } catch {
    console.error("获取最近项目失败");
    return [];
  }
}

/**
 * 将项目置于首槽位，并将原有记录依次后移。
 */
export async function openRecentProject(
  projectId: string,
  title: string,
): Promise<RecentProject[] | null> {
  try {
    return await db.transaction("rw", db.recentProjects, async () => {
      const recentProjects = await db.recentProjects.orderBy("slot").toArray();
      const recentProject = recentProjects.find((project) => project.projectId === projectId);
      const nextProjects = insertRecentProject(recentProjects, {
        projectId,
        title,
        color: recentProject?.color ?? getRandomRecentProjectColor(recentProjects),
      });

      await db.recentProjects.clear();
      await db.recentProjects.bulkPut(nextProjects);

      return nextProjects;
    });
  } catch {
    console.error("保存最近项目失败");
    return null;
  }
}

/**
 * 移除指定槽位的最近项目，不移动其他槽位。
 */
export async function removeRecentProject(slot: number): Promise<boolean> {
  try {
    await db.recentProjects.delete(slot);
    return true;
  } catch {
    console.error("移除最近项目失败");
    return false;
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

// ==================== 写作 Working Copy ====================

function getWritingWorkingCopyId(type: WritingWorkingCopyType, entityId: string): string {
  return `${type}:${entityId}`;
}

export async function getWritingWorkingCopy(
  type: WritingWorkingCopyType,
  entityId: string,
): Promise<WritingWorkingCopy | null> {
  const id = getWritingWorkingCopyId(type, entityId);
  try {
    await writingWorkingCopyOperations.get(id);
    return (await db.writingWorkingCopies.get(id)) ?? null;
  } catch {
    console.error("获取写作草稿失败");
    return null;
  }
}

export async function saveWritingWorkingCopy(
  workingCopy: Omit<WritingWorkingCopy, "id">,
): Promise<WritingWorkingCopy> {
  const record: WritingWorkingCopy = {
    ...workingCopy,
    id: getWritingWorkingCopyId(workingCopy.type, workingCopy.entityId),
  };

  try {
    await enqueueWritingWorkingCopyOperation(record.id, () =>
      db.transaction("rw", db.writingWorkingCopies, async () => {
        const current = await db.writingWorkingCopies.get(record.id);
        if (!current || record.updatedAt.getTime() >= current.updatedAt.getTime()) {
          await db.writingWorkingCopies.put(record);
        }
      }),
    );
  } catch {
    console.error("保存写作草稿失败");
  }

  return record;
}

export async function deleteWritingWorkingCopy(
  type: WritingWorkingCopyType,
  entityId: string,
): Promise<void> {
  const id = getWritingWorkingCopyId(type, entityId);
  try {
    await enqueueWritingWorkingCopyOperation(id, () => db.writingWorkingCopies.delete(id));
  } catch {
    console.error("删除写作草稿失败");
  }
}

export async function deleteWritingWorkingCopyIfUpdatedAt(
  type: WritingWorkingCopyType,
  entityId: string,
  updatedAt: Date,
): Promise<void> {
  const id = getWritingWorkingCopyId(type, entityId);
  try {
    await enqueueWritingWorkingCopyOperation(id, () =>
      db.transaction("rw", db.writingWorkingCopies, async () => {
        const workingCopy = await db.writingWorkingCopies.get(id);
        if (workingCopy?.updatedAt.getTime() === updatedAt.getTime()) {
          await db.writingWorkingCopies.delete(id);
        }
      }),
    );
  } catch {
    console.error("清理过期写作草稿失败");
  }
}

export async function deleteWritingWorkingCopyIfMatches(
  type: WritingWorkingCopyType,
  entityId: string,
  draft: Pick<WritingWorkingCopy, "title" | "content">,
  updatedAt: Date,
): Promise<void> {
  const id = getWritingWorkingCopyId(type, entityId);
  try {
    await enqueueWritingWorkingCopyOperation(id, () =>
      db.transaction("rw", db.writingWorkingCopies, async () => {
        const workingCopy = await db.writingWorkingCopies.get(id);
        if (
          workingCopy?.title === draft.title &&
          workingCopy.content === draft.content &&
          workingCopy.updatedAt.getTime() === updatedAt.getTime()
        ) {
          await db.writingWorkingCopies.delete(id);
        }
      }),
    );
  } catch {
    console.error("清理写作草稿失败");
  }
}

// 导出类型
export type {
  EditorTabRecord,
  ProjectTabs,
  UserPreference,
  PromptEntryData,
  PromptChainWorkingCopy,
};

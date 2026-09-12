/**
 * Local Database
 *
 * Menyimpan seluruh data pengguna lokal memakai Dexie (IndexedDB).
 * Mencakup: bab terakhir yang diakses per proyek, status tab editor, preferensi pengguna, dll.
 */

import Dexie, { type EntityTable } from "dexie";

import {
  getRandomRecentProjectColor,
  insertRecentProject,
  type RecentProject,
} from "./recent-projects";

/**
 * Catatan bab terakhir yang diakses pada sebuah proyek
 */
interface ProjectLastChapter {
  projectId: string;
  chapterId: string;
  updatedAt: Date;
}

/**
 * Catatan tab editor (disimpan per proyek)
 */
interface EditorTabRecord {
  id: string;
  chapterId?: string | null;
  refId?: string | null;
  type?: string;
  title: string;
  isLocked: boolean;
  scrollTop?: number;
}

interface ProjectTabs {
  projectId: string;
  tabs: EditorTabRecord[];
  activeTabId: string | null;
  updatedAt: Date;
}

/**
 * Preferensi pengguna
 */
interface UserPreference {
  key: string;
  value: string;
  updatedAt: Date;
}

/**
 * Data entri prompt
 */
interface PromptEntryData {
  id?: string;
  uid?: string; // Pengenal pelacakan lintas versi
  name: string;
  role: "system" | "user" | "assistant";
  content: string;
  order_index: number;
  is_enabled: boolean;
  token_count: number;
}

/**
 * Working Copy rantai prompt
 */
interface PromptChainWorkingCopy {
  chainId: string; // ID rantai prompt (kunci utama)
  baseVersionId: string; // ID versi yang menjadi dasar
  entries: PromptEntryData[]; // Daftar entri
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

interface AgentInputHistory {
  projectId: string;
  entries: string[];
  draft: string;
  updatedAt: Date;
}

/**
 * Basis data lokal OpenFic
 */
class OpenFicDB extends Dexie {
  projectLastChapters!: EntityTable<ProjectLastChapter, "projectId">;
  projectTabs!: EntityTable<ProjectTabs, "projectId">;
  userPreferences!: EntityTable<UserPreference, "key">;
  promptChainWorkingCopies!: EntityTable<PromptChainWorkingCopy, "chainId">;
  writingWorkingCopies!: EntityTable<WritingWorkingCopy, "id">;
  agentInputHistories!: EntityTable<AgentInputHistory, "projectId">;
  recentProjects!: EntityTable<RecentProject, "slot">;

  constructor() {
    super("OpenFicDB");

    this.version(2).stores({
      // projectId dipakai sebagai kunci utama
      projectLastChapters: "projectId, updatedAt",
      // Tab proyek
      projectTabs: "projectId, updatedAt",
      // Preferensi pengguna
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

    this.version(8).stores({
      projectLastChapters: "projectId, updatedAt",
      projectTabs: "projectId, updatedAt",
      userPreferences: "key, updatedAt",
      promptChainWorkingCopies: "chainId, updatedAt",
      writingWorkingCopies: "id, entityId, type, updatedAt",
      agentInputHistories: "projectId, updatedAt",
      recentProjects: "slot, projectId, openedAt",
    });
  }
}

// Instans tunggal basis data
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

// ==================== Bab terakhir yang diakses ====================

/**
 * Mengambil ID bab terakhir yang diakses pada sebuah proyek
 */
export async function getLastChapterId(projectId: string): Promise<string | null> {
  try {
    const record = await db.projectLastChapters.get(projectId);
    return record?.chapterId ?? null;
  } catch {
    console.error("Gagal mengambil bab terakhir yang diakses");
    return null;
  }
}

/**
 * Menyimpan ID bab terakhir yang diakses pada sebuah proyek
 */
export async function setLastChapterId(projectId: string, chapterId: string): Promise<void> {
  try {
    await db.projectLastChapters.put({
      projectId,
      chapterId,
      updatedAt: new Date(),
    });
  } catch {
    console.error("Gagal menyimpan bab terakhir yang diakses");
  }
}

/**
 * Menghapus catatan akses terakhir sebuah proyek (dipanggil saat proyek dihapus)
 */
export async function deleteLastChapterId(projectId: string): Promise<void> {
  try {
    await db.projectLastChapters.delete(projectId);
  } catch {
    console.error("Gagal menghapus catatan bab terakhir yang diakses");
  }
}

// ==================== Tab editor ====================

/**
 * Mengambil status tab sebuah proyek
 */
export async function getProjectTabs(
  projectId: string,
): Promise<{ tabs: EditorTabRecord[]; activeTabId: string | null } | null> {
  try {
    const record = await db.projectTabs.get(projectId);
    if (!record) return null;
    return { tabs: record.tabs, activeTabId: record.activeTabId };
  } catch {
    console.error("Gagal mengambil tab proyek");
    return null;
  }
}

/**
 * Menyimpan status tab sebuah proyek
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
    console.error("Gagal menyimpan tab proyek");
  }
}

/**
 * Menghapus catatan tab sebuah proyek (dipanggil saat proyek dihapus)
 */
export async function deleteProjectTabs(projectId: string): Promise<void> {
  try {
    await db.projectTabs.delete(projectId);
  } catch {
    console.error("Gagal menghapus catatan tab proyek");
  }
}

// ==================== Riwayat masukan Agent ====================

/**
 * Mengambil riwayat masukan Agent pada sebuah proyek.
 */
export async function getAgentInputHistory(
  projectId: string,
): Promise<{ entries: string[]; draft: string }> {
  try {
    const record = await db.agentInputHistories.get(projectId);
    return {
      entries: record?.entries ?? [],
      draft: record?.draft ?? "",
    };
  } catch {
    console.error("Gagal mengambil riwayat masukan Agent");
    return { entries: [], draft: "" };
  }
}

/**
 * Menyimpan riwayat masukan Agent dan draf yang belum terkirim pada sebuah proyek.
 */
export async function setAgentInputHistory(
  projectId: string,
  entries: string[],
  draft = "",
): Promise<void> {
  try {
    await db.agentInputHistories.put({
      projectId,
      entries,
      draft,
      updatedAt: new Date(),
    });
  } catch {
    console.error("Gagal menyimpan riwayat masukan Agent");
  }
}

/**
 * Menghapus riwayat masukan Agent pada sebuah proyek.
 */
export async function deleteAgentInputHistory(projectId: string): Promise<void> {
  try {
    await db.agentInputHistories.delete(projectId);
  } catch {
    console.error("Gagal menghapus riwayat masukan Agent");
  }
}

// ==================== Preferensi pengguna ====================

/**
 * Mengambil preferensi pengguna
 */
export async function getPreference(key: string): Promise<string | null> {
  try {
    const record = await db.userPreferences.get(key);
    return record?.value ?? null;
  } catch {
    console.error("Gagal mengambil preferensi pengguna");
    return null;
  }
}

/**
 * Menyimpan preferensi pengguna
 */
export async function setPreference(key: string, value: string): Promise<void> {
  try {
    await db.userPreferences.put({
      key,
      value,
      updatedAt: new Date(),
    });
  } catch {
    console.error("Gagal menyimpan preferensi pengguna");
  }
}

/**
 * Menghapus preferensi pengguna
 */
export async function deletePreference(key: string): Promise<void> {
  try {
    await db.userPreferences.delete(key);
  } catch {
    console.error("Gagal menghapus preferensi pengguna");
  }
}

// ==================== Proyek terbaru ====================

/**
 * Mengambil catatan proyek terbaru dari tiga slot tetap.
 */
export async function getRecentProjects(): Promise<RecentProject[]> {
  try {
    return await db.recentProjects.orderBy("slot").toArray();
  } catch {
    console.error("Gagal mengambil proyek terbaru");
    return [];
  }
}

/**
 * Memindahkan proyek ke slot pertama dan menggeser catatan lama satu per satu.
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
    console.error("Gagal menyimpan proyek terbaru");
    return null;
  }
}

/**
 * Menghapus proyek terbaru pada slot tertentu tanpa menggeser slot lain.
 */
export async function removeRecentProject(slot: number): Promise<boolean> {
  try {
    await db.recentProjects.delete(slot);
    return true;
  } catch {
    console.error("Gagal menghapus proyek terbaru");
    return false;
  }
}

/**
 * Menghapus catatan pembukaan terakhir untuk proyek tertentu.
 */
export async function removeRecentProjectByProjectId(projectId: string): Promise<boolean> {
  try {
    return (await db.recentProjects.where("projectId").equals(projectId).delete()) > 0;
  } catch {
    console.error("Gagal menghapus catatan pembukaan terakhir proyek");
    return false;
  }
}

// ==================== Working Copy rantai prompt ====================

/**
 * Mengambil Working Copy sebuah rantai prompt
 */
export async function getPromptChainWorkingCopy(
  chainId: string,
): Promise<PromptChainWorkingCopy | null> {
  try {
    const record = await db.promptChainWorkingCopies.get(chainId);
    return record ?? null;
  } catch {
    console.error("Gagal mengambil Working Copy");
    return null;
  }
}

/**
 * Menyimpan Working Copy sebuah rantai prompt
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
    console.error("Gagal menyimpan Working Copy");
  }
}

/**
 * Menghapus Working Copy sebuah rantai prompt
 */
export async function deletePromptChainWorkingCopy(chainId: string): Promise<void> {
  try {
    await db.promptChainWorkingCopies.delete(chainId);
  } catch {
    console.error("Gagal menghapus Working Copy");
  }
}

// ==================== Working Copy penulisan ====================

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
    console.error("Gagal mengambil draf penulisan");
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
    console.error("Gagal menyimpan draf penulisan");
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
    console.error("Gagal menghapus draf penulisan");
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
    console.error("Gagal membersihkan draf penulisan yang kedaluwarsa");
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
    console.error("Gagal membersihkan draf penulisan");
  }
}

// Ekspor tipe
export type {
  EditorTabRecord,
  ProjectTabs,
  UserPreference,
  PromptEntryData,
  PromptChainWorkingCopy,
};

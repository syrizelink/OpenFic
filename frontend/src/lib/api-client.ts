/**
 * API Client
 *
 * Axios instance configured for the backend API.
 */

import axios from "axios";

import { getRuntimeConfig } from "./runtime-config";

export function getApiBaseUrl(): string {
  const backendBaseUrl = getRuntimeConfig()?.backendBaseUrl;
  if (backendBaseUrl) return `${backendBaseUrl}/api/v1`;
  return "/api/v1";
}

function getApiUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBaseUrl().replace(/\/+$/, "")}${normalizedPath}`;
}

export const apiClient = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 120000,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  config.baseURL = getApiBaseUrl();
  return config;
});

// 响应拦截器 - 错误处理
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    // 开发环境记录错误日志
    if (import.meta.env.DEV) {
      console.error("API Error:", error);
    }
    return Promise.reject(error);
  },
);

// 健康检查类型
export interface HealthResponse {
  status: string;
  version: string;
}

// 健康检查 API
export async function checkHealth(): Promise<HealthResponse> {
  const response = await apiClient.get<HealthResponse>("/health");
  return response.data;
}

// ============================================
// Project API
// ============================================

import type {
  Character,
  CharacterCreate,
  CharacterListItem,
  CharacterListParams,
  CharacterListResponse,
  CharacterSearchResponse,
  CharacterUpdate,
} from "./character.types";
import type { AssistantMentionCandidate } from "./mention.types";
import type {
  Project,
  ProjectCreate,
  ProjectUpdate,
  ProjectListResponse,
  ProjectListParams,
} from "./project.types";
import type {
  SkillReferenceDoc,
  SkillReferenceDocCreate,
  SkillReferenceDocUpdate,
} from "./skill-reference-doc.types";
import type {
  Skill,
  SkillCreate,
  SkillImportResult,
  SkillListParams,
  SkillListResponse,
  SkillUpdate,
} from "./skill.types";

/**
 * 后端响应字段转换（snake_case -> camelCase）
 */
function transformProject(raw: Record<string, unknown>): Project {
  return {
    id: raw.id as string,
    title: raw.title as string,
    description: raw.description as string | null,
    wordCount: raw.word_count as number,
    chapterCount: raw.chapter_count as number,
    coverUrl: raw.cover_url as string | null,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

/**
 * 获取项目列表
 */
export async function fetchProjects(params?: ProjectListParams): Promise<ProjectListResponse> {
  const response = await apiClient.get("/projects", {
    params: {
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 20,
    },
  });
  const data = response.data;
  return {
    items: (data.items as Record<string, unknown>[]).map(transformProject),
    total: data.total,
    page: data.page,
    pageSize: data.page_size,
  };
}

/**
 * 获取单个项目
 */
export async function fetchProject(projectId: string): Promise<Project> {
  const response = await apiClient.get(`/projects/${projectId}`);
  return transformProject(response.data);
}

/**
 * 创建项目
 */
export async function createProject(data: ProjectCreate): Promise<Project> {
  const formData = new FormData();
  formData.append("title", data.title);
  if (data.description) formData.append("description", data.description);
  if (data.cover) formData.append("cover", data.cover);

  const response = await apiClient.post("/projects", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return transformProject(response.data);
}

/**
 * 更新项目
 */
export async function updateProject(projectId: string, data: ProjectUpdate): Promise<Project> {
  const formData = new FormData();
  if (data.title !== undefined) formData.append("title", data.title || "");
  if (data.description !== undefined) formData.append("description", data.description || "");
  if (data.cover) formData.append("cover", data.cover);

  const response = await apiClient.patch(`/projects/${projectId}`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return transformProject(response.data);
}

/**
 * 删除项目
 */
export async function deleteProject(projectId: string): Promise<void> {
  await apiClient.delete(`/projects/${projectId}`);
}

// ============================================
// Character API
// ============================================

function transformCharacter(raw: Record<string, unknown>): Character {
  return {
    id: raw.id as string,
    projectId: raw.project_id as string,
    name: raw.name as string,
    description: (raw.description as string) || "",
    imageUrl: raw.image_url as string | null,
    isFavorited: raw.is_favorited as boolean,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

function transformCharacterListItem(raw: Record<string, unknown>): CharacterListItem {
  return {
    id: raw.id as string,
    projectId: raw.project_id as string,
    name: raw.name as string,
    imageUrl: raw.image_url as string | null,
    tokenCount: raw.token_count as number,
    isFavorited: raw.is_favorited as boolean,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

export async function fetchCharactersByProject(
  projectId: string,
  params?: CharacterListParams,
): Promise<CharacterListResponse> {
  const response = await apiClient.get(`/projects/${projectId}/characters`, {
    params: {
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 100,
    },
  });
  const data = response.data;
  return {
    items: (data.items as Record<string, unknown>[]).map(transformCharacterListItem),
    total: data.total,
    page: data.page,
    pageSize: data.page_size,
  };
}

export async function fetchCharacter(characterId: string): Promise<Character> {
  const response = await apiClient.get(`/characters/${characterId}`);
  return transformCharacter(response.data);
}

export async function createCharacter(
  projectId: string,
  data: CharacterCreate,
): Promise<Character> {
  const formData = new FormData();
  formData.append("name", data.name);
  formData.append("description", data.description ?? "");
  if (data.image) formData.append("image", data.image);

  const response = await apiClient.post(`/projects/${projectId}/characters`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return transformCharacter(response.data);
}

export async function updateCharacter(
  characterId: string,
  data: CharacterUpdate,
): Promise<Character> {
  const formData = new FormData();
  if (data.name !== undefined) formData.append("name", data.name);
  if (data.description !== undefined) {
    formData.append("description", data.description);
  }
  if (data.isFavorited !== undefined) {
    formData.append("is_favorited", String(data.isFavorited));
  }
  if (data.image) formData.append("image", data.image);

  const response = await apiClient.patch(`/characters/${characterId}`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return transformCharacter(response.data);
}

export async function deleteCharacter(characterId: string): Promise<void> {
  await apiClient.delete(`/characters/${characterId}`);
}

export async function batchFavoriteCharacters(
  projectId: string,
  characterIds: string[],
  isFavorited: boolean,
): Promise<number> {
  const response = await apiClient.post(`/projects/${projectId}/characters/batch/favorite`, {
    character_ids: characterIds,
    is_favorited: isFavorited,
  });
  return response.data.updated_count as number;
}

export async function batchDeleteCharacters(
  projectId: string,
  characterIds: string[],
): Promise<number> {
  const response = await apiClient.post(`/projects/${projectId}/characters/batch/delete`, {
    character_ids: characterIds,
  });
  return response.data.deleted_count as number;
}

export async function searchCharacters(
  projectId: string,
  query: string,
): Promise<CharacterSearchResponse> {
  const response = await apiClient.get(`/projects/${projectId}/characters/search`, {
    params: { q: query },
  });
  const data = response.data as Record<string, unknown>;
  return {
    results: ((data.results as Record<string, unknown>[]) ?? []).map((result) => ({
      characterId: result.character_id as string,
      characterName: result.character_name as string,
      matches: ((result.matches as Record<string, unknown>[]) ?? []).map((match) => ({
        lineNumber: match.line_number as number,
        lineText: match.line_text as string,
      })),
    })),
    totalCharacters: data.total_characters as number,
    totalMatches: data.total_matches as number,
  };
}

function transformSkill(raw: Record<string, unknown>): Skill {
  return {
    id: raw.id as string,
    name: raw.name as string,
    summary: raw.summary as string,
    content: raw.content as string,
    isEnabled: raw.is_enabled as boolean,
    isComplete: raw.is_complete as boolean,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

export async function fetchSkills(params?: SkillListParams): Promise<SkillListResponse> {
  const response = await apiClient.get("/skills", {
    params: {
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 100,
    },
  });
  const data = response.data;
  return {
    items: (data.items as Record<string, unknown>[]).map(transformSkill),
    total: data.total,
    page: data.page,
    pageSize: data.page_size,
  };
}

export async function fetchSkill(skillDbId: string): Promise<Skill> {
  const response = await apiClient.get(`/skills/${skillDbId}`);
  return transformSkill(response.data);
}

export async function createSkill(data: SkillCreate): Promise<Skill> {
  const response = await apiClient.post("/skills", {
    name: data.name,
    summary: data.summary,
    content: data.content,
    is_enabled: data.isEnabled ?? false,
  });
  return transformSkill(response.data);
}

export async function importSkill(file: File): Promise<SkillImportResult> {
  const formData = new FormData();
  formData.append("files", file);
  const response = await apiClient.post("/skills/import", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return {
    skill: transformSkill(response.data.skill),
    referenceDocs: (response.data.reference_docs as Record<string, unknown>[]).map(
      transformSkillReferenceDoc,
    ),
    isRecognized: response.data.is_recognized as boolean,
  };
}

export async function updateSkill(skillDbId: string, data: SkillUpdate): Promise<Skill> {
  const response = await apiClient.patch(`/skills/${skillDbId}`, {
    name: data.name,
    summary: data.summary,
    content: data.content,
    is_enabled: data.isEnabled,
  });
  return transformSkill(response.data);
}

export async function toggleSkill(skillDbId: string): Promise<Skill> {
  const response = await apiClient.post(`/skills/${skillDbId}/toggle`);
  return transformSkill(response.data);
}

export async function deleteSkill(skillDbId: string): Promise<void> {
  await apiClient.delete(`/skills/${skillDbId}`);
}

// ============================================
// Skill Reference Docs API
// ============================================

function transformSkillReferenceDoc(raw: Record<string, unknown>): SkillReferenceDoc {
  return {
    id: raw.id as string,
    title: raw.title as string,
    content: raw.content as string,
    tokens: raw.tokens as number,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

export async function fetchSkillReferenceDocs(skillDbId: string): Promise<SkillReferenceDoc[]> {
  const response = await apiClient.get(`/skills/${skillDbId}/reference-docs`);
  return (response.data as Record<string, unknown>[]).map(transformSkillReferenceDoc);
}

export async function createSkillReferenceDoc(
  skillDbId: string,
  data: SkillReferenceDocCreate,
): Promise<SkillReferenceDoc> {
  const response = await apiClient.post(`/skills/${skillDbId}/reference-docs`, {
    title: data.title,
    content: data.content,
  });
  return transformSkillReferenceDoc(response.data);
}

export async function updateSkillReferenceDoc(
  skillDbId: string,
  docId: string,
  data: SkillReferenceDocUpdate,
): Promise<SkillReferenceDoc> {
  const response = await apiClient.patch(`/skills/${skillDbId}/reference-docs/${docId}`, {
    title: data.title,
    content: data.content,
  });
  return transformSkillReferenceDoc(response.data);
}

export async function deleteSkillReferenceDoc(skillDbId: string, docId: string): Promise<void> {
  await apiClient.delete(`/skills/${skillDbId}/reference-docs/${docId}`);
}

// ============================================
// Agent Rules API
// ============================================

import type {
  AgentRule,
  AgentRuleCreate,
  AgentRuleUpdate,
  AgentRuleListResponse,
  AgentRuleListParams,
} from "./agent-rule.types";

function transformAgentRule(raw: Record<string, unknown>): AgentRule {
  return {
    id: raw.id as string,
    title: raw.title as string,
    content: raw.content as string,
    orderIndex: (raw.order_index as number) ?? 0,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

export async function fetchAgentRules(
  params?: AgentRuleListParams,
): Promise<AgentRuleListResponse> {
  const response = await apiClient.get("/agent-rules", {
    params: {
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 100,
    },
  });
  const data = response.data;
  return {
    items: (data.items as Record<string, unknown>[]).map(transformAgentRule),
    total: data.total,
    page: data.page,
    pageSize: data.page_size,
  };
}

export async function createAgentRule(data: AgentRuleCreate): Promise<AgentRule> {
  const response = await apiClient.post("/agent-rules", {
    title: data.title,
    content: data.content,
  });
  return transformAgentRule(response.data);
}

export async function updateAgentRule(ruleId: string, data: AgentRuleUpdate): Promise<AgentRule> {
  const response = await apiClient.patch(`/agent-rules/${ruleId}`, {
    title: data.title,
    content: data.content,
  });
  return transformAgentRule(response.data);
}

export async function deleteAgentRule(ruleId: string): Promise<void> {
  await apiClient.delete(`/agent-rules/${ruleId}`);
}

export async function reorderAgentRules(ruleIds: string[]): Promise<AgentRule[]> {
  const response = await apiClient.post("/agent-rules/reorder", {
    rule_ids: ruleIds,
  });
  return (response.data as Record<string, unknown>[]).map(transformAgentRule);
}

// ============================================
// Agent Memories API
// ============================================

import type {
  AgentMemory,
  AgentMemoryCreate,
  AgentMemoryUpdate,
  AgentMemoryListResponse,
  AgentMemoryListParams,
} from "./agent-memory.types";

function transformAgentMemory(raw: Record<string, unknown>): AgentMemory {
  return {
    id: raw.id as string,
    content: raw.content as string,
    orderIndex: (raw.order_index as number) ?? 0,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

export async function fetchAgentMemories(
  params?: AgentMemoryListParams,
): Promise<AgentMemoryListResponse> {
  const response = await apiClient.get("/agent-memories", {
    params: {
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 100,
    },
  });
  const data = response.data;
  return {
    items: (data.items as Record<string, unknown>[]).map(transformAgentMemory),
    total: data.total,
    page: data.page,
    pageSize: data.page_size,
  };
}

export async function createAgentMemory(data: AgentMemoryCreate): Promise<AgentMemory> {
  const response = await apiClient.post("/agent-memories", {
    content: data.content,
  });
  return transformAgentMemory(response.data);
}

export async function updateAgentMemory(
  memoryId: string,
  data: AgentMemoryUpdate,
): Promise<AgentMemory> {
  const response = await apiClient.patch(`/agent-memories/${memoryId}`, {
    content: data.content,
  });
  return transformAgentMemory(response.data);
}

export async function deleteAgentMemory(memoryId: string): Promise<void> {
  await apiClient.delete(`/agent-memories/${memoryId}`);
}

export async function reorderAgentMemories(memoryIds: string[]): Promise<AgentMemory[]> {
  const response = await apiClient.post("/agent-memories/reorder", {
    memory_ids: memoryIds,
  });
  return (response.data as Record<string, unknown>[]).map(transformAgentMemory);
}

// ============================================
// Chapter API
// ============================================

import type {
  Chapter,
  ChapterCreate,
  ChapterUpdate,
  ChapterListItem,
  ChapterMoveToVolume,
  Volume,
  VolumeCreate,
  VolumeMove,
  VolumeTreeResponse,
  VolumeUpdate,
  VolumeWithChapters,
} from "./chapter.types";

/**
 * 后端响应字段转换（snake_case -> camelCase）- 完整版章节
 */
function transformChapter(raw: Record<string, unknown>): Chapter {
  return {
    id: raw.id as string,
    projectId: raw.project_id as string,
    volumeId: raw.volume_id as string,
    title: raw.title as string,
    content: raw.content as string,
    wordCount: raw.word_count as number,
    order: raw.order as number,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

/**
 * 后端响应字段转换（snake_case -> camelCase）- 精简版章节列表项
 */
function transformChapterListItem(raw: Record<string, unknown>): ChapterListItem {
  return {
    id: raw.id as string,
    projectId: raw.project_id as string,
    volumeId: raw.volume_id as string,
    title: raw.title as string,
    wordCount: raw.word_count as number,
    order: raw.order as number,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

function transformVolume(raw: Record<string, unknown>): Volume {
  return {
    id: raw.id as string,
    projectId: raw.project_id as string,
    title: raw.title as string,
    description: (raw.description as string | null | undefined) ?? null,
    order: raw.order as number,
    chapterCount: raw.chapter_count as number,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

function transformVolumeWithChapters(raw: Record<string, unknown>): VolumeWithChapters {
  return {
    ...transformVolume(raw),
    chapters: ((raw.chapters as Record<string, unknown>[]) ?? []).map(transformChapterListItem),
  };
}

function transformVolumeTree(raw: Record<string, unknown>): VolumeTreeResponse {
  return {
    volumes: ((raw.volumes as Record<string, unknown>[]) ?? []).map(transformVolumeWithChapters),
    totalChapters: raw.total_chapters as number,
  };
}

function transformMentionCandidate(raw: Record<string, unknown>): AssistantMentionCandidate {
  return {
    kind: raw.kind as
      | "volume"
      | "chapter"
      | "note"
      | "note_category"
      | "world_info_entry"
      | "character",
    id: raw.id as string,
    title: raw.title as string,
    label: raw.label as string,
    description: typeof raw.description === "string" ? raw.description : undefined,
  };
}

/**
 * 获取卷-章节树
 */
export async function fetchChapters(projectId: string): Promise<VolumeTreeResponse> {
  const response = await apiClient.get(`/projects/${projectId}/chapters`);
  return transformVolumeTree(response.data);
}

export async function searchMentionCandidates(
  projectId: string,
  query: string,
  limit = 20,
  kind?: "volume" | "chapter" | "note" | "note_category" | "world_info_entry" | "character",
  signal?: AbortSignal,
): Promise<AssistantMentionCandidate[]> {
  const response = await apiClient.get<Record<string, unknown>>(`/projects/${projectId}/mentions`, {
    params: {
      query,
      limit,
      ...(kind ? { kind } : {}),
    },
    signal,
  });
  return ((response.data.items as Record<string, unknown>[]) ?? []).map(transformMentionCandidate);
}

/**
 * 获取单个章节
 */
export async function fetchChapter(chapterId: string): Promise<Chapter> {
  const response = await apiClient.get(`/chapters/${chapterId}`);
  return transformChapter(response.data);
}

/**
 * 创建章节
 */
export async function createChapter(projectId: string, data: ChapterCreate): Promise<Chapter> {
  const response = await apiClient.post(`/projects/${projectId}/chapters`, {
    volume_id: data.volumeId,
    title: data.title,
    content: data.content ?? "",
    word_count: data.wordCount,
  });
  return transformChapter(response.data);
}

export async function createVolume(projectId: string, data: VolumeCreate): Promise<Volume> {
  const response = await apiClient.post(`/projects/${projectId}/volumes`, {
    title: data.title,
    description: data.description ?? null,
  });
  return transformVolume(response.data);
}

export async function fetchVolumes(projectId: string): Promise<Volume[]> {
  const response = await apiClient.get(`/projects/${projectId}/volumes`);
  return (response.data as Record<string, unknown>[]).map(transformVolume);
}

export async function fetchVolume(volumeId: string): Promise<Volume> {
  const response = await apiClient.get(`/volumes/${volumeId}`);
  return transformVolume(response.data);
}

export async function updateVolume(volumeId: string, data: VolumeUpdate): Promise<Volume> {
  const response = await apiClient.patch(`/volumes/${volumeId}`, {
    title: data.title,
    description: data.description,
  });
  return transformVolume(response.data);
}

export async function deleteVolume(volumeId: string, cascade = false): Promise<void> {
  await apiClient.delete(`/volumes/${volumeId}`, {
    params: { cascade },
  });
}

export async function moveVolume(volumeId: string, data: VolumeMove): Promise<Volume> {
  const response = await apiClient.post(`/volumes/${volumeId}/move`, {
    new_order: data.newOrder,
  });
  return transformVolume(response.data);
}

/**
 * 更新章节
 */
export async function updateChapter(chapterId: string, data: ChapterUpdate): Promise<Chapter> {
  const response = await apiClient.patch(`/chapters/${chapterId}`, {
    title: data.title,
    content: data.content,
    word_count: data.wordCount,
  });
  return transformChapter(response.data);
}

/**
 * 删除章节
 */
export async function deleteChapter(chapterId: string): Promise<void> {
  await apiClient.delete(`/chapters/${chapterId}`);
}

/**
 * 批量重排章节顺序
 */
export async function reorderChapters(
  volumeId: string,
  chapterIds: string[],
): Promise<ChapterListItem[]> {
  const response = await apiClient.post("/chapters/reorder", {
    volume_id: volumeId,
    chapter_ids: chapterIds,
  });
  return (response.data as Record<string, unknown>[]).map(transformChapterListItem);
}

export async function moveChapterToVolume(
  chapterId: string,
  data: ChapterMoveToVolume,
): Promise<Chapter> {
  const response = await apiClient.post(`/chapters/${chapterId}/move-to-volume`, {
    volume_id: data.volumeId,
  });
  return transformChapter(response.data);
}

// ============================================
// Chapter Context API
// ============================================

/**
 * 上下文部分响应
 */
export interface ContextPartResponse {
  content: string;
  token_count: number;
  chapter_range: [number, number];
}

/**
 * 构建的上下文响应
 */
export interface BuiltContextResponse {
  latest_field: ContextPartResponse;
  near_field: ContextPartResponse;
  mid_field: ContextPartResponse;
  far_field: ContextPartResponse;
}

/**
 * 获取构建的章节上下文
 */
export async function fetchChapterContext(
  projectId: string,
  currentOrder: number,
): Promise<BuiltContextResponse> {
  const response = await apiClient.get<BuiltContextResponse>(
    `/projects/${projectId}/chapter-context/context`,
    {
      params: {
        current_order: currentOrder,
      },
    },
  );
  return response.data;
}

/**
 * 上下文字段响应（纯文本）
 */
export interface ContextFieldResponse {
  content: string;
}

export type SummaryStatus = "not_generated" | "queued" | "running" | "ready" | "failed";

export interface LongTermSummaryListItem {
  startOrder: number;
  endOrder: number;
  startVolumeTitle: string | null;
  startChapterTitle: string;
  endVolumeTitle: string | null;
  endChapterTitle: string;
  status: SummaryStatus;
  isStale: boolean;
  summaryId: string | null;
  startTime: string;
  endTime: string;
  summary: string;
  errorMessage: string | null;
  updatedAt: string | null;
}

export interface SummaryStatusItem {
  chapterId: string;
  volumeId: string | null;
  status: SummaryStatus;
  isStale: boolean;
  summaryId: string | null;
  updatedAt: string | null;
}

export interface SummaryPanelResponse {
  maintenance: SummaryMaintenance;
}

export interface SummaryRealtimeSnapshot {
  projectId: string;
  projectRevision: number | null;
  summary: {
    statuses: SummaryStatusItem[];
    maintenance: SummaryMaintenance;
  };
}

export interface ChapterSummaryListItem {
  chapterId: string;
  chapterOrder: number;
  volumeId: string | null;
  volumeTitle: string | null;
  volumeOrder: number | null;
  chapterTitle: string;
  status: SummaryStatus;
  isStale: boolean;
  summaryId: string | null;
  startTime: string;
  endTime: string;
  characters: string[];
  locations: string[];
  summary: string;
  errorMessage: string | null;
  updatedAt: string | null;
}

export interface ChapterSummaryListResponse {
  items: ChapterSummaryListItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface LongTermSummaryListResponse {
  items: LongTermSummaryListItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface MissingChapterSummaryItem {
  chapterId: string;
  chapterOrder: number;
  volumeId: string | null;
  volumeTitle: string | null;
  volumeOrder: number | null;
  chapterTitle: string;
  wordCount: number;
  status: SummaryStatus;
  isStale: boolean;
  summaryId: string | null;
  progressMessage: string | null;
}

export interface MissingLongTermSummaryItem {
  startOrder: number;
  endOrder: number;
  startVolumeTitle: string | null;
  startChapterTitle: string;
  endVolumeTitle: string | null;
  endChapterTitle: string;
  status: SummaryStatus;
  isStale: boolean;
  summaryId: string | null;
  progressMessage: string | null;
}

export interface SkippedChapterSummaryItem {
  chapterId: string;
  chapterOrder: number;
  volumeId: string | null;
  volumeTitle: string | null;
  volumeOrder: number | null;
  chapterTitle: string;
  wordCount: number;
}

export interface SummaryBackgroundJobItem {
  jobId: string;
  jobType: "chapter_summary" | "long_term_summary" | "summary_batch";
  status: string;
  chapterId: string | null;
  summaryId: string | null;
  startOrder: number | null;
  endOrder: number | null;
  progressCurrent: number;
  progressTotal: number | null;
  progressMessage: string | null;
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface SummaryBatchProgressItem {
  jobId: string;
  status: string;
  progressCurrent: number;
  progressTotal: number | null;
  progressPercent: number | null;
  progressMessage: string | null;
  totalItemCount: number;
  completedItemCount: number;
  runningItemCount: number;
  queuedItemCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface SummaryMaintenance {
  autoGenerationBlocked: boolean;
  blockReasonCode: string | null;
  blockReasonParams: Record<string, number | string> | null;
  missingOrFailedChapterSummaries: MissingChapterSummaryItem[];
  missingOrFailedLongTermSummaries: MissingLongTermSummaryItem[];
  skippedChapterSummaries: SkippedChapterSummaryItem[];
  batchProgress: SummaryBatchProgressItem | null;
  activeJobs: SummaryBackgroundJobItem[];
}

export interface EnqueueSummaryRequest {
  summaryType: "chapter" | "long_term" | "all";
  chapterId?: string;
  startOrder?: number;
  endOrder?: number;
}

export interface EnqueueSummaryResponse {
  summaryId: string | null;
  status: string;
  jobId: string | null;
  itemCount: number;
}

function transformSummaryStatusItem(raw: Record<string, unknown>): SummaryStatusItem {
  return {
    chapterId: raw.chapter_id as string,
    volumeId: (raw.volume_id as string | null) ?? null,
    status: raw.status as SummaryStatus,
    isStale: Boolean(raw.is_stale),
    summaryId: raw.summary_id as string | null,
    updatedAt: raw.updated_at as string | null,
  };
}

function transformLongTermSummaryListItem(raw: Record<string, unknown>): LongTermSummaryListItem {
  return {
    startOrder: Number(raw.start_order ?? 0),
    endOrder: Number(raw.end_order ?? 0),
    startVolumeTitle: (raw.start_volume_title as string | null) ?? null,
    startChapterTitle: (raw.start_chapter_title as string) || "",
    endVolumeTitle: (raw.end_volume_title as string | null) ?? null,
    endChapterTitle: (raw.end_chapter_title as string) || "",
    status: raw.status as SummaryStatus,
    isStale: Boolean(raw.is_stale),
    summaryId: raw.summary_id as string | null,
    startTime: (raw.start_time as string) || "",
    endTime: (raw.end_time as string) || "",
    summary: (raw.summary as string) || "",
    errorMessage: raw.error_message as string | null,
    updatedAt: raw.updated_at as string | null,
  };
}

function transformChapterSummaryListItem(raw: Record<string, unknown>): ChapterSummaryListItem {
  return {
    chapterId: raw.chapter_id as string,
    chapterOrder: Number(raw.chapter_order ?? 0),
    volumeId: (raw.volume_id as string | null) ?? null,
    volumeTitle: (raw.volume_title as string | null) ?? null,
    volumeOrder: raw.volume_order == null ? null : Number(raw.volume_order),
    chapterTitle: (raw.chapter_title as string) || "未命名章节",
    status: raw.status as SummaryStatus,
    isStale: Boolean(raw.is_stale),
    summaryId: raw.summary_id as string | null,
    startTime: (raw.start_time as string) || "",
    endTime: (raw.end_time as string) || "",
    characters: (raw.characters as string[]) || [],
    locations: (raw.locations as string[]) || [],
    summary: (raw.summary as string) || "",
    errorMessage: raw.error_message as string | null,
    updatedAt: raw.updated_at as string | null,
  };
}

function transformSummaryMaintenance(raw: Record<string, unknown>): SummaryMaintenance {
  return {
    autoGenerationBlocked: Boolean(raw.auto_generation_blocked),
    blockReasonCode: (raw.block_reason_code as string | null) ?? null,
    blockReasonParams: (raw.block_reason_params as Record<string, number | string> | null) ?? null,
    missingOrFailedChapterSummaries: (
      (raw.missing_or_failed_chapter_summaries as Record<string, unknown>[]) || []
    ).map((item) => ({
      chapterId: item.chapter_id as string,
      chapterOrder: item.chapter_order as number,
      volumeId: (item.volume_id as string | null) ?? null,
      volumeTitle: (item.volume_title as string | null) ?? null,
      volumeOrder: item.volume_order == null ? null : Number(item.volume_order),
      chapterTitle: item.chapter_title as string,
      wordCount: Number(item.word_count ?? 0),
      status: item.status as SummaryStatus,
      isStale: Boolean(item.is_stale),
      summaryId: item.summary_id as string | null,
      progressMessage: (item.progress_message as string | null) ?? null,
    })),
    missingOrFailedLongTermSummaries: (
      (raw.missing_or_failed_long_term_summaries as Record<string, unknown>[]) || []
    ).map((item) => ({
      startOrder: item.start_order as number,
      endOrder: item.end_order as number,
      startVolumeTitle: (item.start_volume_title as string | null) ?? null,
      startChapterTitle: (item.start_chapter_title as string) || "",
      endVolumeTitle: (item.end_volume_title as string | null) ?? null,
      endChapterTitle: (item.end_chapter_title as string) || "",
      status: item.status as SummaryStatus,
      isStale: Boolean(item.is_stale),
      summaryId: item.summary_id as string | null,
      progressMessage: (item.progress_message as string | null) ?? null,
    })),
    skippedChapterSummaries: (
      (raw.skipped_chapter_summaries as Record<string, unknown>[]) || []
    ).map((item) => ({
      chapterId: item.chapter_id as string,
      chapterOrder: Number(item.chapter_order ?? 0),
      volumeId: (item.volume_id as string | null) ?? null,
      volumeTitle: (item.volume_title as string | null) ?? null,
      volumeOrder: item.volume_order == null ? null : Number(item.volume_order),
      chapterTitle: (item.chapter_title as string) || "未命名章节",
      wordCount: Number(item.word_count ?? 0),
    })),
    batchProgress: raw.batch_progress
      ? {
          jobId: (raw.batch_progress as Record<string, unknown>).job_id as string,
          status: (raw.batch_progress as Record<string, unknown>).status as string,
          progressCurrent: Number(
            (raw.batch_progress as Record<string, unknown>).progress_current ?? 0,
          ),
          progressTotal:
            (raw.batch_progress as Record<string, unknown>).progress_total == null
              ? null
              : Number((raw.batch_progress as Record<string, unknown>).progress_total),
          progressPercent:
            (raw.batch_progress as Record<string, unknown>).progress_percent == null
              ? null
              : Number((raw.batch_progress as Record<string, unknown>).progress_percent),
          progressMessage:
            ((raw.batch_progress as Record<string, unknown>).progress_message as string | null) ??
            null,
          totalItemCount: Number(
            (raw.batch_progress as Record<string, unknown>).total_item_count ?? 0,
          ),
          completedItemCount: Number(
            (raw.batch_progress as Record<string, unknown>).completed_item_count ?? 0,
          ),
          runningItemCount: Number(
            (raw.batch_progress as Record<string, unknown>).running_item_count ?? 0,
          ),
          queuedItemCount: Number(
            (raw.batch_progress as Record<string, unknown>).queued_item_count ?? 0,
          ),
          createdAt: (raw.batch_progress as Record<string, unknown>).created_at as string,
          updatedAt: (raw.batch_progress as Record<string, unknown>).updated_at as string,
        }
      : null,
    activeJobs: ((raw.active_jobs as Record<string, unknown>[]) || []).map((item) => ({
      jobId: item.job_id as string,
      jobType: item.job_type as "chapter_summary" | "long_term_summary" | "summary_batch",
      status: item.status as string,
      chapterId: (item.chapter_id as string | null) ?? null,
      summaryId: (item.summary_id as string | null) ?? null,
      startOrder: (item.start_order as number | null) ?? null,
      endOrder: (item.end_order as number | null) ?? null,
      progressCurrent: Number(item.progress_current ?? 0),
      progressTotal: item.progress_total == null ? null : Number(item.progress_total),
      progressMessage: (item.progress_message as string | null) ?? null,
      errorMessage: (item.error_message as string | null) ?? null,
      createdAt: item.created_at as string,
      updatedAt: item.updated_at as string,
    })),
  };
}

export function transformSummaryRealtimeSnapshot(
  raw: Record<string, unknown>,
): SummaryRealtimeSnapshot {
  const summary = (raw.summary as Record<string, unknown>) || {};
  return {
    projectId: raw.project_id as string,
    projectRevision: raw.project_revision == null ? null : Number(raw.project_revision),
    summary: {
      statuses: ((summary.statuses as Record<string, unknown>[]) || []).map(
        transformSummaryStatusItem,
      ),
      maintenance: transformSummaryMaintenance(
        (summary.maintenance as Record<string, unknown>) || {},
      ),
    },
  };
}

export async function fetchChapterSummaryList(
  projectId: string,
  page: number,
  pageSize = 20,
  signal?: AbortSignal,
  volumeId?: string | null,
  query?: string,
): Promise<ChapterSummaryListResponse> {
  const response = await apiClient.get<Record<string, unknown>>(
    `/projects/${projectId}/chapter-context/summaries/chapters`,
    {
      params: {
        page,
        page_size: pageSize,
        ...(volumeId ? { volume_id: volumeId } : {}),
        ...(query ? { q: query } : {}),
      },
      signal,
    },
  );
  return {
    items: ((response.data.items as Record<string, unknown>[]) || []).map(
      transformChapterSummaryListItem,
    ),
    total: Number(response.data.total ?? 0),
    page: Number(response.data.page ?? page),
    pageSize: Number(response.data.page_size ?? pageSize),
  };
}

export async function deleteChapterSummaries(
  projectId: string,
  chapterIds: string[],
): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/chapter-context/summaries/chapters`, {
    data: {
      chapter_ids: chapterIds,
    },
  });
}

export async function deleteLongTermSummaries(
  projectId: string,
  ranges: Array<[number, number]>,
): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/chapter-context/summaries/long-term`, {
    data: {
      ranges,
    },
  });
}

export async function fetchLongTermSummariesPage(
  projectId: string,
  page: number,
  pageSize = 20,
  signal?: AbortSignal,
  query?: string,
): Promise<LongTermSummaryListResponse> {
  const response = await apiClient.get<Record<string, unknown>>(
    `/projects/${projectId}/chapter-context/summaries/long-term`,
    { params: { page, page_size: pageSize, ...(query ? { q: query } : {}) }, signal },
  );
  return {
    items: ((response.data.items as Record<string, unknown>[]) || []).map(
      transformLongTermSummaryListItem,
    ),
    total: Number(response.data.total ?? 0),
    page: Number(response.data.page ?? page),
    pageSize: Number(response.data.page_size ?? pageSize),
  };
}

export async function enqueueSummary(
  projectId: string,
  data: EnqueueSummaryRequest,
): Promise<EnqueueSummaryResponse> {
  const response = await apiClient.post<Record<string, unknown>>(
    `/projects/${projectId}/chapter-context/summaries/enqueue`,
    {
      summary_type: data.summaryType,
      chapter_id: data.chapterId,
      start_order: data.startOrder,
      end_order: data.endOrder,
    },
  );
  return {
    summaryId: (response.data.summary_id as string | null) ?? null,
    status: (response.data.status as string) || "queued",
    jobId: (response.data.job_id as string | null) ?? null,
    itemCount: Number(response.data.item_count ?? 0),
  };
}

export async function cancelBackgroundJob(jobId: string, reason: string): Promise<void> {
  await apiClient.post(`/background/jobs/${jobId}/cancel`, { reason });
}

/**
 * 获取近场上下文
 */
export async function fetchNearField(
  projectId: string,
  currentOrder: number,
): Promise<ContextFieldResponse> {
  const response = await apiClient.get<ContextFieldResponse>(
    `/projects/${projectId}/chapter-context/near`,
    {
      params: {
        current_order: currentOrder,
      },
    },
  );
  return response.data;
}

/**
 * 获取中场上下文
 */
export async function fetchMiddleField(
  projectId: string,
  currentOrder: number,
): Promise<ContextFieldResponse> {
  const response = await apiClient.get<ContextFieldResponse>(
    `/projects/${projectId}/chapter-context/middle`,
    {
      params: {
        current_order: currentOrder,
      },
    },
  );
  return response.data;
}

/**
 * 获取远场上下文
 */
export async function fetchFarField(
  projectId: string,
  currentOrder: number,
): Promise<ContextFieldResponse> {
  const response = await apiClient.get<ContextFieldResponse>(
    `/projects/${projectId}/chapter-context/far`,
    {
      params: {
        current_order: currentOrder,
      },
    },
  );
  return response.data;
}

/**
 * 获取最新章节内容
 */
export async function fetchLatestField(
  projectId: string,
  currentOrder: number,
): Promise<ContextFieldResponse> {
  const response = await apiClient.get<ContextFieldResponse>(
    `/projects/${projectId}/chapter-context/latest`,
    {
      params: {
        current_order: currentOrder,
      },
    },
  );
  return response.data;
}

// ============================================
// World Info API
// ============================================

import type {
  WorldInfo,
  WorldInfoImportCompleteEvent,
  WorldInfoImportEvent,
  WorldInfoImportMode,
  WorldInfoImportPreviewResponse,
  WorldInfoEntry,
  WorldInfoEntryBrief,
  WorldInfoEntryCreate,
  WorldInfoEntryUpdate,
  WorldInfoEntryBriefListResponse,
  WorldInfoEntryListParams,
  WorldInfoEntrySearchResponse,
} from "./world-info.types";

/**
 * 后端响应字段转换（snake_case -> camelCase）
 */
function transformWorldInfo(raw: Record<string, unknown>): WorldInfo {
  return {
    id: raw.id as string,
    projectId: raw.project_id as string | null,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

/**
 * 后端响应字段转换（snake_case -> camelCase）
 */
function transformWorldInfoEntry(raw: Record<string, unknown>): WorldInfoEntry {
  return {
    id: raw.id as string,
    worldInfoId: raw.world_info_id as string,
    uid: raw.uid as number,
    name: raw.name as string,
    order: raw.order as number,
    content: raw.content as string,
    tokenCount: raw.token_count as number,
    isEnabled: raw.is_enabled as boolean,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

function transformWorldInfoEntryBrief(raw: Record<string, unknown>): WorldInfoEntryBrief {
  return {
    id: raw.id as string,
    worldInfoId: raw.world_info_id as string,
    uid: raw.uid as number,
    name: raw.name as string,
    order: raw.order as number,
    tokenCount: raw.token_count as number,
    isEnabled: raw.is_enabled as boolean,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

function transformWorldInfoImportPreview(
  raw: Record<string, unknown>,
): WorldInfoImportPreviewResponse {
  return {
    entryCount: raw.entry_count as number,
    enabledCount: raw.enabled_count as number,
    entries: ((raw.entries as Record<string, unknown>[]) || []).map((entry) => ({
      uid: entry.uid as number,
      name: entry.name as string,
      contentPreview: (entry.content_preview as string) || "",
      isEnabled: Boolean(entry.is_enabled),
    })),
  };
}

/**
 * 根据 ID 获取世界书
 */
export async function fetchWorldInfoById(worldInfoId: string): Promise<WorldInfo> {
  const response = await apiClient.get(`/world-info/${worldInfoId}`);
  return transformWorldInfo(response.data);
}

/**
 * 获取项目的世界书
 */
export async function fetchWorldInfoByProject(projectId: string): Promise<WorldInfo> {
  const response = await apiClient.get(`/projects/${projectId}/world-info`);
  return transformWorldInfo(response.data);
}

/**
 * 删除世界书
 */
export async function deleteWorldInfo(worldInfoId: string): Promise<void> {
  await apiClient.delete(`/world-info/${worldInfoId}`);
}

/**
 * 获取世界书条目列表（轻量，不含 content/memo/tags）
 */
export async function fetchWorldInfoEntries(
  worldInfoId: string,
  params?: WorldInfoEntryListParams,
): Promise<WorldInfoEntryBriefListResponse> {
  const response = await apiClient.get(`/world-info/${worldInfoId}/entries`, {
    params: {
      page: params?.page ?? 1,
      page_size: params?.pageSize ?? 100,
    },
  });
  const data = response.data;
  return {
    items: (data.items as Record<string, unknown>[]).map(transformWorldInfoEntryBrief),
    total: data.total,
    page: data.page,
    pageSize: data.page_size,
  };
}

/**
 * 获取单个条目
 */
export async function fetchWorldInfoEntry(entryId: string): Promise<WorldInfoEntry> {
  const response = await apiClient.get(`/world-info-entries/${entryId}`);
  return transformWorldInfoEntry(response.data);
}

/**
 * 创建条目
 */
export async function createWorldInfoEntry(
  worldInfoId: string,
  data: WorldInfoEntryCreate,
): Promise<WorldInfoEntry> {
  const response = await apiClient.post(`/world-info/${worldInfoId}/entries`, {
    name: data.name,
    content: data.content ?? "",
    token_count: data.tokenCount ?? 0,
    is_enabled: data.isEnabled ?? true,
  });
  return transformWorldInfoEntry(response.data);
}

/**
 * 更新条目
 */
export async function updateWorldInfoEntry(
  entryId: string,
  data: WorldInfoEntryUpdate,
): Promise<WorldInfoEntry> {
  const response = await apiClient.patch(`/world-info-entries/${entryId}`, {
    name: data.name,
    content: data.content,
    token_count: data.tokenCount,
    is_enabled: data.isEnabled,
  });
  return transformWorldInfoEntry(response.data);
}

/**
 * 删除条目
 */
export async function deleteWorldInfoEntry(entryId: string): Promise<void> {
  await apiClient.delete(`/world-info-entries/${entryId}`);
}

/**
 * 删除世界书的所有条目
 */
export async function deleteAllWorldInfoEntries(
  worldInfoId: string,
): Promise<{ deletedCount: number }> {
  const response = await apiClient.delete(`/world-info/${worldInfoId}/entries`);
  return { deletedCount: response.data.deleted_count };
}

/**
 * 移动条目
 */
export async function moveWorldInfoEntry(
  entryId: string,
  newOrder: number,
): Promise<WorldInfoEntry> {
  const response = await apiClient.post(`/world-info-entries/${entryId}/move`, {
    new_order: newOrder,
  });
  return transformWorldInfoEntry(response.data);
}

/**
 * 批量重新排序世界书条目
 */
export async function reorderWorldInfoEntries(
  worldInfoId: string,
  orders: Record<string, number>,
): Promise<WorldInfoEntry[]> {
  const response = await apiClient.post(`/world-info/${worldInfoId}/entries/reorder`, {
    orders,
  });
  return response.data.map(transformWorldInfoEntry);
}

/**
 * 切换条目开关
 */
export async function toggleWorldInfoEntry(entryId: string): Promise<WorldInfoEntry> {
  const response = await apiClient.post(`/world-info-entries/${entryId}/toggle`);
  return transformWorldInfoEntry(response.data);
}

/**
 * 批量切换条目开关
 */
export async function batchToggleWorldInfoEntries(
  worldInfoId: string,
  entryIds: string[],
  isEnabled: boolean,
): Promise<number> {
  const response = await apiClient.post(`/world-info/${worldInfoId}/entries/batch/toggle`, {
    entry_ids: entryIds,
    is_enabled: isEnabled,
  });
  return response.data.updated_count as number;
}

/**
 * 批量删除条目
 */
export async function batchDeleteWorldInfoEntries(
  worldInfoId: string,
  entryIds: string[],
): Promise<number> {
  const response = await apiClient.post(`/world-info/${worldInfoId}/entries/batch/delete`, {
    entry_ids: entryIds,
  });
  return response.data.deleted_count as number;
}

/**
 * 搜索世界书条目内容
 */
export async function searchWorldInfoEntries(
  worldInfoId: string,
  query: string,
): Promise<WorldInfoEntrySearchResponse> {
  const response = await apiClient.get(`/world-info/${worldInfoId}/entries/search`, {
    params: { q: query },
  });
  const data = response.data as Record<string, unknown>;
  return {
    results: ((data.results as Record<string, unknown>[]) ?? []).map(
      (r: Record<string, unknown>) => ({
        entryId: r.entry_id as string,
        entryName: r.entry_name as string,
        uid: r.uid as number,
        matches: ((r.matches as Record<string, unknown>[]) ?? []).map(
          (m: Record<string, unknown>) => ({
            lineNumber: m.line_number as number,
            lineText: m.line_text as string,
          }),
        ),
      }),
    ),
    totalEntries: data.total_entries as number,
    totalMatches: data.total_matches as number,
  };
}

export interface ChapterSearchMatch {
  lineNumber: number;
  lineText: string;
}

export interface ChapterSearchResultItem {
  chapterId: string;
  chapterTitle: string;
  volumeTitle: string;
  matches: ChapterSearchMatch[];
}

export interface ChapterSearchResponse {
  results: ChapterSearchResultItem[];
  totalChapters: number;
  totalMatches: number;
}

export async function searchChapters(
  projectId: string,
  query: string,
): Promise<ChapterSearchResponse> {
  const response = await apiClient.get(`/projects/${projectId}/chapters/search`, {
    params: { q: query },
  });
  const data = response.data as Record<string, unknown>;
  return {
    results: ((data.results as Record<string, unknown>[]) ?? []).map(
      (r: Record<string, unknown>) => ({
        chapterId: r.chapter_id as string,
        chapterTitle: r.chapter_title as string,
        volumeTitle: r.volume_title as string,
        matches: ((r.matches as Record<string, unknown>[]) ?? []).map(
          (m: Record<string, unknown>) => ({
            lineNumber: m.line_number as number,
            lineText: m.line_text as string,
          }),
        ),
      }),
    ),
    totalChapters: data.total_chapters as number,
    totalMatches: data.total_matches as number,
  };
}

export interface NoteSearchMatch {
  lineNumber: number;
  lineText: string;
}

export interface NoteSearchResultItem {
  noteId: string;
  noteTitle: string;
  categoryPath: string;
  matches: NoteSearchMatch[];
}

export interface NoteSearchResponse {
  results: NoteSearchResultItem[];
  totalNotes: number;
  totalMatches: number;
}

export async function searchNotes(projectId: string, query: string): Promise<NoteSearchResponse> {
  const response = await apiClient.get(`/projects/${projectId}/notes/search`, {
    params: { q: query },
  });
  const data = response.data as Record<string, unknown>;
  return {
    results: ((data.results as Record<string, unknown>[]) ?? []).map(
      (r: Record<string, unknown>) => ({
        noteId: r.note_id as string,
        noteTitle: r.note_title as string,
        categoryPath: r.category_path as string,
        matches: ((r.matches as Record<string, unknown>[]) ?? []).map(
          (m: Record<string, unknown>) => ({
            lineNumber: m.line_number as number,
            lineText: m.line_text as string,
          }),
        ),
      }),
    ),
    totalNotes: data.total_notes as number,
    totalMatches: data.total_matches as number,
  };
}

/**
 * 预览 SillyTavern 世界书导入结果
 */
export async function previewWorldInfoImport(file: File): Promise<WorldInfoImportPreviewResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiClient.post("/world-info/import/preview", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return transformWorldInfoImportPreview(response.data as Record<string, unknown>);
}

/**
 * 流式导入世界书条目
 */
export async function importWorldInfoEntriesStream(
  worldInfoId: string,
  file: File,
  mode: WorldInfoImportMode,
  onEvent: (event: WorldInfoImportEvent) => void,
): Promise<WorldInfoImportCompleteEvent | null> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(
    getApiUrl(`/world-info/${worldInfoId}/entries/import-stream?mode=${mode}`),
    {
      method: "POST",
      body: formData,
    },
  );

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new Error("无法获取响应流");
  }

  const decoder = new TextDecoder();
  let buffer = "";
  let result: WorldInfoImportCompleteEvent | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) {
        continue;
      }

      try {
        const event = JSON.parse(line.slice(6)) as WorldInfoImportEvent;
        onEvent(event);

        if (event.type === "complete") {
          result = event;
        } else if (event.type === "error") {
          throw new Error(event.message);
        }
      } catch (error) {
        if (error instanceof SyntaxError) {
          console.warn("无法解析 SSE 事件:", line);
        } else {
          throw error;
        }
      }
    }
  }

  return result;
}

// ============================================
// Model API
// ============================================

import type { Model, ModelResponse } from "./model.types";

/**
 * 后端响应字段转换（snake_case -> camelCase）
 */
function transformModel(raw: ModelResponse): Model {
  return {
    id: raw.id,
    name: raw.name,
    remark: raw.remark,
    providerId: raw.provider_id,
    modelId: raw.model_id,
    taskType: raw.task_type,
    tags: raw.tags,
    temperature: raw.temperature,
    topP: raw.top_p,
    topK: raw.top_k,
    minP: raw.min_p,
    topA: raw.top_a,
    frequencyPenalty: raw.frequency_penalty,
    presencePenalty: raw.presence_penalty,
    repetitionPenalty: raw.repetition_penalty,
    maxTokens: raw.max_tokens,
    contextLength: raw.context_length ?? 128000,
    deepseekReasoningEffort: raw.deepseek_reasoning_effort,
    deepseekThinkingType: raw.deepseek_thinking_type,
    dimensions: raw.dimensions,
    isBuiltin: raw.is_builtin ?? false,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

/**
 * 获取所有模型列表
 */
export async function fetchModels(): Promise<Model[]> {
  const response = await apiClient.get<ModelResponse[]>("/models");
  return response.data.map(transformModel);
}

// ============================================
// Prompt Chain API
// ============================================

import type {
  PromptChainVersion,
  PromptEntry,
  VersionWithEntries,
  CreateVersionRequest,
  PromptChainsMetadata,
} from "./prompt-chain.types";

function transformPromptChainVersion(raw: Record<string, unknown>): PromptChainVersion {
  return {
    id: raw.id as string,
    modeName: raw.mode_name as string,
    taskName: raw.task_name as string,
    agentName: raw.agent_name as string | null,
    versionHash: raw.version_hash as string,
    versionNumber: raw.version_number as number,
    parentVersionId: raw.parent_version_id as string | null,
    isActive: raw.is_active as boolean,
    note: raw.note as string | null,
    createdAt: raw.created_at as string,
  };
}

function transformPromptEntry(raw: Record<string, unknown>): PromptEntry {
  return {
    id: raw.id as string,
    uid: raw.uid as string,
    versionId: raw.version_id as string,
    name: raw.name as string,
    role: raw.role as "system" | "user" | "assistant",
    content: raw.content as string,
    orderIndex: raw.order_index as number,
    isEnabled: raw.is_enabled as boolean,
    tokenCount: raw.token_count as number,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

/**
 * 获取版本列表
 */
export async function fetchPromptChainVersions(
  modeName: string,
  taskName: string,
  agentName?: string | null,
  activeOnly: boolean = false,
): Promise<PromptChainVersion[]> {
  const params = {
    ...(agentName ? { agent_name: agentName } : {}),
    active_only: activeOnly,
  };
  const response = await apiClient.get(`/prompt-chains/${modeName}/${taskName}/versions`, {
    params,
  });
  return (response.data as Record<string, unknown>[]).map(transformPromptChainVersion);
}

/**
 * 获取最新版本
 */
export async function fetchLatestPromptChainVersion(
  modeName: string,
  taskName: string,
  agentName?: string | null,
): Promise<VersionWithEntries> {
  const params = agentName ? { agent_name: agentName } : {};
  const response = await apiClient.get(`/prompt-chains/${modeName}/${taskName}/versions/latest`, {
    params,
  });
  return {
    version: transformPromptChainVersion(response.data.version),
    entries: (response.data.entries as Record<string, unknown>[]).map(transformPromptEntry),
  };
}

/**
 * 获取指定版本
 */
export async function fetchPromptChainVersion(
  modeName: string,
  taskName: string,
  versionId: string,
  agentName?: string | null,
): Promise<VersionWithEntries> {
  const params = agentName ? { agent_name: agentName } : {};
  const response = await apiClient.get(
    `/prompt-chains/${modeName}/${taskName}/versions/${versionId}`,
    { params },
  );
  return {
    version: transformPromptChainVersion(response.data.version),
    entries: (response.data.entries as Record<string, unknown>[]).map(transformPromptEntry),
  };
}

/**
 * 创建新版本
 */
export async function createPromptChainVersion(
  modeName: string,
  taskName: string,
  request: CreateVersionRequest,
  agentName?: string | null,
): Promise<VersionWithEntries> {
  const params = agentName ? { agent_name: agentName } : {};

  // 转换为后端期望的格式（snake_case）
  const requestData = {
    parent_version_id: request.parentVersionId,
    entries: request.entries,
    note: request.note,
  };

  const response = await apiClient.post(
    `/prompt-chains/${modeName}/${taskName}/versions`,
    requestData,
    { params },
  );
  return {
    version: transformPromptChainVersion(response.data.version),
    entries: (response.data.entries as Record<string, unknown>[]).map(transformPromptEntry),
  };
}

import type { CompileRequest, CompileResponse } from "./prompt-chain.types";

/**
 * 编译提示词链（解析宏）
 */
export async function compilePromptChain(
  modeName: string,
  taskName: string,
  request: CompileRequest,
  agentName?: string | null,
): Promise<CompileResponse> {
  const params = agentName ? { agent_name: agentName } : {};
  const response = await apiClient.post<CompileResponse>(
    `/prompt-chains/${modeName}/${taskName}/compile`,
    request,
    { params },
  );
  return response.data;
}

/**
 * 获取提示词链元数据
 */
export async function fetchPromptChainsMetadata(): Promise<PromptChainsMetadata> {
  const response = await apiClient.get<PromptChainsMetadata>("/prompt-chains/metadata");
  return response.data;
}

import type { VersionDiff } from "./prompt-chain.types";

/**
 * 获取两个版本之间的差异
 */
export async function fetchVersionDiff(
  modeName: string,
  taskName: string,
  baseVersionId: string,
  compareVersionId: string,
  agentName?: string | null,
): Promise<VersionDiff> {
  const params = agentName ? { agent_name: agentName } : {};
  const response = await apiClient.get(
    `/prompt-chains/${modeName}/${taskName}/versions/${baseVersionId}/diff/${compareVersionId}`,
    { params },
  );

  return {
    baseVersion: transformPromptChainVersion(response.data.base_version),
    compareVersion: transformPromptChainVersion(response.data.compare_version),
    diffs: response.data.diffs.map((diff: Record<string, unknown>) => ({
      entryId: diff.entry_id as string,
      changeType: diff.change_type as string,
      baseEntry: diff.base_entry
        ? transformPromptEntry(diff.base_entry as Record<string, unknown>)
        : null,
      compareEntry: diff.compare_entry
        ? transformPromptEntry(diff.compare_entry as Record<string, unknown>)
        : null,
    })),
  };
}

export async function resetPromptChain(
  modeName: string,
  taskName: string,
  agentName?: string | null,
): Promise<VersionWithEntries> {
  const params = agentName ? { agent_name: agentName } : {};
  const response = await apiClient.post(`/prompt-chains/${modeName}/${taskName}/reset`, null, {
    params,
  });

  return {
    version: transformPromptChainVersion(response.data.version),
    entries: (response.data.entries as Record<string, unknown>[]).map(transformPromptEntry),
  };
}

// ============================================
// Task API
// ============================================

import type { Task, TaskListItem, TaskListResponse, UpdateTaskRequest } from "./task.types";

function normalizeUtcDateString(value: unknown): string {
  if (typeof value !== "string") return "";

  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  if (hasTimezone) return value;

  return `${value}Z`;
}

function transformTaskMessage(raw: Record<string, unknown>): Task["messages"][number] {
  return {
    id: raw.id as string,
    taskId: (raw.task_id ?? raw.taskId) as string | null | undefined,
    role: raw.role as "system" | "user" | "assistant" | "tool",
    agentId: (raw.agent_id ?? raw.agentId) as string | null | undefined,
    content: raw.content as string,
    toolCalls: (raw.tool_calls ?? raw.toolCalls) as Record<string, unknown>[] | undefined,
    toolCallId: (raw.tool_call_id ?? raw.toolCallId) as string | null | undefined,
    metadata: (raw.metadata as Record<string, unknown> | null | undefined) ?? undefined,
    messageType: (raw.message_type ?? raw.messageType) as string | null | undefined,
    messageStatus: (raw.message_status ?? raw.messageStatus) as string | null | undefined,
    displayChannel: (raw.display_channel ?? raw.displayChannel) as string | null | undefined,
    payload: (raw.payload as Record<string, unknown> | null | undefined) ?? undefined,
    correlationId: (raw.correlation_id ?? raw.correlationId) as string | null | undefined,
    createdAt: normalizeUtcDateString(raw.created_at ?? raw.createdAt),
    updatedAt: normalizeUtcDateString(raw.updated_at ?? raw.updatedAt),
  };
}

/**
 * 后端响应字段转换（snake_case -> camelCase）
 */
function transformTask(raw: Record<string, unknown>): Task {
  return {
    id: raw.id as string,
    projectId: raw.project_id as string,
    title: raw.title as string,
    messages: ((raw.messages as Record<string, unknown>[] | undefined) ?? []).map(
      transformTaskMessage,
    ),
    tokenInput: Number(raw.token_input ?? raw.tokenInput ?? 0),
    tokenOutput: Number(raw.token_output ?? raw.tokenOutput ?? 0),
    tokenCache: Number(raw.token_cache ?? raw.tokenCache ?? 0),
    contextInputTokens: Number(raw.context_input_tokens ?? raw.contextInputTokens ?? 0),
    isRunning: raw.is_running === true,
    currentRevisionId: raw.current_revision_id as string | null | undefined,
    currentMessageId: raw.current_message_id as string | null | undefined,
    agentSessionId: raw.agent_session_id as string | null | undefined,
    isFavorited: raw.is_favorited as boolean,
    createdAt: normalizeUtcDateString(raw.created_at),
    updatedAt: normalizeUtcDateString(raw.updated_at),
  };
}

function transformTaskListItem(raw: Record<string, unknown>): TaskListItem {
  return {
    id: raw.id as string,
    projectId: raw.project_id as string,
    title: raw.title as string,
    tokenInput: Number(raw.token_input ?? raw.tokenInput ?? 0),
    tokenOutput: Number(raw.token_output ?? raw.tokenOutput ?? 0),
    tokenCache: Number(raw.token_cache ?? raw.tokenCache ?? 0),
    contextInputTokens: Number(raw.context_input_tokens ?? raw.contextInputTokens ?? 0),
    isRunning: raw.is_running === true,
    isFavorited: raw.is_favorited as boolean,
    createdAt: normalizeUtcDateString(raw.created_at),
    updatedAt: normalizeUtcDateString(raw.updated_at),
  };
}

export type {
  BackgroundEvent,
  BackgroundEventSubscription,
  BackgroundProjectionSubscription,
  BackgroundSnapshot,
} from "./background-socket";
export { subscribeBackgroundEvents, subscribeBackgroundProjection } from "./background-socket";

/**
 * 获取任务详情
 */
export async function fetchTask(taskId: string): Promise<Task> {
  const response = await apiClient.get(`/tasks/${taskId}`);
  return transformTask(response.data);
}

/**
 * 获取项目的任务列表
 */
export async function fetchTasks(
  projectId: string,
  params?: {
    limit?: number;
    offset?: number;
    search?: string;
    favorited?: boolean;
  },
): Promise<TaskListResponse> {
  const response = await apiClient.get(`/projects/${projectId}/tasks`, {
    params: {
      limit: params?.limit,
      offset: params?.offset,
      search: params?.search,
      favorited: params?.favorited,
    },
  });
  return {
    items: (response.data.items as Record<string, unknown>[]).map(transformTaskListItem),
    total: response.data.total,
  };
}

/**
 * 更新任务
 */
export async function updateTask(taskId: string, data: UpdateTaskRequest): Promise<Task> {
  const response = await apiClient.patch(`/tasks/${taskId}`, {
    title: data.title,
    is_favorited: data.is_favorited,
  });
  return transformTask(response.data);
}

/**
 * 删除任务
 */
export async function deleteTask(taskId: string): Promise<void> {
  await apiClient.delete(`/tasks/${taskId}`);
}

/**
 * 删除项目下的所有任务
 */
export async function deleteAllTasks(
  projectId: string,
): Promise<{ deletedCount: number; skippedRunningCount: number }> {
  const response = await apiClient.delete(`/projects/${projectId}/tasks`);
  return {
    deletedCount: Number(response.data.deleted_count ?? 0),
    skippedRunningCount: Number(response.data.skipped_running_count ?? 0),
  };
}

// ============================================
// Agent API
// ============================================

import type {
  ActiveSubagentState,
  AgentCancelPendingMessageResponse,
  AgentCompactionResponse,
  AgentSessionCreateRequest,
  AgentSessionCreateResponse,
  AgentForkResponse,
  AgentPendingMessage,
  AgentSendMessageResponse,
  AgentSessionStateResponse,
  AgentRollbackResponse,
  AgentCancelResponse,
  AgentQuestionAnswerResponse,
  SubagentSessionPayload,
} from "./agent.types";

/**
 * 创建 Agent 会话（仅创建 Task，不运行）
 */
export async function createAgentSession(
  data: AgentSessionCreateRequest,
): Promise<AgentSessionCreateResponse> {
  const response = await apiClient.post("/agent/sessions", data);
  return response.data;
}

export async function fetchAgentSessionState(
  sessionId: string,
): Promise<AgentSessionStateResponse> {
  const response = await apiClient.get(`/agent/sessions/${sessionId}`);
  const data = response.data as Record<string, unknown>;
  return {
    sessionId: String(data.session_id ?? sessionId),
    state:
      data.state && typeof data.state === "object" && !Array.isArray(data.state)
        ? (data.state as Record<string, unknown>)
        : {},
    isRunning: data.is_running === true,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function transformPendingAgentMessage(raw: unknown): AgentPendingMessage | null {
  if (!isRecord(raw)) return null;
  const messageId = String(raw.message_id ?? "");
  const content = String(raw.content ?? "");
  const createdAt = String(raw.created_at ?? "");
  if (!messageId || !content || !createdAt) return null;
  return {
    messageId,
    content,
    createdAt,
  };
}

function transformActiveSubagentState(raw: Record<string, unknown>): ActiveSubagentState {
  const metadata = raw.metadata;
  const metadataRecord = isRecord(metadata) ? metadata : null;
  const pendingApproval = isRecord(raw.pending_approval) ? raw.pending_approval : null;
  return {
    childRunId: String(raw.child_run_id ?? ""),
    childThreadId: String(raw.child_thread_id ?? ""),
    agentKey: raw.agent_key as ActiveSubagentState["agentKey"],
    agentNumber: String(raw.agent_number ?? metadataRecord?.agent_number ?? "") || undefined,
    status: raw.status as ActiveSubagentState["status"],
    queuedMessages: Number(raw.queued_messages ?? 0),
    isActive: raw.is_active === true,
    pendingApproval,
  };
}

function transformSubagentSessionPayload(raw: Record<string, unknown>): SubagentSessionPayload {
  const metadata = raw.metadata;
  const metadataRecord = isRecord(metadata) ? metadata : null;
  const pendingApproval = isRecord(raw.pending_approval) ? raw.pending_approval : null;
  return {
    childRunId: String(raw.child_run_id ?? ""),
    childThreadId: String(raw.child_thread_id ?? ""),
    parentSessionId: String(raw.parent_session_id ?? ""),
    agentKey: raw.agent_key as SubagentSessionPayload["agentKey"],
    agentNumber: String(raw.agent_number ?? metadataRecord?.agent_number ?? "") || undefined,
    status: raw.status as SubagentSessionPayload["status"],
    isActive: raw.is_active === true,
    isRunning: raw.is_running === true,
    tokenInput: Number(raw.token_input ?? 0),
    tokenOutput: Number(raw.token_output ?? 0),
    tokenCache: Number(raw.token_cache ?? 0),
    contextInputTokens: Number(raw.context_input_tokens ?? 0),
    contextLength: Number(raw.context_length ?? 0),
    pendingApproval,
    messages: ((raw.messages as Record<string, unknown>[] | undefined) ?? []).map(
      transformTaskMessage,
    ),
  };
}

export async function fetchActiveSubagents(
  parentSessionId: string,
): Promise<ActiveSubagentState[]> {
  const response = await apiClient.get(`/agent/sessions/${parentSessionId}/subagents`);
  return ((response.data as Record<string, unknown>[] | undefined) ?? []).map(
    transformActiveSubagentState,
  );
}

export async function fetchSubagentSession(childRunId: string): Promise<SubagentSessionPayload> {
  const response = await apiClient.get(`/agent/subagents/${childRunId}`);
  return transformSubagentSessionPayload(response.data as Record<string, unknown>);
}

/**
 * 发送用户消息并运行 Agent 会话。结果通过 Socket.IO 推送。
 */
export async function sendAgentMessage(
  sessionId: string,
  message: string,
): Promise<AgentSendMessageResponse> {
  const response = await apiClient.post(`/agent/sessions/${sessionId}/message`, { message });
  const data = response.data as Record<string, unknown>;
  return {
    success: data.success === true,
    session_id: String(data.session_id ?? sessionId),
    message: String(data.message ?? ""),
    queued: data.queued === true,
    pending_message: transformPendingAgentMessage(data.pending_message),
  };
}

export async function compactAgentSession(sessionId: string): Promise<AgentCompactionResponse> {
  const response = await apiClient.post(`/agent/sessions/${sessionId}/compaction`);
  const data = response.data as Record<string, unknown>;
  return {
    success: data.success === true,
    session_id: String(data.session_id ?? sessionId),
    compaction_id: String(data.compaction_id ?? ""),
    start_seq: Number(data.start_seq ?? 0),
    end_seq: Number(data.end_seq ?? 0),
    source_input_tokens: Number(data.source_input_tokens ?? 0),
    summary_tokens: Number(data.summary_tokens ?? 0),
  };
}

export async function submitAgentQuestionAnswer(
  sessionId: string,
  actionId: string,
  answer: string,
): Promise<AgentQuestionAnswerResponse | void> {
  const response = await apiClient.post(`/agent/sessions/${sessionId}/question-answer`, {
    action_id: actionId,
    answer,
  });
  return response.data;
}

/**
 * 回滚Agent会话到指定revision
 */
export async function rollbackAgentRevision(
  sessionId: string,
  revisionId: string,
): Promise<AgentRollbackResponse> {
  const response = await apiClient.post(`/agent/sessions/${sessionId}/rollback`, {
    revision_id: revisionId,
  });
  return response.data;
}

export async function forkAgentSession(
  sessionId: string,
  sourceRevisionId: string,
  modelId: string,
): Promise<AgentForkResponse> {
  const response = await apiClient.post(`/agent/sessions/${sessionId}/fork`, {
    source_revision_id: sourceRevisionId,
    model_id: modelId,
  });
  return response.data;
}

export async function submitAgentToolApproval(
  sessionId: string,
  approvalId: string,
  approved: boolean,
): Promise<void> {
  await apiClient.post(`/agent/sessions/${sessionId}/tool-approval`, {
    approval_id: approvalId,
    approved,
  });
}

/**
 * 取消Agent会话
 */
export async function cancelAgentSession(sessionId: string): Promise<AgentCancelResponse> {
  const response = await apiClient.post(`/agent/sessions/${sessionId}/cancel`);
  return response.data;
}

export async function cancelPendingAgentMessage(
  sessionId: string,
  messageId: string,
): Promise<AgentCancelPendingMessageResponse> {
  const response = await apiClient.post(`/agent/sessions/${sessionId}/pending-message/cancel`, {
    message_id: messageId,
  });
  return response.data;
}

// ============================================
// Notes API
// ============================================

import type {
  Note,
  NoteListItem,
  NoteCategory,
  NoteCategoryItem,
  NoteTreeResponse,
  NoteCreate,
  NoteUpdate,
  NoteCategoryCreate,
  NoteCategoryUpdate,
  NoteItemMove,
  NoteMoveResult,
} from "./note.types";

function transformNote(raw: Record<string, unknown>): Note {
  return {
    id: raw.id as string,
    projectId: raw.project_id as string,
    categoryId: (raw.category_id as string | null | undefined) ?? null,
    title: raw.title as string,
    content: raw.content as string,
    isLocked: raw.is_locked as boolean,
    isHidden: raw.is_hidden as boolean,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

function transformNoteListItem(raw: Record<string, unknown>): NoteListItem {
  return {
    id: raw.id as string,
    projectId: raw.project_id as string,
    categoryId: (raw.category_id as string | null | undefined) ?? null,
    title: raw.title as string,
    isLocked: raw.is_locked as boolean,
    isHidden: raw.is_hidden as boolean,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

function transformNoteCategory(raw: Record<string, unknown>): NoteCategory {
  return {
    id: raw.id as string,
    projectId: raw.project_id as string,
    parentId: (raw.parent_id as string | null | undefined) ?? null,
    title: raw.title as string,
    createdAt: raw.created_at as string,
    updatedAt: raw.updated_at as string,
  };
}

function transformNoteCategoryItem(raw: Record<string, unknown>): NoteCategoryItem {
  return {
    ...transformNoteCategory(raw),
    categories: ((raw.categories as Record<string, unknown>[]) ?? []).map(
      transformNoteCategoryItem,
    ),
    notes: ((raw.notes as Record<string, unknown>[]) ?? []).map(transformNoteListItem),
  };
}

function transformNoteTree(raw: Record<string, unknown>): NoteTreeResponse {
  return {
    categories: ((raw.categories as Record<string, unknown>[]) ?? []).map(
      transformNoteCategoryItem,
    ),
    rootNotes: ((raw.root_notes as Record<string, unknown>[]) ?? []).map(transformNoteListItem),
    totalNotes: raw.total_notes as number,
  };
}

function transformNoteMoveResult(raw: Record<string, unknown>): NoteMoveResult {
  return {
    kind: raw.kind as "category" | "note",
    note: raw.note ? transformNote(raw.note as Record<string, unknown>) : undefined,
    category: raw.category
      ? transformNoteCategory(raw.category as Record<string, unknown>)
      : undefined,
  };
}

export async function fetchNoteTree(projectId: string): Promise<NoteTreeResponse> {
  const response = await apiClient.get(`/projects/${projectId}/notes`);
  return transformNoteTree(response.data);
}

export async function fetchNote(noteId: string): Promise<Note> {
  const response = await apiClient.get(`/notes/${noteId}`);
  return transformNote(response.data);
}

export async function createNote(projectId: string, data: NoteCreate): Promise<Note> {
  const response = await apiClient.post(`/projects/${projectId}/notes`, {
    category_id: data.categoryId,
    title: data.title,
    content: data.content,
  });
  return transformNote(response.data);
}

export async function updateNote(noteId: string, data: NoteUpdate): Promise<Note> {
  const response = await apiClient.patch(`/notes/${noteId}`, {
    title: data.title,
    content: data.content,
  });
  return transformNote(response.data);
}

export async function deleteNote(noteId: string): Promise<void> {
  await apiClient.delete(`/notes/${noteId}`);
}

export async function toggleNoteLock(noteId: string, isLocked: boolean): Promise<Note> {
  const response = await apiClient.patch(`/notes/${noteId}/lock`, {
    is_locked: isLocked,
  });
  return transformNote(response.data);
}

export async function toggleNoteHidden(noteId: string, isHidden: boolean): Promise<Note> {
  const response = await apiClient.patch(`/notes/${noteId}/hidden`, {
    is_hidden: isHidden,
  });
  return transformNote(response.data);
}

export async function createNoteCategory(
  projectId: string,
  data: NoteCategoryCreate,
): Promise<NoteCategory> {
  const response = await apiClient.post(`/projects/${projectId}/note-categories`, {
    parent_id: data.parentId,
    title: data.title,
  });
  return transformNoteCategory(response.data);
}

export async function updateNoteCategory(
  categoryId: string,
  data: NoteCategoryUpdate,
): Promise<NoteCategory> {
  const response = await apiClient.patch(`/note-categories/${categoryId}`, {
    title: data.title,
  });
  return transformNoteCategory(response.data);
}

export async function deleteNoteCategory(categoryId: string): Promise<void> {
  await apiClient.delete(`/note-categories/${categoryId}`);
}

export async function moveNoteItem(data: NoteItemMove): Promise<NoteMoveResult> {
  const response = await apiClient.post("/note-items/move", {
    kind: data.kind,
    item_id: data.itemId,
    target_category_id: data.targetCategoryId,
  });
  return transformNoteMoveResult(response.data);
}

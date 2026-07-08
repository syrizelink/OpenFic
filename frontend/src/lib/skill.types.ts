import type { SkillReferenceDoc } from "./skill-reference-doc.types";

export interface Skill {
  id: string;
  name: string;
  summary: string;
  content: string;
  isEnabled: boolean;
  isComplete: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface SkillCreate {
  name: string;
  summary: string;
  content: string;
  isEnabled?: boolean;
}

export interface SkillUpdate {
  name?: string;
  summary?: string;
  content?: string;
  isEnabled?: boolean;
}

export interface SkillListResponse {
  items: Skill[];
  total: number;
  page: number;
  pageSize: number;
}

export interface SkillListParams {
  page?: number;
  pageSize?: number;
}

export interface SkillImportResult {
  skill: Skill;
  referenceDocs: SkillReferenceDoc[];
  isRecognized: boolean;
}
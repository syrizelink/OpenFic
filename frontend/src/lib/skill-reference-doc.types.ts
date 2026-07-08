export interface SkillReferenceDoc {
  id: string;
  title: string;
  content: string;
  tokens: number;
  createdAt: string;
  updatedAt: string;
}

export interface SkillReferenceDocCreate {
  title: string;
  content: string;
}

export interface SkillReferenceDocUpdate {
  title?: string;
  content?: string;
}

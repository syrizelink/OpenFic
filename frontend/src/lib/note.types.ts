export interface Note {
  id: string;
  projectId: string;
  categoryId: string | null;
  title: string;
  content: string;
  isLocked: boolean;
  isHidden: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface NoteListItem {
  id: string;
  projectId: string;
  categoryId: string | null;
  title: string;
  isLocked: boolean;
  isHidden: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface NoteCategory {
  id: string;
  projectId: string;
  parentId: string | null;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export interface NoteCategoryItem extends NoteCategory {
  categories: NoteCategoryItem[];
  notes: NoteListItem[];
}

export interface NoteTreeResponse {
  categories: NoteCategoryItem[];
  rootNotes: NoteListItem[];
  totalNotes: number;
}

export interface NoteCreate {
  categoryId?: string | null;
  title: string;
  content?: string;
}

export interface NoteUpdate {
  title?: string;
  content?: string;
}

export interface NoteCategoryCreate {
  parentId?: string | null;
  title: string;
}

export interface NoteCategoryUpdate {
  title?: string;
}

export interface NoteItemMove {
  kind: "category" | "note";
  itemId: string;
  targetCategoryId?: string | null;
}

export interface NoteMoveResult {
  kind: "category" | "note";
  note?: Note;
  category?: NoteCategory;
}

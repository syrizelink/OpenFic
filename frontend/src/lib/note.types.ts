export interface Note {
  id: string;
  projectId: string;
  categoryId: string | null;
  title: string;
  content: string;
  isLocked: boolean;
  isHidden: boolean;
  orderIndex: number;
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
  orderIndex: number;
  createdAt: string;
  updatedAt: string;
}

export interface NoteCategory {
  id: string;
  projectId: string;
  parentId: string | null;
  title: string;
  orderIndex: number;
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

export type NoteItemKind = "category" | "note";
export interface NoteSiblingRef {
  kind: NoteItemKind;
  itemId: string;
}
export interface NoteItemReorder extends NoteSiblingRef {
  targetCategoryId: string | null;
  orderedSiblings: NoteSiblingRef[];
}

export type NoteConflictStrategy = "rename" | "overwrite" | "skip";
export interface ProjectNoteImportRequest {
  sourceProjectId: string;
  selectedCategoryIds: string[];
  selectedNoteIds: string[];
  defaultConflictStrategy: NoteConflictStrategy;
  conflictOverrides: Record<string, NoteConflictStrategy>;
}
export interface ProjectNoteImportAction {
  sourceNoteId: string;
  sourcePath: string;
  targetTitle: string;
  action: "create" | "rename" | "overwrite" | "skip";
}
export interface ProjectNoteImportPreview {
  categories: NoteCategoryItem[];
  rootNotes: NoteListItem[];
  actions: ProjectNoteImportAction[];
  createCategoryCount: number;
  mergeCategoryCount: number;
  createNoteCount: number;
  overwriteNoteCount: number;
  skipNoteCount: number;
}
export interface ProjectNoteImportResult {
  createdCategoryCount: number;
  mergedCategoryCount: number;
  createdNoteCount: number;
  renamedNoteCount: number;
  overwrittenNoteCount: number;
  skippedNoteCount: number;
}

export interface NoteImportPreview {
  fileType: "md" | "zip";
  noteCount: number;
  categoryCount: number;
  ignoredFileCount: number;
}

export interface NoteImportResult {
  fileType: "md" | "zip";
  importedNoteCount: number;
  importedCategoryCount: number;
  ignoredFileCount: number;
}

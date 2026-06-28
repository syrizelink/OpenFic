import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "@/components";
import { useTranslation } from "react-i18next";
import {
  fetchNoteTree,
  fetchNote,
  createNote,
  updateNote,
  deleteNote,
  toggleNoteLock,
  toggleNoteHidden,
  createNoteCategory,
  updateNoteCategory,
  deleteNoteCategory,
  moveNoteItem,
} from "@/lib/api-client";
import type {
  Note,
  NoteCreate,
  NoteListItem,
  NoteUpdate,
  NoteCategoryCreate,
  NoteCategoryUpdate,
  NoteItemMove,
  NoteTreeResponse,
  NoteCategoryItem,
} from "@/lib/note.types";

function cloneCategoryItem(cat: NoteCategoryItem): NoteCategoryItem {
  return {
    ...cat,
    categories: cat.categories.map(cloneCategoryItem),
    notes: cat.notes.map((n) => ({ ...n })),
  };
}

function cloneTree(tree: NoteTreeResponse): NoteTreeResponse {
  return {
    ...tree,
    categories: tree.categories.map(cloneCategoryItem),
    rootNotes: tree.rootNotes.map((n) => ({ ...n })),
  };
}

type NoteMutator = (note: NoteListItem) => NoteListItem;

function applyToNote(tree: NoteTreeResponse, noteId: string, mutator: NoteMutator): NoteTreeResponse {
  const next = cloneTree(tree);

  const walkCategories = (cats: NoteCategoryItem[]): boolean => {
    for (const cat of cats) {
      const idx = cat.notes.findIndex((n) => n.id === noteId);
      if (idx !== -1) {
        cat.notes[idx] = mutator(cat.notes[idx]!);
        return true;
      }
      if (walkCategories(cat.categories)) return true;
    }
    return false;
  };

  if (walkCategories(next.categories)) return next;

  const rootIdx = next.rootNotes.findIndex((n) => n.id === noteId);
  if (rootIdx !== -1) {
    next.rootNotes[rootIdx] = mutator(next.rootNotes[rootIdx]!);
    return next;
  }

  return next;
}

type CategoryMutator = (category: NoteCategoryItem) => NoteCategoryItem;

function applyToCategory(tree: NoteTreeResponse, categoryId: string, mutator: CategoryMutator): NoteTreeResponse {
  const next = cloneTree(tree);

  const walk = (cats: NoteCategoryItem[]): boolean => {
    for (const cat of cats) {
      if (cat.id === categoryId) {
        const idx = cats.indexOf(cat);
        cats[idx] = mutator(cat);
        return true;
      }
      if (walk(cat.categories)) return true;
    }
    return false;
  };

  walk(next.categories);
  return next;
}

function removeNoteFromTree(tree: NoteTreeResponse, noteId: string): NoteTreeResponse {
  const next = cloneTree(tree);

  const walkCategories = (cats: NoteCategoryItem[]): boolean => {
    for (const cat of cats) {
      const idx = cat.notes.findIndex((n) => n.id === noteId);
      if (idx !== -1) {
        cat.notes.splice(idx, 1);
        return true;
      }
      if (walkCategories(cat.categories)) return true;
    }
    return false;
  };

  if (walkCategories(next.categories)) return next;

  const rootIdx = next.rootNotes.findIndex((n) => n.id === noteId);
  if (rootIdx !== -1) {
    next.rootNotes.splice(rootIdx, 1);
    next.totalNotes = Math.max(0, next.totalNotes - 1);
  }
  return next;
}

function removeCategoryFromTree(tree: NoteTreeResponse, categoryId: string): NoteTreeResponse {
  const next = cloneTree(tree);

  const walk = (cats: NoteCategoryItem[]): boolean => {
    const idx = cats.findIndex((c) => c.id === categoryId);
    if (idx !== -1) {
      cats.splice(idx, 1);
      return true;
    }
    return cats.some((cat) => walk(cat.categories));
  };

  walk(next.categories);
  return next;
}

function findNoteInTree(tree: NoteTreeResponse, noteId: string): NoteListItem | undefined {
  const walk = (cats: NoteCategoryItem[]): NoteListItem | undefined => {
    for (const cat of cats) {
      const found = cat.notes.find((n) => n.id === noteId);
      if (found) return found;
      const nested = walk(cat.categories);
      if (nested) return nested;
    }
    return undefined;
  };
  return walk(tree.categories) ?? tree.rootNotes.find((n) => n.id === noteId);
}

function findCategoryInTree(tree: NoteTreeResponse, categoryId: string): NoteCategoryItem | undefined {
  const walk = (cats: NoteCategoryItem[]): NoteCategoryItem | undefined => {
    for (const cat of cats) {
      if (cat.id === categoryId) return cat;
      const nested = walk(cat.categories);
      if (nested) return nested;
    }
    return undefined;
  };
  return walk(tree.categories);
}

function moveNoteInTree(tree: NoteTreeResponse, noteId: string, targetCategoryId: string | null): NoteTreeResponse {
  const source = findNoteInTree(tree, noteId);
  if (!source) return tree;

  let next = removeNoteFromTree(tree, noteId);
  next = cloneTree(next);
  const movedNote: NoteListItem = { ...source, categoryId: targetCategoryId };

  if (targetCategoryId === null) {
    next.rootNotes.push(movedNote);
    next.totalNotes = next.rootNotes.length + countCategoryNotes(next.categories);
    return next;
  }

  const insertInto = (cats: NoteCategoryItem[]): boolean => {
    for (const cat of cats) {
      if (cat.id === targetCategoryId) {
        cat.notes.push(movedNote);
        return true;
      }
      if (insertInto(cat.categories)) return true;
    }
    return false;
  };
  insertInto(next.categories);
  return next;
}

function moveCategoryInTree(tree: NoteTreeResponse, categoryId: string, targetCategoryId: string | null): NoteTreeResponse {
  const source = findCategoryInTree(tree, categoryId);
  if (!source) return tree;

  const next = removeCategoryFromTree(tree, categoryId);
  const moved: NoteCategoryItem = cloneCategoryItem({ ...source, parentId: targetCategoryId });

  if (targetCategoryId === null) {
    next.categories.push(moved);
    return next;
  }

  const insertInto = (cats: NoteCategoryItem[]): boolean => {
    for (const cat of cats) {
      if (cat.id === targetCategoryId) {
        cat.categories.push(moved);
        return true;
      }
      if (insertInto(cat.categories)) return true;
    }
    return false;
  };
  insertInto(next.categories);
  return next;
}

function countCategoryNotes(cats: NoteCategoryItem[]): number {
  return cats.reduce(
    (sum, cat) => sum + cat.notes.length + countCategoryNotes(cat.categories),
    0
  );
}

export function useNoteTree(projectId: string) {
  return useQuery({
    queryKey: ["note-tree", projectId],
    queryFn: () => fetchNoteTree(projectId),
    enabled: !!projectId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useNote(noteId: string | null) {
  return useQuery({
    queryKey: ["note", noteId],
    queryFn: () => fetchNote(noteId!),
    enabled: !!noteId,
    staleTime: 0,
  });
}

export function useCreateNote(projectId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  return useMutation({
    mutationFn: (data: NoteCreate) => createNote(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["note-tree", projectId] });
      toast.success(t("writing.noteCreated"));
    },
    onError: () => {
      toast.error(t("writing.noteCreateFailed"));
    },
  });
}

export function useUpdateNote(projectId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  return useMutation({
    mutationFn: ({
      noteId,
      data,
    }: {
      noteId: string;
      data: NoteUpdate;
    }) => updateNote(noteId, data),
    onMutate: async ({ noteId, data }) => {
      await queryClient.cancelQueries({ queryKey: ["note-tree", projectId] });
      const previous = queryClient.getQueryData<NoteTreeResponse>(["note-tree", projectId]);
      if (previous && data.title !== undefined) {
        queryClient.setQueryData<NoteTreeResponse>(["note-tree", projectId], (tree) => {
          if (!tree) return tree;
          return applyToNote(tree, noteId, (note) => ({ ...note, title: data.title! }));
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["note-tree", projectId], context.previous);
      }
      toast.error(t("writing.noteRenameFailed"));
    },
    onSuccess: (updatedNote) => {
      queryClient.setQueryData(["note", updatedNote.id], updatedNote);
      queryClient.invalidateQueries({ queryKey: ["note-tree", updatedNote.projectId] });
    },
  });
}

export function useDeleteNote(projectId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  return useMutation({
    mutationFn: (noteId: string) => deleteNote(noteId),
    onMutate: async (noteId) => {
      await queryClient.cancelQueries({ queryKey: ["note-tree", projectId] });
      const previous = queryClient.getQueryData<NoteTreeResponse>(["note-tree", projectId]);
      if (previous) {
        queryClient.setQueryData<NoteTreeResponse>(["note-tree", projectId], (tree) => {
          if (!tree) return tree;
          return removeNoteFromTree(tree, noteId);
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["note-tree", projectId], context.previous);
      }
      toast.error(t("writing.deleteNoteFailed"));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["note-tree", projectId] });
      toast.success(t("writing.deleteNoteSuccess"));
    },
  });
}

export function useToggleNoteLock(projectId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  return useMutation({
    mutationFn: ({
      noteId,
      isLocked,
    }: {
      noteId: string;
      isLocked: boolean;
    }) => toggleNoteLock(noteId, isLocked),
    onMutate: async ({ noteId, isLocked }) => {
      await queryClient.cancelQueries({ queryKey: ["note-tree", projectId] });
      const previous = queryClient.getQueryData<NoteTreeResponse>(["note-tree", projectId]);
      if (previous) {
        queryClient.setQueryData<NoteTreeResponse>(["note-tree", projectId], (tree) => {
          if (!tree) return tree;
          return applyToNote(tree, noteId, (note) => ({ ...note, isLocked }));
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["note-tree", projectId], context.previous);
      }
      toast.error(t("writing.noteLockToggleFailed"));
    },
    onSuccess: (updatedNote) => {
      queryClient.setQueryData(["note", updatedNote.id], updatedNote);
      queryClient.invalidateQueries({ queryKey: ["note-tree", updatedNote.projectId] });
      toast.success(updatedNote.isLocked ? t("writing.noteLockedToast") : t("writing.noteUnlockedToast"));
    },
  });
}

export function useToggleNoteHidden(projectId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  return useMutation({
    mutationFn: ({
      noteId,
      isHidden,
    }: {
      noteId: string;
      isHidden: boolean;
    }) => toggleNoteHidden(noteId, isHidden),
    onMutate: async ({ noteId, isHidden }) => {
      await queryClient.cancelQueries({ queryKey: ["note-tree", projectId] });
      const previous = queryClient.getQueryData<NoteTreeResponse>(["note-tree", projectId]);
      if (previous) {
        queryClient.setQueryData<NoteTreeResponse>(["note-tree", projectId], (tree) => {
          if (!tree) return tree;
          return applyToNote(tree, noteId, (note) => ({ ...note, isHidden }));
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["note-tree", projectId], context.previous);
      }
      toast.error(t("writing.noteHiddenToggleFailed"));
    },
    onSuccess: (updatedNote) => {
      queryClient.setQueryData(["note", updatedNote.id], updatedNote);
      queryClient.invalidateQueries({ queryKey: ["note-tree", updatedNote.projectId] });
      toast.success(updatedNote.isHidden ? t("writing.noteHiddenOn") : t("writing.noteHiddenOff"));
    },
  });
}

export function useCreateNoteCategory(projectId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  return useMutation({
    mutationFn: (data: NoteCategoryCreate) => createNoteCategory(projectId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["note-tree", projectId] });
      toast.success(t("writing.categoryCreated"));
    },
    onError: () => {
      toast.error(t("writing.categoryCreateFailed"));
    },
  });
}

export function useUpdateNoteCategory(projectId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  return useMutation({
    mutationFn: ({
      categoryId,
      data,
    }: {
      categoryId: string;
      data: NoteCategoryUpdate;
    }) => updateNoteCategory(categoryId, data),
    onMutate: async ({ categoryId, data }) => {
      await queryClient.cancelQueries({ queryKey: ["note-tree", projectId] });
      const previous = queryClient.getQueryData<NoteTreeResponse>(["note-tree", projectId]);
      if (previous && data.title !== undefined) {
        queryClient.setQueryData<NoteTreeResponse>(["note-tree", projectId], (tree) => {
          if (!tree) return tree;
          return applyToCategory(tree, categoryId, (cat) => ({ ...cat, title: data.title! }));
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["note-tree", projectId], context.previous);
      }
      toast.error(t("writing.categoryRenameFailed"));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["note-tree", projectId] });
      toast.success(t("writing.categoryRenamed"));
    },
  });
}

export function useDeleteNoteCategory(projectId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  return useMutation({
    mutationFn: (categoryId: string) => deleteNoteCategory(categoryId),
    onMutate: async (categoryId) => {
      await queryClient.cancelQueries({ queryKey: ["note-tree", projectId] });
      const previous = queryClient.getQueryData<NoteTreeResponse>(["note-tree", projectId]);
      if (previous) {
        queryClient.setQueryData<NoteTreeResponse>(["note-tree", projectId], (tree) => {
          if (!tree) return tree;
          return removeCategoryFromTree(tree, categoryId);
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["note-tree", projectId], context.previous);
      }
      toast.error(t("writing.deleteCategoryFailed"));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["note-tree", projectId] });
      toast.success(t("writing.deleteNoteSuccess"));
    },
  });
}

export function useMoveNoteItem(projectId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  return useMutation({
    mutationFn: (data: NoteItemMove) => moveNoteItem(data),
    onMutate: async ({ kind, itemId, targetCategoryId }) => {
      await queryClient.cancelQueries({ queryKey: ["note-tree", projectId] });
      const previous = queryClient.getQueryData<NoteTreeResponse>(["note-tree", projectId]);
      if (previous) {
        queryClient.setQueryData<NoteTreeResponse>(["note-tree", projectId], (tree) => {
          if (!tree) return tree;
          if (kind === "note") {
            return moveNoteInTree(tree, itemId, targetCategoryId ?? null);
          }
          return moveCategoryInTree(tree, itemId, targetCategoryId ?? null);
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["note-tree", projectId], context.previous);
      }
      toast.error(t("writing.noteMoveFailed"));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["note-tree", projectId] });
    },
  });
}

export function useDuplicateNote(projectId: string) {
  const queryClient = useQueryClient();
  const { t } = useTranslation();

  return useMutation({
    mutationFn: async (noteId: string): Promise<Note> => {
      const original = await fetchNote(noteId);
      return createNote(projectId, {
        categoryId: original.categoryId,
        title: `${original.title}-${t("writing.duplicateSuffix")}`,
        content: original.content,
      });
    },
    onSuccess: (newNote) => {
      queryClient.invalidateQueries({ queryKey: ["note-tree", projectId] });
      toast.success(t("writing.noteDuplicated"));
      return newNote;
    },
    onError: () => {
      toast.error(t("writing.noteDuplicateFailed"));
    },
  });
}

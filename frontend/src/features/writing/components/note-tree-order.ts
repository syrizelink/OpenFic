import type {
  NoteCategoryItem,
  NoteItemKind,
  NoteListItem,
  NoteSiblingRef,
  NoteTreeResponse,
} from "@/lib/note.types";

export type MixedNoteTreeItem =
  | { kind: "category"; item: NoteCategoryItem }
  | { kind: "note"; item: NoteListItem };

export function getMixedChildren(
  categories: NoteCategoryItem[],
  notes: NoteListItem[],
): MixedNoteTreeItem[] {
  return [
    ...categories.map((item) => ({ kind: "category" as const, item })),
    ...notes.map((item) => ({ kind: "note" as const, item })),
  ].sort(
    (left, right) =>
      left.item.orderIndex - right.item.orderIndex ||
      left.kind.localeCompare(right.kind) ||
      left.item.id.localeCompare(right.item.id),
  );
}

export function getSiblingRefs(tree: NoteTreeResponse, parentId: string | null): NoteSiblingRef[] {
  if (parentId === null) {
    return getMixedChildren(tree.categories, tree.rootNotes).map(toRef);
  }
  const category = findCategory(tree.categories, parentId);
  return category ? getMixedChildren(category.categories, category.notes).map(toRef) : [];
}

export function findItemParent(
  tree: NoteTreeResponse,
  kind: NoteItemKind,
  itemId: string,
): string | null | undefined {
  if (kind === "category") return findCategory(tree.categories, itemId)?.parentId;
  if (tree.rootNotes.some((item) => item.id === itemId)) return null;
  return findNoteParent(tree.categories, itemId);
}

function toRef(value: MixedNoteTreeItem): NoteSiblingRef {
  return { kind: value.kind, itemId: value.item.id };
}

function findCategory(categories: NoteCategoryItem[], id: string): NoteCategoryItem | undefined {
  for (const category of categories) {
    if (category.id === id) return category;
    const nested = findCategory(category.categories, id);
    if (nested) return nested;
  }
}

function findNoteParent(categories: NoteCategoryItem[], noteId: string): string | null | undefined {
  for (const category of categories) {
    if (category.notes.some((item) => item.id === noteId)) return category.id;
    const nested = findNoteParent(category.categories, noteId);
    if (nested !== undefined) return nested;
  }
}

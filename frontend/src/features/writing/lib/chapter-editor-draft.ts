export interface ChapterEditorDraft {
  title: string;
  content: string;
}

export function createChapterEditorDraft(input: {
  title: string;
  content?: string | null;
}): ChapterEditorDraft {
  return {
    title: input.title,
    content: input.content ?? "",
  };
}

export function isChapterEditorDraftDirty(
  saved: ChapterEditorDraft,
  current: ChapterEditorDraft
): boolean {
  return saved.title !== current.title || saved.content !== current.content;
}

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

export interface EditorDraft {
  title: string;
  content: string;
}

interface DraftSnapshot {
  draft: EditorDraft;
  hasChanges: boolean;
  isSaving: boolean;
  isBlocked: boolean;
}

interface DraftRecord {
  key: string;
  savedDraft: EditorDraft;
  snapshot: DraftSnapshot;
  listeners: Set<() => void>;
  completion?: Promise<void>;
  pendingRemote?: EditorDraft;
}

interface EditorDraftOptions {
  key: string;
  value: EditorDraft;
  isLocked?: boolean;
  canSave?: () => boolean;
  onSave: (draft: EditorDraft) => Promise<EditorDraft | null>;
  onError?: () => void;
}

const drafts = new Map<string, DraftRecord>();
const AUTO_SAVE_DELAY = 1500;

function normalizeDraft(draft: EditorDraft): EditorDraft {
  return { title: draft.title, content: draft.content.replace(/\r\n?/g, "\n") };
}

function hasSameContent(a: EditorDraft, b: EditorDraft): boolean {
  return a.title.trim() === b.title.trim() && a.content === b.content;
}

function clearSavedDraft(record: DraftRecord): void {
  if (
    record.listeners.size === 0 &&
    !record.snapshot.hasChanges &&
    !record.snapshot.isSaving &&
    drafts.get(record.key) === record
  ) {
    drafts.delete(record.key);
  }
}

function publish(
  record: DraftRecord,
  draft: EditorDraft,
  isSaving: boolean,
  isBlocked: boolean,
): void {
  record.snapshot = {
    draft,
    hasChanges: !hasSameContent(draft, record.savedDraft),
    isSaving,
    isBlocked,
  };
  record.listeners.forEach((listener) => listener());
}

function saveDraft(
  record: DraftRecord,
  onSave: EditorDraftOptions["onSave"],
  onError: EditorDraftOptions["onError"],
  canSave: () => boolean,
): Promise<void> {
  if (record.completion) return record.completion;
  if (!record.snapshot.hasChanges || !canSave()) return Promise.resolve();

  const submittedDraft = record.snapshot.draft;
  publish(record, submittedDraft, true, false);
  const completion = Promise.resolve().then(async () => {
    let didSave = false;
    try {
      const savedDraft = await onSave(submittedDraft);
      if (!savedDraft) {
        publish(record, record.snapshot.draft, true, true);
        return;
      }
      record.savedDraft = normalizeDraft(savedDraft);
      record.pendingRemote = undefined;
      const draft = hasSameContent(record.snapshot.draft, submittedDraft)
        ? record.savedDraft
        : record.snapshot.draft;
      publish(record, draft, true, false);
      didSave = true;
    } catch {
      publish(record, record.snapshot.draft, true, true);
      onError?.();
    } finally {
      record.completion = undefined;
      publish(record, record.snapshot.draft, false, record.snapshot.isBlocked);
      clearSavedDraft(record);
    }

    // Finish edits made during the request even if the editor was unmounted.
    if (didSave && record.snapshot.hasChanges && record.listeners.size === 0) {
      await saveDraft(record, onSave, onError, canSave);
    }
  });
  record.completion = completion;
  return completion;
}

// Callers mount a keyed editor for each entity; unsaved records survive that mount.
export function useEditorDraft({
  key,
  value,
  isLocked = false,
  canSave,
  onSave,
  onError,
}: EditorDraftOptions) {
  const [record] = useState(() => {
    const existing = drafts.get(key);
    if (existing) return existing;
    const draft = normalizeDraft(value);
    const created: DraftRecord = {
      key,
      savedDraft: draft,
      snapshot: { draft, hasChanges: false, isSaving: false, isBlocked: false },
      listeners: new Set(),
    };
    drafts.set(key, created);
    return created;
  });
  const optionsRef = useRef({ onSave, onError, isLocked, canSave });
  const remoteValueRef = useRef<EditorDraft | null>(null);
  optionsRef.current = { onSave, onError, isLocked, canSave };
  const subscribe = useCallback(
    (listener: () => void) => {
      drafts.set(record.key, record);
      record.listeners.add(listener);
      return () => {
        record.listeners.delete(listener);
        clearSavedDraft(record);
      };
    },
    [record],
  );
  const getSnapshot = useCallback(() => record.snapshot, [record]);
  const snapshot = useSyncExternalStore(subscribe, getSnapshot);

  const handleSave = useCallback(() => {
    const options = optionsRef.current;
    return saveDraft(
      record,
      options.onSave,
      options.onError,
      () => optionsRef.current.canSave?.() ?? !optionsRef.current.isLocked,
    );
  }, [record]);

  const handleTitleChange = useCallback(
    (title: string) => {
      publish(record, { ...record.snapshot.draft, title }, record.snapshot.isSaving, false);
    },
    [record],
  );
  const handleContentChange = useCallback(
    (content: string) => {
      publish(record, { ...record.snapshot.draft, content }, record.snapshot.isSaving, false);
    },
    [record],
  );

  useEffect(() => {
    const draft = normalizeDraft({ title: value.title, content: value.content });
    if (
      remoteValueRef.current?.title === draft.title &&
      remoteValueRef.current?.content === draft.content
    )
      return;
    remoteValueRef.current = draft;
    if (record.snapshot.hasChanges || record.snapshot.isSaving) {
      record.pendingRemote = hasSameContent(draft, record.savedDraft) ? undefined : draft;
      return;
    }
    record.pendingRemote = undefined;
    record.savedDraft = draft;
    if (
      draft.title !== record.snapshot.draft.title ||
      draft.content !== record.snapshot.draft.content
    ) {
      publish(record, draft, false, false);
    }
  }, [record, value.title, value.content]);

  useEffect(() => {
    if (snapshot.hasChanges || snapshot.isSaving || !record.pendingRemote) return;
    const draft = record.pendingRemote;
    record.pendingRemote = undefined;
    record.savedDraft = draft;
    publish(record, draft, false, false);
  }, [record, snapshot.hasChanges, snapshot.isSaving]);

  useEffect(() => {
    if (!snapshot.hasChanges || snapshot.isSaving || snapshot.isBlocked || isLocked) return;
    const timer = setTimeout(() => void handleSave(), AUTO_SAVE_DELAY);
    return () => clearTimeout(timer);
  }, [snapshot, isLocked, handleSave]);

  useEffect(
    () => () => {
      if (record.snapshot.hasChanges && !record.snapshot.isBlocked) void handleSave();
    },
    [record, handleSave],
  );

  return {
    ...snapshot.draft,
    hasChanges: snapshot.hasChanges,
    isSaving: snapshot.isSaving,
    isSaveBlocked: snapshot.isBlocked,
    handleTitleChange,
    handleContentChange,
    handleSave,
  };
}

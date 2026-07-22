import { useCallback } from "react";

import {
  deleteWritingWorkingCopy,
  deleteWritingWorkingCopyIfMatches,
  saveWritingWorkingCopy,
  type WritingWorkingCopyType,
} from "@/lib/local-db";

export interface WritingDraft {
  title: string;
  content: string;
}

export interface WritingWorkingCopyController {
  persistWorkingCopy: (draft: WritingDraft, baseUpdatedAt: string, updatedAt: Date) => void;
  clearWorkingCopy: (draft: WritingDraft, updatedAt: Date) => Promise<void>;
}

interface UseWritingWorkingCopyOptions {
  type: WritingWorkingCopyType;
  entityId: string;
}

export function useWritingWorkingCopy({ type, entityId }: UseWritingWorkingCopyOptions) {
  const persistWorkingCopy = useCallback(
    (draft: WritingDraft, baseUpdatedAt: string, updatedAt: Date) => {
      void saveWritingWorkingCopy({
        entityId,
        type,
        title: draft.title,
        content: draft.content,
        baseUpdatedAt,
        updatedAt,
      });
    },
    [entityId, type],
  );

  const clearWorkingCopy = useCallback(
    (draft: WritingDraft, updatedAt: Date) =>
      deleteWritingWorkingCopyIfMatches(type, entityId, draft, updatedAt),
    [entityId, type],
  );

  const discardWorkingCopy = useCallback(
    () => deleteWritingWorkingCopy(type, entityId),
    [entityId, type],
  );

  return {
    persistWorkingCopy,
    clearWorkingCopy,
    discardWorkingCopy,
  };
}

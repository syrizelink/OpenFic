import { useQuery } from "@tanstack/react-query";

import {
  deleteWritingWorkingCopyIfUpdatedAt,
  getWritingWorkingCopy,
  type WritingWorkingCopyType,
} from "@/lib/local-db";

import { resolveWritingWorkingCopy } from "../lib/writing-working-copy";
import type { WritingDraft } from "./use-writing-working-copy";

export async function loadWritingEditorEntity<TEntity extends WritingEditorEntity>(
  type: WritingWorkingCopyType,
  entityId: string,
  fetchEntity: (entityId: string) => Promise<TEntity>,
): Promise<WritingEditorEntityResult<TEntity>> {
  const [entity, workingCopy] = await Promise.all([
    fetchEntity(entityId),
    getWritingWorkingCopy(type, entityId),
  ]);
  const resolved = resolveWritingWorkingCopy(entity, workingCopy);

  if (resolved.shouldDelete) {
    await deleteWritingWorkingCopyIfUpdatedAt(type, entity.id, workingCopy!.updatedAt);
  }

  return {
    entity,
    draft: resolved.draft,
    draftUpdatedAt:
      !resolved.shouldDelete && workingCopy !== null
        ? workingCopy.updatedAt
        : new Date(entity.updatedAt),
    isWorkingCopyRecovered: !resolved.shouldDelete && workingCopy !== null,
  };
}

interface WritingEditorEntity {
  id: string;
  title: string;
  content: string;
  updatedAt: string;
}

interface WritingEditorEntityResult<TEntity> {
  entity: TEntity;
  draft: WritingDraft;
  draftUpdatedAt: Date;
  isWorkingCopyRecovered: boolean;
}

interface UseWritingEditorEntityOptions<TEntity extends WritingEditorEntity> {
  type: WritingWorkingCopyType;
  entityId: string | null;
  fetchEntity: (entityId: string) => Promise<TEntity>;
}

export function useWritingEditorEntity<TEntity extends WritingEditorEntity>({
  type,
  entityId,
  fetchEntity,
}: UseWritingEditorEntityOptions<TEntity>) {
  return useQuery<WritingEditorEntityResult<TEntity>>({
    queryKey: ["writing-editor", type, entityId],
    queryFn: () => loadWritingEditorEntity(type, entityId!, fetchEntity),
    enabled: !!entityId,
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: "always",
  });
}

/**
 * usePromptChain Hook
 *
 * 管理提示词链的状态：版本、条目、Working Copy
 * 增强版：添加错误处理和健壮性
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect, useCallback, useRef } from "react";

import {
  fetchPromptChainVersions,
  fetchLatestPromptChainVersion,
  fetchPromptChainVersion,
  createPromptChainVersion,
} from "@/lib/api-client";
import {
  getPromptChainWorkingCopy,
  savePromptChainWorkingCopy,
  deletePromptChainWorkingCopy,
} from "@/lib/local-db";
import type { PromptEntry, PromptEntryData } from "@/lib/prompt-chain.types";
import { countTokens } from "@/lib/tiktoken-utils";

function getEntryTokenCount(content: string, tokenCount: number): number {
  if (!content.trim()) return 0;
  return countTokens(content) || tokenCount;
}

function mapPromptEntry(entry: PromptEntry): PromptEntryData {
  return {
    id: entry.id,
    uid: entry.uid,
    name: entry.name,
    role: entry.role,
    content: entry.content,
    order_index: entry.orderIndex,
    is_enabled: entry.isEnabled,
    token_count: getEntryTokenCount(entry.content, entry.tokenCount),
  };
}

function normalizePromptEntryData(entry: PromptEntryData): PromptEntryData {
  return {
    ...entry,
    token_count: getEntryTokenCount(entry.content, entry.token_count),
  };
}

export function usePromptChain(promptId: string) {
  const queryClient = useQueryClient();
  const [currentVersionId, setCurrentVersionId] = useState<string | null>(null);
  const [entries, setEntries] = useState<PromptEntryData[]>([]);
  const [baseEntries, setBaseEntries] = useState<PromptEntryData[]>([]);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const workingCopySaveRef = useRef(Promise.resolve());
  const [error, setError] = useState<Error | null>(null);

  const shouldQuery = !!promptId;
  const chainKey = promptId;

  const { data: versions = [], error: versionsError } = useQuery({
    queryKey: ["promptChainVersions", promptId],
    queryFn: () => fetchPromptChainVersions(promptId, false),
    enabled: shouldQuery,
    retry: 2,
    staleTime: 2 * 60 * 1000,
  });

  const {
    data: latestVersion,
    isLoading,
    error: latestVersionError,
  } = useQuery({
    queryKey: ["promptChainLatest", promptId],
    queryFn: () => fetchLatestPromptChainVersion(promptId),
    enabled: shouldQuery,
    retry: 2,
    staleTime: 2 * 60 * 1000,
  });

  const queryError = (versionsError || latestVersionError) as Error | null;

  const saveWorkingCopy = useCallback(
    (baseVersionId: string, nextEntries: PromptEntryData[]) => {
      const save = workingCopySaveRef.current.then(() =>
        savePromptChainWorkingCopy(chainKey, baseVersionId, nextEntries),
      );
      workingCopySaveRef.current = save.catch(() => undefined);
      return save;
    },
    [chainKey],
  );

  useEffect(() => {
    queueMicrotask(() => {
      setCurrentVersionId(null);
      setEntries([]);
      setBaseEntries([]);
      setError(null);
    });
  }, [promptId]);

  useEffect(() => {
    if (!latestVersion) return;

    let isStale = false;

    const loadInitialState = async () => {
      try {
        const workingCopy = await getPromptChainWorkingCopy(chainKey);

        if (isStale) return;

        if (workingCopy) {
          setCurrentVersionId(workingCopy.baseVersionId);
          setEntries(workingCopy.entries.map(normalizePromptEntryData));
          const baseEntriesData = latestVersion.entries.map(mapPromptEntry);
          setBaseEntries(baseEntriesData);
        } else {
          setCurrentVersionId(latestVersion.version.id);
          const entriesData = latestVersion.entries.map(mapPromptEntry);
          setEntries(entriesData);
          setBaseEntries(entriesData);

          await saveWorkingCopy(latestVersion.version.id, entriesData);
        }
      } catch (err) {
        if (isStale) return;

        console.error("Failed to load initial state:", err);
        setError(err as Error);
      }
    };

    loadInitialState();

    return () => {
      isStale = true;
    };
  }, [chainKey, latestVersion, saveWorkingCopy]);

  useEffect(() => {
    if (!currentVersionId || entries.length === 0) return;

    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }

    saveTimerRef.current = setTimeout(async () => {
      try {
        await saveWorkingCopy(currentVersionId, entries);
      } catch (err) {
        console.error("Failed to save working copy:", err);
      } finally {
        saveTimerRef.current = null;
      }
    }, 1000);

    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
    };
  }, [chainKey, currentVersionId, entries, saveWorkingCopy]);

  const loadVersion = useCallback(
    async (versionId: string) => {
      try {
        setError(null);
        const versionData = await fetchPromptChainVersion(promptId, versionId);

        setCurrentVersionId(versionData.version.id);
        const entriesData = versionData.entries.map(mapPromptEntry);
        setEntries(entriesData);
        setBaseEntries(entriesData);

        await saveWorkingCopy(versionData.version.id, entriesData);
      } catch (err) {
        console.error("加载版本失败:", err);
        setError(err as Error);
      }
    },
    [promptId, saveWorkingCopy],
  );

  const currentVersion =
    versions.find((v) => v.id === currentVersionId) || latestVersion?.version || null;

  const isDefault = currentVersionId === "default" || currentVersion?.versionNumber === 0;
  const hasUnsavedChanges = JSON.stringify(entries) !== JSON.stringify(baseEntries);

  const createVersionMutation = useMutation({
    mutationFn: async (note?: string) => {
      if (!hasUnsavedChanges) throw new Error("No unsaved changes");

      const parentVersionId = isDefault ? "default" : currentVersionId;
      if (!parentVersionId) throw new Error("No current version");

      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
      await saveWorkingCopy(parentVersionId, entries);

      return createPromptChainVersion(promptId, {
        parentVersionId,
        entries: entries,
        note,
      });
    },
    onSuccess: async (data) => {
      try {
        queryClient.invalidateQueries({
          queryKey: ["promptChainVersions", promptId],
        });
        queryClient.invalidateQueries({
          queryKey: ["promptChainLatest", promptId],
        });

        setCurrentVersionId(data.version.id);

        const entriesData = data.entries.map(mapPromptEntry);
        setEntries(entriesData);
        setBaseEntries(entriesData);

        await deletePromptChainWorkingCopy(chainKey);

        setError(null);
      } catch (err) {
        console.error("Failed to update after version creation:", err);
        setError(err as Error);
      }
    },
    onError: (err) => {
      console.error("创建版本失败:", err);
      setError(err as Error);
    },
  });

  const saveVersion = useCallback(
    (note?: string) => {
      createVersionMutation.mutate(note);
    },
    [createVersionMutation],
  );

  const resetWorkingCopy = useCallback(
    async (baseVersionId: string, nextEntries: PromptEntryData[]) => {
      setCurrentVersionId(baseVersionId);
      setEntries(nextEntries);
      setBaseEntries(nextEntries);
      await saveWorkingCopy(baseVersionId, nextEntries);
      queryClient.invalidateQueries({
        queryKey: ["promptChainVersions", promptId],
      });
      queryClient.invalidateQueries({
        queryKey: ["promptChainLatest", promptId],
      });
    },
    [promptId, queryClient, saveWorkingCopy],
  );

  return {
    currentVersion,
    versions,
    entries,
    setEntries,
    isLoading,
    loadVersion,
    saveVersion,
    isSaving: createVersionMutation.isPending,
    hasUnsavedChanges,
    error: error || queryError,
    isDefault,
    resetWorkingCopy,
  };
}

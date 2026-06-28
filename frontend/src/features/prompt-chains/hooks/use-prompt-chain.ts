/**
 * usePromptChain Hook
 *
 * 管理提示词链的状态：版本、条目、Working Copy
 * 增强版：添加错误处理和健壮性
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchPromptChainVersions,
  fetchLatestPromptChainVersion,
  fetchPromptChainVersion,
  createPromptChainVersion,
} from "@/lib/api-client";
import { countTokens } from "@/lib/tiktoken-utils";
import {
  getPromptChainWorkingCopy,
  savePromptChainWorkingCopy,
  deletePromptChainWorkingCopy,
} from "@/lib/local-db";
import type {
  PromptEntry,
  PromptEntryData,
} from "@/lib/prompt-chain.types";

function getChainKey(modeName: string, taskName: string, agentName: string | null): string {
  return agentName ? `${modeName}/${taskName}/${agentName}` : `${modeName}/${taskName}`;
}

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

export function usePromptChain(
  modeName: string,
  taskName: string,
  agentName: string | null
) {
  const queryClient = useQueryClient();
  const [currentVersionId, setCurrentVersionId] = useState<string | null>(null);
  const [entries, setEntries] = useState<PromptEntryData[]>([]);
  const [baseEntries, setBaseEntries] = useState<PromptEntryData[]>([]);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const shouldQuery = !!modeName && !!taskName;

  const chainKey = getChainKey(modeName, taskName, agentName);

  const { data: versions = [], error: versionsError } = useQuery({
    queryKey: ["promptChainVersions", modeName, taskName, agentName],
    queryFn: () => fetchPromptChainVersions(modeName, taskName, agentName, false),
    enabled: shouldQuery,
    retry: 2,
    staleTime: 2 * 60 * 1000,
  });

  const { data: latestVersion, isLoading, error: latestVersionError } = useQuery({
    queryKey: ["promptChainLatest", modeName, taskName, agentName],
    queryFn: () => fetchLatestPromptChainVersion(modeName, taskName, agentName),
    enabled: shouldQuery,
    retry: 2,
    staleTime: 2 * 60 * 1000,
  });

  const queryError = (versionsError || latestVersionError) as Error | null;

  useEffect(() => {
    queueMicrotask(() => {
      setCurrentVersionId(null);
      setEntries([]);
      setBaseEntries([]);
      setError(null);
    });
  }, [modeName, taskName, agentName]);

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

          await savePromptChainWorkingCopy(
            chainKey,
            latestVersion.version.id,
            entriesData
          );
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
  }, [chainKey, latestVersion]);

  useEffect(() => {
    if (!currentVersionId || entries.length === 0) return;

    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
    }

    saveTimerRef.current = setTimeout(async () => {
      try {
        await savePromptChainWorkingCopy(chainKey, currentVersionId, entries);
      } catch (err) {
        console.error("Failed to save working copy:", err);
      } finally {
        saveTimerRef.current = null;
      }
    }, 2000);

    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
    };
  }, [chainKey, currentVersionId, entries]);

  const loadVersion = useCallback(
    async (versionId: string) => {
      try {
        setError(null);
        const versionData = await fetchPromptChainVersion(
          modeName,
          taskName,
          versionId,
          agentName
        );

        setCurrentVersionId(versionData.version.id);
        const entriesData = versionData.entries.map(mapPromptEntry);
        setEntries(entriesData);
        setBaseEntries(entriesData);

        await savePromptChainWorkingCopy(chainKey, versionData.version.id, entriesData);
      } catch (err) {
        console.error("加载版本失败:", err);
        setError(err as Error);
      }
    },
    [chainKey, modeName, taskName, agentName]
  );

  const currentVersion = versions.find((v) => v.id === currentVersionId) || latestVersion?.version || null;

  const isDefault = currentVersionId === "default" || currentVersion?.versionNumber === 0;
  const hasUnsavedChanges = JSON.stringify(entries) !== JSON.stringify(baseEntries);

  const createVersionMutation = useMutation({
    mutationFn: async (note?: string) => {
      if (!hasUnsavedChanges) throw new Error("No unsaved changes");

      const parentVersionId = isDefault ? "default" : currentVersionId;
      if (!parentVersionId) throw new Error("No current version");

      return createPromptChainVersion(modeName, taskName, {
        parentVersionId,
        entries: entries,
        note,
      }, agentName);
    },
    onSuccess: async (data) => {
      try {
        queryClient.invalidateQueries({
          queryKey: ["promptChainVersions", modeName, taskName, agentName],
        });
        queryClient.invalidateQueries({
          queryKey: ["promptChainLatest", modeName, taskName, agentName],
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
    [createVersionMutation]
  );

  const resetWorkingCopy = useCallback(
    async (baseVersionId: string, nextEntries: PromptEntryData[]) => {
      setCurrentVersionId(baseVersionId);
      setEntries(nextEntries);
      setBaseEntries(nextEntries);
      await savePromptChainWorkingCopy(chainKey, baseVersionId, nextEntries);
      queryClient.invalidateQueries({
        queryKey: ["promptChainVersions", modeName, taskName, agentName],
      });
      queryClient.invalidateQueries({
        queryKey: ["promptChainLatest", modeName, taskName, agentName],
      });
    },
    [agentName, chainKey, modeName, queryClient, taskName]
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

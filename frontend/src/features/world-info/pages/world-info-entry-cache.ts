import type { WorldInfoEntryBrief, WorldInfoEntryBriefListResponse } from "@/lib/world-info.types";

export function updateWorldInfoEntryBrief(
  data: WorldInfoEntryBriefListResponse | undefined,
  entryId: string,
  updateEntry: (entry: WorldInfoEntryBrief) => WorldInfoEntryBrief,
): WorldInfoEntryBriefListResponse | undefined {
  if (!data) return data;

  return {
    ...data,
    items: data.items.map((entry) => (entry.id === entryId ? updateEntry(entry) : entry)),
  };
}

export function updateWorldInfoEntryBriefs(
  data: WorldInfoEntryBriefListResponse | undefined,
  entryIds: readonly string[],
  updateEntry: (entry: WorldInfoEntryBrief) => WorldInfoEntryBrief,
): WorldInfoEntryBriefListResponse | undefined {
  if (!data) return data;

  const entryIdSet = new Set(entryIds);
  return {
    ...data,
    items: data.items.map((entry) => (entryIdSet.has(entry.id) ? updateEntry(entry) : entry)),
  };
}

export function mergeWorldInfoEntryOrder(
  data: WorldInfoEntryBriefListResponse | undefined,
  reorderedEntries: WorldInfoEntryBrief[],
): WorldInfoEntryBriefListResponse | undefined {
  if (!data) return data;

  const orderById = new Map(reorderedEntries.map((entry) => [entry.id, entry.order]));
  return {
    ...data,
    items: data.items.map((entry) => {
      const order = orderById.get(entry.id);
      return order === undefined ? entry : { ...entry, order };
    }),
  };
}

interface EntityListCache<TItem> {
  items: TItem[];
  total: number;
}

export function removeListItemFromCache<TItem extends { id: string }>(
  data: EntityListCache<TItem> | undefined,
  itemId: string,
): EntityListCache<TItem> | undefined {
  if (!data) return data;

  const items = data.items.filter((item) => item.id !== itemId);
  if (items.length === data.items.length) return data;

  return {
    ...data,
    items,
    total: Math.max(0, data.total - 1),
  };
}

export interface Instance {
  id: string;
  name: string;
  url: string;
}
export const STORAGE_KEY: string;
export function normalizeInstanceUrl(input: string): string;
export function readInstances(storage: Pick<Storage, "getItem">): Instance[];

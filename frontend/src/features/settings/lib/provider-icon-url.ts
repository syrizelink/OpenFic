import { getApiBaseUrl, resolveBackendUrl } from "@/lib/api-client";

export function getProviderIconUrl(iconPath?: string | null): string | null {
  if (!iconPath) {
    return null;
  }

  if (iconPath.startsWith("/")) {
    return resolveBackendUrl(iconPath);
  }

  return `${getApiBaseUrl()}/${iconPath.replace(/^\/+/, "")}`;
}

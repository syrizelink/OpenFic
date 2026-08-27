import { getApiBaseUrl, resolveBackendUrl } from "@/lib/api-client";

const FRONTEND_ICON_PATH_PREFIX = "/provider-icons/";

export function getProviderIconUrl(iconPath?: string | null): string | null {
  if (!iconPath) {
    return null;
  }

  if (iconPath.startsWith(FRONTEND_ICON_PATH_PREFIX)) {
    return iconPath;
  }

  if (iconPath.startsWith("/")) {
    return resolveBackendUrl(iconPath);
  }

  return `${getApiBaseUrl()}/${iconPath.replace(/^\/+/, "")}`;
}

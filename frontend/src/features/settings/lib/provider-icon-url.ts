export function getProviderIconUrl(iconPath?: string | null): string | null {
  if (!iconPath) {
    return null;
  }

  if (iconPath.startsWith("/")) {
    return iconPath;
  }

  return `/api/v1/${iconPath.replace(/^\/+/, "")}`;
}

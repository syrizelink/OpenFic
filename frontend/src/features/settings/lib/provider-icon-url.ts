export function getUploadedProviderIconUrl(iconPath?: string | null): string | null {
  if (!iconPath) {
    return null;
  }

  if (iconPath.startsWith("/")) {
    return iconPath;
  }

  return `/api/icons/model/${iconPath}`;
}

export function getCatalogProviderIconUrl(iconPath?: string | null): string | null {
  if (!iconPath) {
    return null;
  }

  if (iconPath.startsWith("http://") || iconPath.startsWith("https://")) {
    return iconPath;
  }

  if (iconPath.startsWith("/")) {
    return iconPath;
  }

  return `/api/v1/${iconPath.replace(/^\/+/, "")}`;
}

/**
 * Provider Icons
 *
 * 提供商图标工具。
 */

import { useState } from "react";
import { Loader2 } from "lucide-react";

import type { ProviderType } from "@/lib/model.types";
import {
  getCatalogProviderIconUrl,
  getUploadedProviderIconUrl,
} from "./provider-icon-url";

/**
 * 提供商图标组件
 */
interface ProviderIconProps {
  providerType?: ProviderType;
  uploadedIconPath?: string | null;
  catalogIconPath?: string | null;
  size?: number;
  className?: string;
}

export function ProviderIcon({
  uploadedIconPath,
  catalogIconPath,
  size = 20,
  className = "",
}: ProviderIconProps) {
  const uploadedIconUrl = getUploadedProviderIconUrl(uploadedIconPath);
  const catalogIconUrl = getCatalogProviderIconUrl(catalogIconPath);
  const iconUrl = uploadedIconUrl || catalogIconUrl;
  const shouldShowLoading = Boolean(catalogIconUrl && !uploadedIconUrl);
  const [loadedIconUrl, setLoadedIconUrl] = useState<string | null>(null);
  const isLoaded = !shouldShowLoading || loadedIconUrl === iconUrl;

  if (iconUrl) {
    return (
      <span
        aria-hidden="true"
        className={className}
        style={{
          position: "relative",
          display: "inline-flex",
          width: size,
          height: size,
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        {shouldShowLoading && !isLoaded ? (
          <Loader2
            size={Math.max(12, Math.round(size * 0.7))}
            className="animate-spin"
            style={{
              position: "absolute",
              color: "var(--gray-10)",
            }}
          />
        ) : null}
        <img
          src={iconUrl}
          alt=""
          aria-hidden="true"
          width={size}
          height={size}
          onLoad={() => setLoadedIconUrl(iconUrl)}
          onError={() => setLoadedIconUrl(iconUrl)}
          style={{
            width: size,
            height: size,
            display: "block",
            opacity: shouldShowLoading && !isLoaded ? 0 : 1,
          }}
        />
      </span>
    );
  }

  return null;
}

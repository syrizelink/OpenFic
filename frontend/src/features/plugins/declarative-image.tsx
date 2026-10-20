import { useQuery } from "@tanstack/react-query";
import type { CSSProperties } from "react";

import { apiClient } from "@/lib/api-client";

export function DeclarativeImage({
  pluginId,
  asset,
  alt,
  fit = "contain",
  style,
  ...props
}: {
  pluginId: string;
  asset: string;
  alt: string;
  width?: number;
  height?: number;
  style?: CSSProperties;
  fit?: "contain" | "cover" | "fill";
}) {
  const { data, error } = useQuery({
    queryKey: ["plugin-asset", pluginId, asset],
    queryFn: async () => {
      const { data } = await apiClient.post<{ result: { mime: string; base64: string } }>(
        `/plugins/${pluginId}/rpc`,
        { method: "sdk.assets.read", params: { name: asset } },
      );
      if (!/^image\/(png|jpeg|webp|gif|avif)$/.test(data.result.mime))
        throw new Error("Unsupported image format");
      return `data:${data.result.mime};base64,${data.result.base64}`;
    },
    gcTime: 0,
    refetchOnWindowFocus: false,
    retry: false,
  });
  if (error)
    return (
      <span
        role="img"
        aria-label={alt}
        title="Image unavailable"
      >
        {alt}
      </span>
    );
  return (
    <img
      {...props}
      src={data}
      alt={alt}
      draggable={false}
      style={{ ...style, objectFit: fit }}
    />
  );
}

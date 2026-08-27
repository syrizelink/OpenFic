/**
 * Provider Icons
 *
 * 提供商图标工具。
 */

import { useEffect, useRef, useState } from "react";

import { Spinner } from "@/components";

import { scheduleProviderIconRequest } from "./provider-icon-request-queue";
import { getProviderIconUrl } from "./provider-icon-url";

/**
 * 提供商图标组件
 */
interface ProviderIconProps {
  iconPath?: string | null;
  size?: number;
  preserveColors?: boolean;
}

const providerIconCache = new Map<string, SVGSVGElement>();
const pendingProviderIconLoads = new Map<string, Promise<SVGSVGElement>>();

function getProviderIconCacheKey(iconUrl: string, size: number, preserveColors: boolean): string {
  return `${iconUrl}:${size}:${preserveColors}`;
}

function cloneProviderSvg(svg: SVGSVGElement): SVGSVGElement {
  return svg.cloneNode(true) as SVGSVGElement;
}

function prepareProviderSvg(svg: SVGSVGElement, size: number, preserveColors: boolean): void {
  const inheritsNoFill = svg.getAttribute("fill") === "none";

  svg
    .querySelectorAll("script, foreignObject, image, use, iframe, object, embed, link, style")
    .forEach((element) => element.remove());
  svg.querySelectorAll<SVGElement>("*").forEach((element) => {
    for (const attribute of Array.from(element.attributes)) {
      if (
        attribute.name.startsWith("on") ||
        attribute.name === "href" ||
        attribute.name === "xlink:href"
      ) {
        element.removeAttribute(attribute.name);
      }
    }

    if (!preserveColors) {
      if (
        element.getAttribute("fill") !== "none" &&
        (element.hasAttribute("fill") || !inheritsNoFill)
      ) {
        element.setAttribute("fill", "currentColor");
      }
      if (element.hasAttribute("stroke")) {
        element.setAttribute("stroke", "currentColor");
      }
    }
    element.removeAttribute("style");
  });

  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("aria-hidden", "true");
  svg.style.display = "block";
}

async function loadProviderSvg(
  iconUrl: string,
  size: number,
  preserveColors: boolean,
): Promise<SVGSVGElement> {
  const cacheKey = getProviderIconCacheKey(iconUrl, size, preserveColors);
  const cachedSvg = providerIconCache.get(cacheKey);
  if (cachedSvg) return cloneProviderSvg(cachedSvg);

  const pendingLoad = pendingProviderIconLoads.get(cacheKey);
  if (pendingLoad) return cloneProviderSvg(await pendingLoad);

  const loadPromise = (async () => {
    const response = await fetch(iconUrl, { credentials: "include" });
    if (!response.ok) throw new Error(`Failed to load provider icon: ${response.status}`);

    const document = new DOMParser().parseFromString(await response.text(), "image/svg+xml");
    const svg = document.documentElement;
    if (!(svg instanceof SVGSVGElement)) throw new Error("Provider icon is not an SVG");

    prepareProviderSvg(svg, size, preserveColors);
    providerIconCache.set(cacheKey, svg);
    return svg;
  })().finally(() => {
    pendingProviderIconLoads.delete(cacheKey);
  });

  pendingProviderIconLoads.set(cacheKey, loadPromise);
  return cloneProviderSvg(await loadPromise);
}

export function ProviderIcon({ iconPath, size = 20, preserveColors = false }: ProviderIconProps) {
  const iconUrl = getProviderIconUrl(iconPath);
  const svgContainerRef = useRef<HTMLSpanElement>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!iconUrl) return;

    const svgContainer = svgContainerRef.current;
    let isCancelled = false;
    const cacheKey = getProviderIconCacheKey(iconUrl, size, preserveColors);
    const cachedSvg = providerIconCache.get(cacheKey);

    if (cachedSvg) {
      svgContainer?.replaceChildren(cloneProviderSvg(cachedSvg));
      setIsLoading(false);
      return;
    }

    svgContainer?.replaceChildren();
    setIsLoading(true);

    const cancelRequest = scheduleProviderIconRequest(async () => {
      try {
        const svg = await loadProviderSvg(iconUrl, size, preserveColors);
        if (!isCancelled) svgContainerRef.current?.replaceChildren(svg);
      } catch {
        if (!isCancelled) svgContainerRef.current?.replaceChildren();
      } finally {
        if (!isCancelled) setIsLoading(false);
      }
    });

    return () => {
      isCancelled = true;
      cancelRequest();
    };
  }, [iconUrl, preserveColors, size]);

  if (!iconUrl) {
    return null;
  }

  return (
    <span
      aria-hidden="true"
      style={{
        display: "inline-flex",
        width: size,
        height: size,
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
    >
      {isLoading ? <Spinner size={12} /> : null}
      <span
        ref={svgContainerRef}
        style={{
          display: isLoading ? "none" : "inline-flex",
          width: isLoading ? undefined : size,
          height: isLoading ? undefined : size,
          alignItems: "center",
          justifyContent: "center",
        }}
      />
    </span>
  );
}

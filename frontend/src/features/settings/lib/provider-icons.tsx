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
}

function prepareProviderSvg(svg: SVGSVGElement, size: number): void {
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

    if (
      element.getAttribute("fill") !== "none" &&
      (element.hasAttribute("fill") || !inheritsNoFill)
    ) {
      element.setAttribute("fill", "currentColor");
    }
    if (element.hasAttribute("stroke")) {
      element.setAttribute("stroke", "currentColor");
    }
    element.removeAttribute("style");
  });

  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("aria-hidden", "true");
  svg.style.display = "block";
}

export function ProviderIcon({ iconPath, size = 20 }: ProviderIconProps) {
  const iconUrl = getProviderIconUrl(iconPath);
  const svgContainerRef = useRef<HTMLSpanElement>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!iconUrl) return;

    const abortController = new AbortController();
    const svgContainer = svgContainerRef.current;

    svgContainer?.replaceChildren();
    setIsLoading(true);

    const cancelRequest = scheduleProviderIconRequest(async () => {
      try {
        const response = await fetch(iconUrl, {
          signal: abortController.signal,
          credentials: "include",
        });
        if (!response.ok) throw new Error(`Failed to load provider icon: ${response.status}`);

        const document = new DOMParser().parseFromString(await response.text(), "image/svg+xml");
        const svg = document.documentElement;
        if (!(svg instanceof SVGSVGElement)) throw new Error("Provider icon is not an SVG");

        prepareProviderSvg(svg, size);
        if (!abortController.signal.aborted) {
          svgContainerRef.current?.replaceChildren(svg);
        }
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          svgContainerRef.current?.replaceChildren();
        }
      } finally {
        if (!abortController.signal.aborted) setIsLoading(false);
      }
    });

    return () => {
      abortController.abort();
      cancelRequest();
    };
  }, [iconUrl, size]);

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

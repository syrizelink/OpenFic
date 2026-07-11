/**
 * Provider Icons
 *
 * 提供商图标工具。
 */

import { ReactSVG } from "react-svg";

import { Spinner } from "@/components";

import { getProviderIconUrl } from "./provider-icon-url";

/**
 * 提供商图标组件
 */
interface ProviderIconProps {
  iconPath?: string | null;
  size?: number;
}

function prepareProviderSvg(svg: SVGSVGElement, size: number): void {
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

    if (element.getAttribute("fill") !== "none") {
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
      <ReactSVG
        beforeInjection={(svg) => prepareProviderSvg(svg, size)}
        evalScripts="never"
        fallback={() => null}
        loading={() => <Spinner size={12} />}
        src={iconUrl}
        style={{
          display: "inline-flex",
          width: size,
          height: size,
          alignItems: "center",
          justifyContent: "center",
        }}
        wrapper="span"
      />
    </span>
  );
}

import { Text } from "@radix-ui/themes";
import { Package } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { getApiBaseUrl } from "@/lib/api-client";

import type { InstalledPlugin } from "./api";

export function PluginImage({
  plugin,
  placement,
}: {
  plugin: InstalledPlugin;
  placement: "list" | "detail";
}) {
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const source = plugin.icon
    ? `${getApiBaseUrl()}/plugins/${encodeURIComponent(plugin.id)}/icon?${new URLSearchParams({
        version: plugin.version,
        revision: String(plugin.development_revision ?? 0),
        path: plugin.icon,
      })}`
    : null;
  if (!source || failedSource === source)
    return placement === "list" ? (
      <Package
        size={14}
        aria-hidden="true"
      />
    ) : null;
  return (
    <img
      className={placement === "list" ? "plugin-icon-list" : "plugin-icon-detail"}
      src={source}
      alt=""
      aria-hidden="true"
      onError={() => setFailedSource(source)}
    />
  );
}

export function PluginDescription({ description }: { description: string }) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const measureRef = useRef<HTMLParagraphElement>(null);
  const measureTextRef = useRef<HTMLSpanElement>(null);
  const measureSuffixRef = useRef<HTMLSpanElement>(null);
  const [prefix, setPrefix] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(false);
  const expandLabel = t("plugins.expandDescription");

  useLayoutEffect(() => {
    const container = containerRef.current;
    const measure = measureRef.current;
    const measureText = measureTextRef.current;
    const suffix = measureSuffixRef.current;
    if (!container || !measure || !measureText || !suffix) return;
    let isActive = true;

    const updateTruncation = () => {
      if (!container.getBoundingClientRect().width) return;
      const lineHeight = Number.parseFloat(getComputedStyle(measure).lineHeight);
      if (!Number.isFinite(lineHeight)) return;
      const maxHeight = lineHeight * 2 + 0.5;
      measureText.textContent = description;
      suffix.hidden = true;
      if (measure.getBoundingClientRect().height <= maxHeight) {
        setPrefix(null);
        return;
      }
      suffix.hidden = false;
      const graphemes = Array.from(
        new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(description),
        (item) => item.segment,
      );
      let low = 0;
      let high = graphemes.length;
      while (low < high) {
        const middle = Math.ceil((low + high) / 2);
        measureText.textContent = graphemes.slice(0, middle).join("").trimEnd();
        if (measure.getBoundingClientRect().height <= maxHeight) low = middle;
        else high = middle - 1;
      }
      setPrefix(graphemes.slice(0, low).join("").trimEnd());
    };

    updateTruncation();
    const observer = new ResizeObserver(updateTruncation);
    observer.observe(container);
    document.fonts.addEventListener("loadingdone", updateTruncation);
    void document.fonts.ready.then(() => {
      if (isActive) updateTruncation();
    });
    return () => {
      isActive = false;
      observer.disconnect();
      document.fonts.removeEventListener("loadingdone", updateTruncation);
    };
  }, [description, expandLabel]);

  return (
    <div
      ref={containerRef}
      className="plugin-description"
    >
      <Text
        as="p"
        size="2"
        color="gray"
        className="plugin-description-text"
      >
        {isExpanded || prefix === null ? description : prefix}
        {(isExpanded || prefix !== null) && (
          <span className="plugin-description-suffix">
            {!isExpanded && "..."}
            <button
              type="button"
              className="plugin-description-expand"
              aria-expanded={isExpanded}
              onClick={() => setIsExpanded(!isExpanded)}
            >
              {isExpanded ? t("plugins.collapseDescription") : expandLabel}
            </button>
          </span>
        )}
      </Text>
      <div
        className="plugin-description-measure-container"
        aria-hidden="true"
      >
        <Text
          as="p"
          size="2"
          color="gray"
          className="plugin-description-text"
          ref={measureRef}
        >
          <span ref={measureTextRef} />
          <span
            ref={measureSuffixRef}
            className="plugin-description-suffix"
          >
            ...<span className="plugin-description-expand">{expandLabel}</span>
          </span>
        </Text>
      </div>
    </div>
  );
}

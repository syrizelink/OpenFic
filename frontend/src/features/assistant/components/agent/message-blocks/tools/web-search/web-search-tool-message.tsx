import { Box } from "@radix-ui/themes";
import { ExternalLink, Globe } from "lucide-react";
import { useState } from "react";

import { ExternalLinkSafetyDialog } from "@/components/external-link-safety-dialog";
import i18n from "@/i18n";
import type { AgentMessage } from "@/lib/agent.types";

import { joinClassNames } from "../../shared/message-shell-utils";
import { ToolBody, ToolNotice } from "../shared/tool-message-shared";
import {
  getToolResultData,
  getToolResultMessage,
  getStreamingData,
} from "../shared/tool-message-utils";
import {
  getWebSearchFaviconUrl,
  isSafeWebSearchUrl,
  normalizeWebSearchData,
  type WebSearchResultPayload,
} from "./web-search-tool-message.utils";

import "./web-search-tool-message.css";

interface WebSearchToolMessageProps {
  message: AgentMessage;
}

function getResultTitle(result: WebSearchResultPayload, index: number): string {
  return (
    result.title || result.url || i18n.t("assistant.tools.webSearchResult", { index: index + 1 })
  );
}

function WebSearchResultFavicon({ url }: { url: string }) {
  const faviconUrl = getWebSearchFaviconUrl(url);
  const [loadedFaviconUrl, setLoadedFaviconUrl] = useState<string>();
  const [hasError, setHasError] = useState(false);
  const isLoaded = faviconUrl !== undefined && loadedFaviconUrl === faviconUrl && !hasError;

  return (
    <span
      className="agent-web-search-result-favicon"
      aria-hidden="true"
    >
      {!isLoaded ? (
        <Globe
          size={14}
          className="agent-web-search-result-favicon-fallback"
        />
      ) : null}
      {faviconUrl && !hasError ? (
        <img
          src={faviconUrl}
          alt=""
          className={`agent-web-search-result-favicon-image${
            isLoaded ? " agent-web-search-result-favicon-image--loaded" : ""
          }`}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onLoad={() => setLoadedFaviconUrl(faviconUrl)}
          onError={() => setHasError(true)}
        />
      ) : null}
    </span>
  );
}

interface WebSearchToolIconProps {
  message: AgentMessage;
  className: string;
}

export function WebSearchToolIcon({ message, className }: WebSearchToolIconProps) {
  const data = normalizeWebSearchData(getToolResultData(message) ?? getStreamingData(message));
  const [loadedIconUrls, setLoadedIconUrls] = useState<Array<string | undefined>>([]);
  const [failedIconUrls, setFailedIconUrls] = useState<Array<string | undefined>>([]);
  const faviconCandidates = data.results
    .map((result, index) => ({ index, url: getWebSearchFaviconUrl(result.url) }))
    .filter(
      (candidate): candidate is { index: number; url: string } => candidate.url !== undefined,
    );
  const loadedIcons = faviconCandidates.filter(
    ({ index, url }) => loadedIconUrls[index] === url && failedIconUrls[index] !== url,
  );
  const stackedIcons = loadedIcons.length >= 2 ? loadedIcons.slice(0, 3) : [];
  const stackPositions = new Map(stackedIcons.map(({ index }, position) => [index, position]));
  const showStack = stackedIcons.length >= 2;

  return (
    <span
      className={joinClassNames(
        "agent-web-search-tool-icon",
        showStack && `agent-web-search-tool-icon--stack-${stackedIcons.length}`,
      )}
      aria-hidden="true"
    >
      {!showStack ? (
        <Globe
          size={16}
          className={className}
        />
      ) : null}
      {faviconCandidates.map(({ index, url }) => {
        const stackPosition = stackPositions.get(index);
        return (
          <img
            key={`${index}:${url}`}
            src={url}
            alt=""
            className={joinClassNames(
              "agent-web-search-tool-icon-image",
              stackPosition !== undefined && "agent-web-search-tool-icon-image--visible",
              stackPosition === 0 && "agent-web-search-tool-icon-image--first",
              stackPosition === 1 && "agent-web-search-tool-icon-image--second",
              stackPosition === 2 && "agent-web-search-tool-icon-image--third",
            )}
            loading="lazy"
            decoding="async"
            referrerPolicy="no-referrer"
            onLoad={() => {
              setLoadedIconUrls((current) => {
                const next = [...current];
                next[index] = url;
                return next;
              });
            }}
            onError={() => {
              setFailedIconUrls((current) => {
                const next = [...current];
                next[index] = url;
                return next;
              });
            }}
          />
        );
      })}
    </span>
  );
}

interface WebSearchResultItemProps {
  result: WebSearchResultPayload;
  index: number;
  onOpenLink: (url: string) => void;
}

function WebSearchResultItem({ result, index, onOpenLink }: WebSearchResultItemProps) {
  const isLink = isSafeWebSearchUrl(result.url);
  const title = getResultTitle(result, index);
  const titleContent = (
    <>
      <span
        className="agent-web-search-result-index"
        aria-hidden="true"
      >
        {index + 1}
      </span>
      <WebSearchResultFavicon url={result.url} />
      <span className="agent-web-search-result-title">{title}</span>
      <ExternalLink
        className="agent-web-search-result-icon"
        size={13}
        aria-hidden="true"
      />
    </>
  );

  return (
    <li className="agent-web-search-result">
      {isLink ? (
        <a
          className="agent-web-search-result-link"
          href={result.url}
          onClick={(event) => {
            event.preventDefault();
            onOpenLink(result.url);
          }}
          rel="noopener noreferrer"
          target="_blank"
        >
          {titleContent}
        </a>
      ) : (
        <div className="agent-web-search-result-link">{titleContent}</div>
      )}
      {result.snippet ? (
        <div className="agent-web-search-result-snippet">{result.snippet}</div>
      ) : null}
    </li>
  );
}

export function WebSearchToolMessage({ message }: WebSearchToolMessageProps) {
  const data = normalizeWebSearchData(getToolResultData(message) ?? getStreamingData(message));
  const [pendingUrl, setPendingUrl] = useState<string | null>(null);

  const handleConfirmLink = () => {
    if (pendingUrl) {
      window.open(pendingUrl, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <>
      <ToolBody>
        <Box className="agent-web-search-panel">
          {data.results.length > 0 ? (
            <ol className="agent-web-search-results">
              {data.results.map((result, index) => (
                <WebSearchResultItem
                  key={`${result.url}:${result.title}:${index}`}
                  result={result}
                  index={index}
                  onOpenLink={setPendingUrl}
                />
              ))}
            </ol>
          ) : (
            <ToolNotice title={i18n.t("assistant.tools.noWebSearchResults")}>
              {getToolResultMessage(message) ??
                i18n.t("assistant.tools.noWebSearchResultsDescription")}
            </ToolNotice>
          )}
        </Box>
      </ToolBody>
      <ExternalLinkSafetyDialog
        isOpen={pendingUrl !== null}
        url={pendingUrl ?? ""}
        onClose={() => setPendingUrl(null)}
        onConfirm={handleConfirmLink}
      />
    </>
  );
}

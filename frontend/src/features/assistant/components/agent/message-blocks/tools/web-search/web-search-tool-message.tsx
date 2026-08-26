import { Box } from "@radix-ui/themes";
import { ExternalLink } from "lucide-react";
import { useState } from "react";

import { ExternalLinkSafetyDialog } from "@/components/external-link-safety-dialog";
import i18n from "@/i18n";
import type { AgentMessage } from "@/lib/agent.types";

import { ToolBody, ToolNotice } from "../shared/tool-message-shared";
import {
  getToolResultData,
  getToolResultMessage,
  getStreamingData,
} from "../shared/tool-message-utils";
import {
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

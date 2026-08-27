import { cjk } from "@streamdown/cjk";
import { math } from "@streamdown/math";
import { mermaid } from "@streamdown/mermaid";
import {
  Streamdown,
  type AnimateOptions,
  type LinkSafetyConfig,
  type PluginConfig,
} from "streamdown";

import "katex/dist/katex.min.css";

import { createLimitedCodePlugin } from "@/lib/limited-code-highlighter";

import { ExternalLinkSafetyDialog } from "./external-link-safety-dialog";
import { STREAMDOWN_REMARK_PLUGINS } from "./streaming-markdown-config";

import "./streaming-markdown.css";

interface StreamingMarkdownProps {
  content: string;
  isStreaming?: boolean;
  className?: string;
}

const STREAMING_ANIMATION: AnimateOptions = {
  animation: "blurIn",
  duration: 200,
  easing: "ease-out",
  sep: "word",
};

const STREAMDOWN_PLUGINS: PluginConfig = {
  cjk,
  code: createLimitedCodePlugin(),
  math,
  mermaid,
};

const STREAMDOWN_CONTROLS = {
  code: false,
  table: false,
  mermaid: {
    copy: false,
    download: false,
    fullscreen: false,
    panZoom: true,
  },
};

const STREAMDOWN_LINK_SAFETY: LinkSafetyConfig = {
  enabled: true,
  renderModal: (props) => <ExternalLinkSafetyDialog {...props} />,
};

export function StreamingMarkdown({
  content,
  isStreaming = false,
  className,
}: StreamingMarkdownProps) {
  const markdownClassName = className ? `streaming-markdown ${className}` : "streaming-markdown";

  return (
    <Streamdown
      animated={STREAMING_ANIMATION}
      className={markdownClassName}
      controls={STREAMDOWN_CONTROLS}
      data-streaming={isStreaming ? "true" : undefined}
      isAnimating={isStreaming}
      lineNumbers
      linkSafety={STREAMDOWN_LINK_SAFETY}
      mode="streaming"
      parseIncompleteMarkdown
      plugins={STREAMDOWN_PLUGINS}
      remarkPlugins={STREAMDOWN_REMARK_PLUGINS}
    >
      {content}
    </Streamdown>
  );
}

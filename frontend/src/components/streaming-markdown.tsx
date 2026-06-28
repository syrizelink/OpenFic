import { cjk } from "@streamdown/cjk";
import { code } from "@streamdown/code";
import { math } from "@streamdown/math";
import { mermaid } from "@streamdown/mermaid";
import { AlertDialog, Button, Flex, Text } from "@radix-ui/themes";
import { useEffect, useRef, useState } from "react";
import {
  Streamdown,
  type AnimateOptions,
  type LinkSafetyConfig,
  type LinkSafetyModalProps,
  type PluginConfig,
} from "streamdown";
import "katex/dist/katex.min.css";

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
  sep: "word"
};

const STREAMDOWN_PLUGINS: PluginConfig = {
  cjk,
  code,
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

const COPY_FEEDBACK_MS = 2000;

const STREAMDOWN_LINK_SAFETY: LinkSafetyConfig = {
  enabled: true,
  renderModal: (props) => <StreamingMarkdownLinkSafetyDialog {...props} />,
};

function StreamingMarkdownLinkSafetyDialog({
  isOpen,
  onClose,
  onConfirm,
  url,
}: LinkSafetyModalProps) {
  const [copied, setCopied] = useState(false);
  const copyResetTimerRef = useRef<number | null>(null);

  const clearCopyResetTimer = () => {
    if (copyResetTimerRef.current !== null) {
      window.clearTimeout(copyResetTimerRef.current);
      copyResetTimerRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      clearCopyResetTimer();
    };
  }, []);

  const resetCopyFeedbackLater = () => {
    clearCopyResetTimer();
    copyResetTimerRef.current = window.setTimeout(() => {
      setCopied(false);
      copyResetTimerRef.current = null;
    }, COPY_FEEDBACK_MS);
  };

  const handleCopyLink = async () => {
    if (typeof navigator === "undefined" || !navigator.clipboard?.writeText) {
      return;
    }

    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      resetCopyFeedbackLater();
    } catch {
      setCopied(false);
    }
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      clearCopyResetTimer();
      setCopied(false);
      onClose();
    }
  };

  const handleConfirm = () => {
    onConfirm();
    onClose();
  };

  return (
    <AlertDialog.Root open={isOpen} onOpenChange={handleOpenChange}>
      <AlertDialog.Content
        className="streaming-markdown-link-dialog"
        data-streamdown="link-safety-dialog"
        maxWidth="420px"
      >
        <AlertDialog.Title>Open external link?</AlertDialog.Title>
        <AlertDialog.Description size="2">
          <Text color="gray">You're about to visit an external website.</Text>
        </AlertDialog.Description>

        <div
          className="streaming-markdown-link-dialog-url"
          data-streamdown="link-safety-dialog-url"
          dir="ltr"
        >
          {url}
        </div>

        <Flex className="streaming-markdown-link-dialog-actions" gap="3" justify="end" mt="4" wrap="wrap">
          <Button
            className="streaming-markdown-link-dialog-copy"
            color="gray"
            onClick={() => {
              void handleCopyLink();
            }}
            type="button"
            variant="soft"
          >
            {copied ? "Copied" : "Copy link"}
          </Button>
          <AlertDialog.Cancel>
            <Button color="gray" variant="soft">
              Close
            </Button>
          </AlertDialog.Cancel>
          <AlertDialog.Action>
            <Button onClick={handleConfirm}>Open link</Button>
          </AlertDialog.Action>
        </Flex>
      </AlertDialog.Content>
    </AlertDialog.Root>
  );
}

export function StreamingMarkdown({ content, isStreaming = false, className }: StreamingMarkdownProps) {
  const markdownClassName = className ? `streaming-markdown ${className}` : "streaming-markdown";

  return (
    <Streamdown
      animated={isStreaming ? STREAMING_ANIMATION : false}
      className={markdownClassName}
      controls={STREAMDOWN_CONTROLS}
      data-streaming={isStreaming ? "true" : undefined}
      isAnimating={isStreaming}
      lineNumbers
      linkSafety={STREAMDOWN_LINK_SAFETY}
      mode={isStreaming ? "streaming" : "static"}
      parseIncompleteMarkdown={isStreaming}
      plugins={STREAMDOWN_PLUGINS}
      remarkPlugins={STREAMDOWN_REMARK_PLUGINS}
    >
      {content}
    </Streamdown>
  );
}

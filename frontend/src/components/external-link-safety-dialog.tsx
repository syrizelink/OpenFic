import { Button, Dialog, Flex, Text } from "@radix-ui/themes";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { LinkSafetyModalProps } from "streamdown";

import "./external-link-safety-dialog.css";

const COPY_FEEDBACK_MS = 2000;

export function ExternalLinkSafetyDialog({
  isOpen,
  onClose,
  onConfirm,
  url,
}: LinkSafetyModalProps) {
  const { t } = useTranslation();
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
    <Dialog.Root
      open={isOpen}
      onOpenChange={handleOpenChange}
    >
      <Dialog.Content
        className="external-link-safety-dialog"
        data-streamdown="link-safety-dialog"
        maxWidth="420px"
        onPointerDownOutside={(event) => {
          event.preventDefault();
          handleOpenChange(false);
        }}
      >
        <Dialog.Title>{t("streamingMarkdown.openExternalLink")}</Dialog.Title>
        <Dialog.Description size="2">
          <Text color="gray">{t("streamingMarkdown.externalLinkWarning")}</Text>
        </Dialog.Description>

        <div
          className="external-link-safety-dialog-url"
          data-streamdown="link-safety-dialog-url"
          dir="ltr"
        >
          {url}
        </div>

        <Flex
          className="external-link-safety-dialog-actions"
          gap="3"
          justify="end"
          mt="4"
          wrap="wrap"
        >
          <Button
            className="external-link-safety-dialog-copy"
            color="gray"
            onClick={() => {
              void handleCopyLink();
            }}
            type="button"
            variant="soft"
          >
            {copied ? t("streamingMarkdown.copied") : t("streamingMarkdown.copyLink")}
          </Button>
          <Dialog.Close>
            <Button
              color="gray"
              variant="soft"
            >
              {t("common.close")}
            </Button>
          </Dialog.Close>
          <Dialog.Close>
            <Button onClick={handleConfirm}>{t("streamingMarkdown.openLink")}</Button>
          </Dialog.Close>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

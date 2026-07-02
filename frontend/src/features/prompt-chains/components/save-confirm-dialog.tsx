/**
 * SaveConfirmDialog Component
 *
 * 保存版本确认对话框（检测并警告版本截断）
 */

import { Dialog, Flex, Text, Button, Callout, Box } from "@radix-ui/themes";
import { AlertTriangle } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { PromptChainVersion } from "@/lib/prompt-chain.types";

interface SaveConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentVersion: PromptChainVersion | null;
  versions: PromptChainVersion[];
  onConfirm: () => void;
}

export function SaveConfirmDialog({
  open,
  onOpenChange,
  currentVersion,
  versions,
  onConfirm,
}: SaveConfirmDialogProps) {
  const { t } = useTranslation();
  if (!currentVersion) return null;

  // 检查当前版本是否是最新版本
  const activeVersions = versions.filter((v) => v.isActive);
  const maxVersionNumber = Math.max(...activeVersions.map((v) => v.versionNumber));
  const isLatestVersion = currentVersion.versionNumber === maxVersionNumber;

  // 计算将被截断的版本
  const versionsToTruncate = activeVersions.filter(
    (v) => v.versionNumber > currentVersion.versionNumber
  );

  const handleConfirm = () => {
    onConfirm();
    onOpenChange(false);
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content style={{ maxWidth: "500px" }}>
        <Dialog.Title>{t("promptChains.confirmSave")}</Dialog.Title>

        <Flex direction="column" gap="3" mt="3">
          <Text size="2">
            {t("promptChains.confirmSaveMessage", { version: currentVersion.versionNumber + 1 })}
          </Text>

          {/* 警告：从中间版本保存 */}
          {!isLatestVersion && versionsToTruncate.length > 0 && (
            <Callout.Root color="orange">
              <Callout.Icon>
                <AlertTriangle size={16} />
              </Callout.Icon>
              <Callout.Text>
                <Text size="2" weight="bold" mb="1">
                  {t("promptChains.confirmSaveTruncateWarningTitle")}
                </Text>
                <Text size="2">
                  {t("promptChains.confirmSaveTruncateWarningDescription", {
                    current: currentVersion.versionNumber,
                    next: currentVersion.versionNumber + 1,
                    max: maxVersionNumber,
                  })}
                </Text>
              </Callout.Text>
            </Callout.Root>
          )}

          {/* 将被截断的版本列表 */}
          {versionsToTruncate.length > 0 && (
            <Box
              p="3"
              style={{
                background: "var(--orange-a2)",
                border: "1px solid var(--orange-a5)",
                borderRadius: "var(--radius-2)",
              }}
            >
              <Text size="2" weight="bold" mb="2">
                {t("promptChains.truncatedVersions")}
              </Text>
              <Flex direction="column" gap="1">
                {versionsToTruncate.map((v) => (
                  <Text key={v.id} size="2">
                    • v{v.versionNumber} ({v.versionHash})
                    {v.note && ` - ${v.note}`}
                  </Text>
                ))}
              </Flex>
            </Box>
          )}
        </Flex>

        <Flex gap="3" mt="4" justify="end">
          <Dialog.Close>
            <Button variant="soft" color="gray">
              {t("common.cancel")}
            </Button>
          </Dialog.Close>
          <Button onClick={handleConfirm} color={isLatestVersion ? "blue" : "orange"}>
            {isLatestVersion ? t("promptChains.confirmSaveButton") : t("promptChains.confirmSaveAndTruncateButton")}
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

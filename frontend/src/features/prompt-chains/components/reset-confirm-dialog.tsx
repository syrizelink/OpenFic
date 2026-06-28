/**
 * ResetConfirmDialog Component
 *
 * 重置提示词链到默认状态的确认对话框
 */

import { Dialog, Flex, Text, Button } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";
import { AlertTriangle } from "lucide-react";

interface ResetConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  isLoading: boolean;
}

export function ResetConfirmDialog({
  open,
  onOpenChange,
  onConfirm,
  isLoading,
}: ResetConfirmDialogProps) {
  const { t } = useTranslation();

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content maxWidth="400px">
        <Dialog.Title>{t("promptChains.resetToDefault")}</Dialog.Title>
        <Dialog.Description>
          <Flex direction="column" gap="3">
            <Flex align="center" gap="2">
              <AlertTriangle size={20} color="var(--red-9)" />
              <Text size="2" color="red">
                {t("promptChains.resetWarningTitle")}
              </Text>
            </Flex>
            <Text size="2">
              {t("promptChains.resetWarningDescription")}
            </Text>
          </Flex>
        </Dialog.Description>

        <Flex gap="3" mt="4" justify="end">
          <Button
            variant="soft"
            color="gray"
            onClick={() => onOpenChange(false)}
            disabled={isLoading}
          >
            {t("common.cancel")}
          </Button>
          <Button
            variant="solid"
            color="red"
            onClick={() => {
              onConfirm();
            }}
            disabled={isLoading}
          >
            {isLoading ? t("common.processing") : t("promptChains.resetConfirm")}
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}
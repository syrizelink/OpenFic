/**
 * ConfirmDialog Component
 *
 * 可复用的确认对话框组件，用于删除确认等场景。
 */

import { AlertDialog, Button, Flex, Text } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";

interface ConfirmDialogProps {
  /** 是否打开对话框 */
  open: boolean;
  /** 关闭对话框回调 */
  onOpenChange: (open: boolean) => void;
  /** 确认回调 */
  onConfirm: () => void;
  /** 对话框标题 */
  title: string;
  /** 对话框描述 */
  description: string;
  /** 确认按钮文字 */
  confirmText?: string;
  /** 取消按钮文字 */
  cancelText?: string;
  /** 确认按钮颜色 */
  confirmColor?: "red" | "blue" | "green";
  /** 是否处于加载状态 */
  loading?: boolean;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  onConfirm,
  title,
  description,
  confirmText,
  cancelText,
  confirmColor = "red",
  loading = false,
}: ConfirmDialogProps) {
  const { t } = useTranslation();

  const handleConfirm = () => {
    onConfirm();
  };

  return (
    <AlertDialog.Root
      open={open}
      onOpenChange={onOpenChange}
    >
      <AlertDialog.Content maxWidth="400px">
        <AlertDialog.Title>{title}</AlertDialog.Title>
        <AlertDialog.Description size="2">
          <Text color="gray">{description}</Text>
        </AlertDialog.Description>

        <Flex
          gap="3"
          mt="4"
          justify="end"
        >
          <AlertDialog.Cancel>
            <Button
              variant="soft"
              color="gray"
              disabled={loading}
            >
              {cancelText ?? t("common.cancel")}
            </Button>
          </AlertDialog.Cancel>
          <AlertDialog.Action>
            <Button
              variant="solid"
              color={confirmColor}
              onClick={handleConfirm}
              loading={loading}
            >
              {confirmText ?? t("common.confirm")}
            </Button>
          </AlertDialog.Action>
        </Flex>
      </AlertDialog.Content>
    </AlertDialog.Root>
  );
}

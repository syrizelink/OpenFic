/**
 * ConfirmDialog Component
 *
 * Komponen dialog konfirmasi yang dapat dipakai ulang, misalnya untuk konfirmasi penghapusan.
 */

import { AlertDialog, Button, Flex, Text } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";

interface ConfirmDialogProps {
  /** Status terbuka dialog */
  open: boolean;
  /** Callback penutupan dialog */
  onOpenChange: (open: boolean) => void;
  /** Callback konfirmasi */
  onConfirm: () => void;
  /** Judul dialog */
  title: string;
  /** Deskripsi dialog */
  description: string;
  /** Teks tombol konfirmasi */
  confirmText?: string;
  /** Teks tombol batal */
  cancelText?: string;
  /** Warna tombol konfirmasi */
  confirmColor?: "red" | "blue" | "green";
  /** Status sedang memuat */
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

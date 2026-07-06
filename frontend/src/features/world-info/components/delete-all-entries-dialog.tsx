import { Button, Dialog, Flex } from "@radix-ui/themes";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { useTranslation } from "react-i18next";

import { toast } from "@/components/toast";
import { deleteAllWorldInfoEntries } from "@/lib/api-client";

interface DeleteAllEntriesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  worldInfoId: string;
  onSuccess?: () => void;
}

export function DeleteAllEntriesDialog({
  open,
  onOpenChange,
  worldInfoId,
  onSuccess,
}: DeleteAllEntriesDialogProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const deleteAllMutation = useMutation({
    mutationFn: () => deleteAllWorldInfoEntries(worldInfoId),
    onSuccess: () => {
      toast.success(t("worldInfo.allEntriesDeleted"));
      queryClient.invalidateQueries({
        queryKey: ["world-info-entries", worldInfoId],
      });
      onOpenChange(false);
      onSuccess?.();
    },
    onError: () => {
      toast.error(t("worldInfo.deleteFailed"));
      onOpenChange(false);
    },
  });

  const handleConfirm = useCallback(() => {
    deleteAllMutation.mutate();
  }, [deleteAllMutation]);

  return (
    <Dialog.Root
      open={open}
      onOpenChange={onOpenChange}
    >
      <Dialog.Content style={{ maxWidth: 400 }}>
        <Dialog.Title>{t("worldInfo.deleteAllEntries")}</Dialog.Title>
        <Dialog.Description
          size="2"
          mb="4"
        >
          {t("worldInfo.deleteAllEntriesConfirm")}
        </Dialog.Description>
        <Flex
          gap="3"
          justify="end"
        >
          <Dialog.Close>
            <Button
              variant="soft"
              color="gray"
            >
              {t("common.cancel")}
            </Button>
          </Dialog.Close>
          <Button
            variant="solid"
            color="red"
            onClick={handleConfirm}
            disabled={deleteAllMutation.isPending}
          >
            {t("common.delete")}
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

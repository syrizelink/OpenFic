import { Button, Dialog, Flex, Text } from "@radix-ui/themes";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { SimpleSelect } from "@/components";
import type { ChapterListItem, VolumeWithChapters } from "@/lib/chapter.types";

interface MoveChapterToVolumeDialogProps {
  open: boolean;
  chapters: ChapterListItem[];
  volumes: VolumeWithChapters[];
  onOpenChange: (open: boolean) => void;
  onConfirm: (volumeId: string) => void;
  loading?: boolean;
}

export function MoveChapterToVolumeDialog({
  open,
  chapters,
  volumes,
  onOpenChange,
  onConfirm,
  loading = false,
}: MoveChapterToVolumeDialogProps) {
  const { t } = useTranslation();
  const [selectedVolumeId, setSelectedVolumeId] = useState("");

  useEffect(() => {
    if (!open || chapters.length === 0) return;
    const firstTarget = volumes.find((volume) =>
      chapters.some((chapter) => volume.id !== chapter.volumeId),
    );
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setSelectedVolumeId(firstTarget?.id ?? "");
    });
    return () => {
      cancelled = true;
    };
  }, [chapters, open, volumes]);

  const options = useMemo(
    () =>
      volumes.map((volume) => ({
        value: volume.id,
        label: volume.title || t("volume.untitled"),
        disabled: chapters.every((chapter) => volume.id === chapter.volumeId),
      })),
    [chapters, t, volumes],
  );

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(nextOpen) => {
        if (!loading) onOpenChange(nextOpen);
      }}
    >
      <Dialog.Content maxWidth="420px">
        <Dialog.Title>{t("writing.moveToVolumeDialog.title")}</Dialog.Title>
        <Dialog.Description
          size="2"
          color="gray"
        >
          {t("writing.moveToVolumeDialog.description")}
        </Dialog.Description>

        <Flex
          direction="column"
          gap="3"
          mt="4"
        >
          <Text
            size="2"
            weight="medium"
          >
            {chapters.length === 1
              ? chapters[0]?.title || t("writing.untitledChapter")
              : t("writing.selectedChapters", { count: chapters.length })}
          </Text>
          <SimpleSelect
            value={selectedVolumeId}
            options={options}
            onChange={setSelectedVolumeId}
            placeholder={t("volume.untitled")}
          />
        </Flex>

        <Flex
          justify="end"
          gap="3"
          mt="5"
        >
          <Dialog.Close>
            <Button
              variant="soft"
              color="gray"
              disabled={loading}
            >
              {t("common.cancel")}
            </Button>
          </Dialog.Close>
          <Button
            loading={loading}
            disabled={
              !selectedVolumeId ||
              chapters.every((chapter) => selectedVolumeId === chapter.volumeId)
            }
            onClick={() => onConfirm(selectedVolumeId)}
          >
            {t("common.confirm")}
          </Button>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

import { Box, Flex, SegmentedControl, Text, TextField } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";

import {
  MAX_IMPORT_CHUNK_SIZE,
  MAX_MERGED_VOLUME_TITLE_LENGTH,
  type DocumentImportOptions,
  type ChapterTitleMode,
  type ImportSplitMode,
  type ImportStructureMode,
} from "../lib/import-api";

import "./import-dialog.css";

interface ImportDocumentOptionsProps {
  value: DocumentImportOptions;
  onChange: (options: DocumentImportOptions) => void;
  disabled?: boolean;
}

/** Shared parsing and document-structure controls for document import flows. */
export function ImportDocumentOptions({
  value,
  onChange,
  disabled = false,
}: ImportDocumentOptionsProps) {
  const { t } = useTranslation();

  const updateOptions = (update: Partial<DocumentImportOptions>) => {
    onChange({ ...value, ...update });
  };

  return (
    <Flex
      direction="column"
      gap="4"
      className="import-dialog-split-content"
    >
      <Box>
        <Text
          as="p"
          size="3"
          weight="medium"
          mb="2"
        >
          {t("import.splitMode")}
        </Text>
        <SegmentedControl.Root
          value={value.splitMode}
          onValueChange={(splitMode) => updateOptions({ splitMode: splitMode as ImportSplitMode })}
          size="2"
          disabled={disabled}
          aria-label={t("import.splitMode")}
          className="import-dialog-split-mode"
        >
          <SegmentedControl.Item value="auto">{t("import.autoSplit")}</SegmentedControl.Item>
          <SegmentedControl.Item value="manual">{t("import.manualSplit")}</SegmentedControl.Item>
        </SegmentedControl.Root>
      </Box>

      {value.splitMode === "manual" ? (
        <Box>
          <Text
            as="label"
            htmlFor="document-import-chunk-size"
            size="2"
            weight="medium"
            mb="1"
            className="import-dialog-label"
          >
            {t("import.chunkSize")}
          </Text>
          <TextField.Root
            id="document-import-chunk-size"
            type="number"
            min={1}
            max={MAX_IMPORT_CHUNK_SIZE}
            value={String(value.chunkSize)}
            disabled={disabled}
            onChange={(event) => updateOptions({ chunkSize: Number(event.target.value) })}
          />
          <Text
            as="p"
            size="1"
            color="gray"
            mt="1"
          >
            {t("import.chunkSizeHint", { max: MAX_IMPORT_CHUNK_SIZE })}
          </Text>
        </Box>
      ) : (
        <Text
          as="p"
          size="2"
          color="gray"
          className="import-dialog-split-description"
        >
          {t("import.autoSplitDescription")}
        </Text>
      )}

      <Box>
        <Text
          as="p"
          size="3"
          weight="medium"
          mb="2"
        >
          {t("import.documents.structureMode")}
        </Text>
        <SegmentedControl.Root
          value={value.structureMode}
          onValueChange={(structureMode) =>
            updateOptions({ structureMode: structureMode as ImportStructureMode })
          }
          size="2"
          disabled={disabled}
          aria-label={t("import.documents.structureMode")}
          className="import-dialog-split-mode"
        >
          <SegmentedControl.Item value="separate_volumes">
            {t("import.documents.separateVolumes")}
          </SegmentedControl.Item>
          <SegmentedControl.Item value="merge_volume">
            {t("import.documents.mergeVolume")}
          </SegmentedControl.Item>
        </SegmentedControl.Root>
      </Box>

      {value.structureMode === "merge_volume" && (
        <Flex
          direction="column"
          gap="3"
        >
          <Box>
            <Text
              as="label"
              htmlFor="document-import-merged-volume-title"
              size="2"
              weight="medium"
              mb="1"
              className="import-dialog-label"
            >
              {t("import.documents.mergedVolumeTitle")}
            </Text>
            <TextField.Root
              id="document-import-merged-volume-title"
              value={value.mergedVolumeTitle}
              maxLength={MAX_MERGED_VOLUME_TITLE_LENGTH}
              placeholder={t("import.documents.mergedVolumeTitlePlaceholder")}
              disabled={disabled}
              onChange={(event) => updateOptions({ mergedVolumeTitle: event.target.value })}
            />
          </Box>
          <Box>
            <Text
              as="p"
              size="2"
              weight="medium"
              mb="1"
            >
              {t("import.documents.chapterTitleMode")}
            </Text>
            <SegmentedControl.Root
              value={value.chapterTitleMode}
              onValueChange={(chapterTitleMode) =>
                updateOptions({ chapterTitleMode: chapterTitleMode as ChapterTitleMode })
              }
              size="2"
              disabled={disabled}
              aria-label={t("import.documents.chapterTitleMode")}
              className="import-dialog-split-mode"
            >
              <SegmentedControl.Item value="preserve">
                {t("import.documents.preserveChapterTitles")}
              </SegmentedControl.Item>
              <SegmentedControl.Item value="continuous_numbering">
                {t("import.documents.continuousNumbering")}
              </SegmentedControl.Item>
            </SegmentedControl.Root>
          </Box>
        </Flex>
      )}
    </Flex>
  );
}

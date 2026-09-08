import {
  Badge,
  Box,
  Button,
  Card,
  Dialog,
  Flex,
  Progress,
  ScrollArea,
  Text,
} from "@radix-ui/themes";
import { AlertCircle, Check, ChevronLeft, ChevronRight } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { SimpleSelect } from "@/components";
import { ImportDocumentOptions } from "@/features/projects/components/import-document-options";
import { ImportFileList } from "@/features/projects/components/import-file-list";
import {
  DEFAULT_DOCUMENT_IMPORT_OPTIONS,
  getDocumentImportErrorMessage,
  previewDocuments,
  validateDocumentImportOptions,
  type DocumentImportOptions,
  type ImportPreviewResponse,
} from "@/features/projects/lib/import-api";

import { useImportDocumentsIntoProject } from "../hooks/use-volumes";
import { useWritingStore } from "../store/use-writing-store";

interface ChapterImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  currentVolumeId: string | null;
  onImported: (firstChapterId: string) => void;
}

type Step = "select" | "options" | "preview" | "importing";
type Placement = "append" | "after_volume";

function getImportFileTitle(filename: string): string {
  return filename.replace(/\.(txt|md)$/i, "");
}

/** Import ordered document files as new volumes in an existing writing project. */
export function ChapterImportDialog({
  open,
  onOpenChange,
  projectId,
  currentVolumeId,
  onImported,
}: ChapterImportDialogProps) {
  const { t, i18n } = useTranslation();
  const importMutation = useImportDocumentsIntoProject(projectId);
  const setVolumeExpanded = useWritingStore((state) => state.setVolumeExpanded);
  const [step, setStep] = useState<Step>("select");
  const [files, setFiles] = useState<File[]>([]);
  const [options, setOptions] = useState<DocumentImportOptions>(DEFAULT_DOCUMENT_IMPORT_OPTIONS);
  const [mergedVolumeTitleEdited, setMergedVolumeTitleEdited] = useState(false);
  const [placement, setPlacement] = useState<Placement>("append");
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const previewRequestSequence = useRef(0);

  const resetState = useCallback(() => {
    previewRequestSequence.current += 1;
    setStep("select");
    setFiles([]);
    setOptions(DEFAULT_DOCUMENT_IMPORT_OPTIONS);
    setMergedVolumeTitleEdited(false);
    setPlacement("append");
    setPreview(null);
    setError(null);
  }, []);

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen && importMutation.isPending) return;
      if (!nextOpen) resetState();
      onOpenChange(nextOpen);
    },
    [importMutation.isPending, onOpenChange, resetState],
  );

  const invalidatePreview = useCallback(() => {
    previewRequestSequence.current += 1;
    setPreview(null);
  }, []);

  const handleFilesChange = useCallback(
    (nextFiles: File[]) => {
      invalidatePreview();
      setFiles(nextFiles);
      if (!mergedVolumeTitleEdited) {
        setOptions((currentOptions) => ({
          ...currentOptions,
          mergedVolumeTitle: nextFiles[0] ? getImportFileTitle(nextFiles[0].name) : "",
        }));
      }
      setError(null);
    },
    [invalidatePreview, mergedVolumeTitleEdited],
  );

  const handleOptionsChange = useCallback(
    (nextOptions: DocumentImportOptions) => {
      invalidatePreview();
      if (nextOptions.mergedVolumeTitle !== options.mergedVolumeTitle) {
        setMergedVolumeTitleEdited(true);
      }
      setOptions(nextOptions);
      setError(null);
    },
    [invalidatePreview, options.mergedVolumeTitle],
  );

  const handlePlacementChange = useCallback(
    (nextPlacement: Placement) => {
      invalidatePreview();
      setPlacement(nextPlacement);
      setError(null);
    },
    [invalidatePreview],
  );

  const optionsValidationKey = validateDocumentImportOptions(options);
  const createdVolumeCount = useMemo(
    () => (options.structureMode === "merge_volume" ? 1 : (preview?.volumes.length ?? 0)),
    [options.structureMode, preview?.volumes.length],
  );
  const formatWordCount = useCallback(
    (count: number) =>
      new Intl.NumberFormat(i18n.language, {
        notation: count >= 10_000 ? "compact" : "standard",
        maximumFractionDigits: count >= 10_000 ? 1 : 0,
      }).format(count),
    [i18n.language],
  );

  const handlePreview = useCallback(async () => {
    if (files.length === 0) {
      setError(t("import.documents.invalidFileTotal"));
      return;
    }
    if (optionsValidationKey) {
      setError(t(optionsValidationKey));
      return;
    }

    const requestSequence = previewRequestSequence.current + 1;
    previewRequestSequence.current = requestSequence;
    setError(null);

    try {
      const result = await previewDocuments(files, options);
      if (requestSequence !== previewRequestSequence.current) return;
      setPreview(result);
      setStep("preview");
    } catch (reason) {
      if (requestSequence !== previewRequestSequence.current) return;
      setError(getDocumentImportErrorMessage(reason, t("import.parseFailed")));
    }
  }, [files, options, optionsValidationKey, t]);

  const handleImport = useCallback(async () => {
    if (!preview) return;

    setStep("importing");
    setError(null);

    try {
      const result = await importMutation.mutateAsync({
        files,
        placement:
          placement === "after_volume" && currentVolumeId
            ? { placement: "after_volume", afterVolumeId: currentVolumeId }
            : { placement: "append" },
        options,
      });
      result.created_volume_ids.forEach((volumeId) => setVolumeExpanded(volumeId, true));
      onImported(result.first_chapter_id);
      handleOpenChange(false);
    } catch (reason) {
      setError(getDocumentImportErrorMessage(reason, t("import.importFailed")));
      setStep("preview");
    }
  }, [
    currentVolumeId,
    files,
    handleOpenChange,
    importMutation,
    onImported,
    options,
    placement,
    preview,
    setVolumeExpanded,
    t,
  ]);

  const renderContent = () => {
    if (step === "select") {
      return (
        <ImportFileList
          files={files}
          onChange={handleFilesChange}
        />
      );
    }

    if (step === "options") {
      return (
        <Flex
          direction="column"
          gap="4"
        >
          <ImportDocumentOptions
            value={options}
            onChange={handleOptionsChange}
          />
          <Box>
            <Text
              as="p"
              size="3"
              weight="medium"
              mb="2"
            >
              {t("import.documents.placement")}
            </Text>
            <SimpleSelect
              value={placement}
              onChange={(value) => handlePlacementChange(value as Placement)}
              placeholder={t("import.documents.placement")}
              options={[
                { value: "append", label: t("import.documents.append") },
                {
                  value: "after_volume",
                  label: t("import.documents.afterCurrentVolume"),
                  disabled: !currentVolumeId,
                },
              ]}
            />
          </Box>
          {optionsValidationKey && (
            <Text
              size="2"
              color="red"
            >
              {t(optionsValidationKey)}
            </Text>
          )}
        </Flex>
      );
    }

    if (step === "preview") {
      return (
        <Flex
          direction="column"
          gap="4"
        >
          <Flex gap="3">
            <Card className="import-dialog-stat-card">
              <Text
                as="p"
                size="2"
                color="gray"
              >
                {t("import.documents.createdVolumes")}
              </Text>
              <Text
                size="5"
                weight="bold"
              >
                {createdVolumeCount}
              </Text>
            </Card>
            <Card className="import-dialog-stat-card">
              <Text
                as="p"
                size="2"
                color="gray"
              >
                {t("import.chapterCount")}
              </Text>
              <Text
                size="5"
                weight="bold"
              >
                {preview?.chapter_count ?? 0}
              </Text>
            </Card>
            <Card className="import-dialog-stat-card">
              <Text
                as="p"
                size="2"
                color="gray"
              >
                {t("import.totalWordCount")}
              </Text>
              <Text
                size="5"
                weight="bold"
              >
                {formatWordCount(preview?.total_word_count ?? 0)}
              </Text>
            </Card>
          </Flex>
          <Box
            className="import-dialog-preview-panel"
            style={{ height: "clamp(180px, 30vh, 260px)" }}
          >
            <ScrollArea style={{ height: "100%" }}>
              <Flex
                direction="column"
                gap="3"
                p="3"
              >
                {preview?.volumes.map((volume, volumeIndex) => (
                  <Box key={`${volumeIndex}-${volume.title}`}>
                    <Flex
                      align="center"
                      justify="between"
                      gap="2"
                      mb="1"
                    >
                      <Text
                        size="2"
                        weight="medium"
                      >
                        {volume.title}
                      </Text>
                      <Badge
                        size="1"
                        color="gray"
                      >
                        {volume.chapter_count} {t("projects.chapters")}
                      </Badge>
                    </Flex>
                    <Flex direction="column">
                      {volume.chapters.map((chapter, chapterIndex) => (
                        <Box
                          key={`${chapterIndex}-${chapter.title}`}
                          py="2"
                          style={
                            chapterIndex < volume.chapters.length - 1
                              ? { borderBottom: "1px solid var(--gray-a4)" }
                              : undefined
                          }
                        >
                          <Text
                            size="2"
                            weight="medium"
                          >
                            {chapter.title}
                          </Text>
                          <Text
                            as="p"
                            size="1"
                            color="gray"
                            mt="1"
                            style={{ whiteSpace: "pre-wrap" }}
                          >
                            {chapter.content_preview}
                          </Text>
                        </Box>
                      ))}
                    </Flex>
                  </Box>
                ))}
              </Flex>
            </ScrollArea>
          </Box>
        </Flex>
      );
    }

    return (
      <Box style={{ textAlign: "center", padding: "48px 24px" }}>
        <Text
          as="p"
          size="3"
          weight="medium"
          mb="2"
        >
          {t("import.importing")}
        </Text>
        <Progress
          value={null}
          max={100}
          size="2"
        />
      </Box>
    );
  };

  const renderFooter = () => {
    if (step === "select") {
      return (
        <>
          <Button
            variant="soft"
            color="gray"
            onClick={() => handleOpenChange(false)}
          >
            {t("import.close")}
          </Button>
          <Button
            disabled={files.length === 0}
            onClick={() => setStep("options")}
          >
            {t("import.next")}
            <ChevronRight size={16} />
          </Button>
        </>
      );
    }
    if (step === "options") {
      return (
        <>
          <Button
            variant="soft"
            color="gray"
            onClick={() => setStep("select")}
          >
            <ChevronLeft size={16} />
            {t("import.back")}
          </Button>
          <Button
            disabled={files.length === 0 || Boolean(optionsValidationKey)}
            onClick={() => void handlePreview()}
          >
            {t("import.next")}
            <ChevronRight size={16} />
          </Button>
        </>
      );
    }
    if (step === "preview") {
      return (
        <>
          <Button
            variant="soft"
            color="gray"
            onClick={() => setStep("options")}
          >
            <ChevronLeft size={16} />
            {t("import.back")}
          </Button>
          <Button onClick={() => void handleImport()}>
            <Check size={16} />
            {t("import.startImport")}
          </Button>
        </>
      );
    }
    return null;
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={handleOpenChange}
    >
      <Dialog.Content maxWidth="640px">
        <Dialog.Title>{t("projects.import")}</Dialog.Title>
        <Dialog.Description
          size="2"
          color="gray"
          mb="4"
        >
          {step === "select"
            ? t("import.selectFile")
            : step === "options"
              ? t("import.documents.placement")
              : step === "preview"
                ? t("import.parseResult")
                : t("import.importing")}
        </Dialog.Description>

        {renderContent()}

        {error && step !== "select" && (
          <Flex
            align="center"
            gap="2"
            mt="3"
          >
            <AlertCircle
              size={14}
              color="var(--red-9)"
            />
            <Text
              size="2"
              color="red"
            >
              {error}
            </Text>
          </Flex>
        )}

        {step !== "importing" && (
          <Flex
            justify="between"
            gap="3"
            mt="5"
          >
            {renderFooter()}
          </Flex>
        )}
      </Dialog.Content>
    </Dialog.Root>
  );
}

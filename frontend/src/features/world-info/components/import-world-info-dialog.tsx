import {
  Badge,
  Box,
  Button,
  Card,
  Dialog,
  Flex,
  Progress,
  SegmentedControl,
  ScrollArea,
  Text,
} from "@radix-ui/themes";
import { AlertCircle, Check, ChevronLeft, ChevronRight, FileJson, Upload } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";

import "./import-world-info-dialog.css";

import { importWorldInfoEntriesStream, previewWorldInfoImport } from "@/lib/api-client";
import type { WorldInfoImportMode, WorldInfoImportPreviewResponse } from "@/lib/world-info.types";

interface ImportWorldInfoDialogProps {
  open: boolean;
  worldInfoId: string | null;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (importedCount: number) => void;
}

type Step = "select" | "preview" | "importing" | "complete";

export function ImportWorldInfoDialog({
  open,
  worldInfoId,
  onOpenChange,
  onSuccess,
}: ImportWorldInfoDialogProps) {
  const { t } = useTranslation();
  const [step, setStep] = useState<Step>("select");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<WorldInfoImportPreviewResponse | null>(null);
  const [mode, setMode] = useState<WorldInfoImportMode>("append");
  const [importProgress, setImportProgress] = useState(0);
  const [importStage, setImportStage] = useState("");
  const [currentEntry, setCurrentEntry] = useState(0);
  const [totalEntries, setTotalEntries] = useState(0);
  const [importedCount, setImportedCount] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetState = useCallback(() => {
    setStep("select");
    setLoading(false);
    setError(null);
    setFile(null);
    setPreviewData(null);
    setMode("append");
    setImportProgress(0);
    setImportStage("");
    setCurrentEntry(0);
    setTotalEntries(0);
    setImportedCount(0);
  }, []);

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen) {
        resetState();
      }
      onOpenChange(nextOpen);
    },
    [onOpenChange, resetState],
  );

  const handleFileSelect = useCallback(
    async (selectedFile: File) => {
      if (!selectedFile.name.toLowerCase().endsWith(".json")) {
        setError(t("worldInfo.importInvalidFileType"));
        return;
      }

      setLoading(true);
      setError(null);
      setFile(selectedFile);

      try {
        const result = await previewWorldInfoImport(selectedFile);
        setPreviewData(result);
        setStep("preview");
      } catch (importError) {
        const message =
          importError instanceof Error ? importError.message : t("worldInfo.importParseFailed");
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    [t],
  );

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const droppedFile = event.dataTransfer.files[0];
      if (droppedFile) {
        void handleFileSelect(droppedFile);
      }
    },
    [handleFileSelect],
  );

  const handleImport = useCallback(async () => {
    if (!worldInfoId || !file) {
      return;
    }

    setLoading(true);
    setError(null);
    setImportProgress(0);
    setCurrentEntry(0);
    setTotalEntries(previewData?.entryCount ?? 0);
    setStep("importing");

    try {
      const result = await importWorldInfoEntriesStream(worldInfoId, file, mode, (event) => {
        if (event.type === "progress") {
          setImportProgress(event.progress);
          setImportStage(event.stage);
          setCurrentEntry(event.current ?? 0);
          setTotalEntries(event.total ?? previewData?.entryCount ?? 0);
          return;
        }

        if (event.type === "complete") {
          setImportedCount(event.imported_count);
        }
      });

      if (result) {
        setImportedCount(result.imported_count);
        setStep("complete");
        onSuccess?.(result.imported_count);
      }
    } catch (importError) {
      const message =
        importError instanceof Error ? importError.message : t("worldInfo.importFailed");
      setError(message);
      setStep("preview");
    } finally {
      setLoading(false);
    }
  }, [file, mode, onSuccess, previewData?.entryCount, t, worldInfoId]);

  const getStageLabel = useCallback(() => {
    if (importStage === "reading") return t("worldInfo.importReading");
    if (importStage === "parsing") return t("worldInfo.importParsing");
    if (importStage === "importing_entries") return t("worldInfo.importingEntries");
    return t("worldInfo.importInProgress");
  }, [importStage, t]);

  const renderStepContent = () => {
    switch (step) {
      case "select":
        return (
          <Box>
            <input
              className="world-info-import-file-input"
              ref={fileInputRef}
              type="file"
              accept=".json,application/json"
              onChange={(event) => {
                const selectedFile = event.target.files?.[0];
                if (selectedFile) {
                  void handleFileSelect(selectedFile);
                }
              }}
            />
            <Box
              className="world-info-import-dropzone"
              onDragOver={(event) => event.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload
                size={48}
                className="world-info-import-upload-icon"
              />
              <Text
                as="p"
                size="3"
                weight="medium"
                mb="2"
              >
                {t("worldInfo.importDragDropHint")}
              </Text>
              <Text
                as="p"
                size="2"
                color="gray"
              >
                {t("worldInfo.importSupportedFormats")}
              </Text>
            </Box>

            {loading && (
              <Flex
                align="center"
                gap="2"
                mt="4"
                justify="center"
              >
                <Spinner size={18} />
                <Text
                  size="2"
                  color="gray"
                >
                  {t("worldInfo.importParsing")}
                </Text>
              </Flex>
            )}
          </Box>
        );

      case "preview":
        return (
          <Box>
            {previewData && (
              <>
                <Flex
                  gap="4"
                  mb="4"
                >
                  <Card className="world-info-import-stat-card">
                    <Text
                      size="2"
                      color="gray"
                      mb="1"
                      className="world-info-import-block-label"
                    >
                      {t("worldInfo.importEntryCount")}
                    </Text>
                    <Text
                      size="5"
                      weight="bold"
                    >
                      {previewData.entryCount}
                    </Text>
                  </Card>
                  <Card className="world-info-import-stat-card">
                    <Text
                      size="2"
                      color="gray"
                      mb="1"
                      className="world-info-import-block-label"
                    >
                      {t("worldInfo.importEnabledCount")}
                    </Text>
                    <Text
                      size="5"
                      weight="bold"
                    >
                      {previewData.enabledCount}
                    </Text>
                  </Card>
                </Flex>

                <Text
                  size="2"
                  weight="medium"
                  mb="2"
                  className="world-info-import-preview-title"
                >
                  {t("worldInfo.importPreview")}
                </Text>
                <Box mb="4">
                  <Text
                    size="2"
                    weight="medium"
                    mb="2"
                    as="p"
                  >
                    {t("worldInfo.importMode")}
                  </Text>
                  <SegmentedControl.Root
                    value={mode}
                    onValueChange={(value) => setMode(value as WorldInfoImportMode)}
                    size="2"
                  >
                    <SegmentedControl.Item value="append">
                      {t("worldInfo.importModeAppend")}
                    </SegmentedControl.Item>
                    <SegmentedControl.Item value="overwrite">
                      {t("worldInfo.importModeOverwrite")}
                    </SegmentedControl.Item>
                  </SegmentedControl.Root>
                  <Text
                    as="p"
                    size="1"
                    color="gray"
                    mt="2"
                  >
                    {mode === "append"
                      ? t("worldInfo.importModeAppendDesc")
                      : t("worldInfo.importModeOverwriteDesc")}
                  </Text>
                </Box>
                <ScrollArea className="world-info-import-preview-scroll">
                  <Box p="2">
                    {previewData.entries.map((entry, index) => (
                      <Box
                        key={`${entry.uid}-${index}`}
                        py="2"
                        px="2"
                        className={
                          index < previewData.entries.length - 1
                            ? "world-info-import-preview-row--bordered"
                            : undefined
                        }
                      >
                        <Flex
                          align="center"
                          gap="2"
                          mb="1"
                        >
                          <FileJson
                            size={16}
                            color="var(--gray-9)"
                          />
                          <Text
                            size="2"
                            weight="medium"
                            className="world-info-import-preview-name"
                            truncate
                          >
                            {entry.name}
                          </Text>
                          <Badge
                            size="1"
                            color={entry.isEnabled ? "green" : "gray"}
                          >
                            {entry.isEnabled ? t("worldInfo.enabled") : t("worldInfo.disabled")}
                          </Badge>
                        </Flex>
                        <Text
                          size="1"
                          color="gray"
                          className="world-info-import-preview-meta"
                        >
                          UID: {entry.uid}
                        </Text>
                        {entry.contentPreview && (
                          <Text
                            size="1"
                            color="gray"
                            mt="1"
                            className="world-info-import-preview-content"
                          >
                            {entry.contentPreview}
                          </Text>
                        )}
                      </Box>
                    ))}
                  </Box>
                </ScrollArea>
              </>
            )}
          </Box>
        );

      case "importing":
        return (
          <Box className="world-info-import-progress">
            <Text
              as="p"
              size="3"
              weight="medium"
              mb="2"
            >
              {t("worldInfo.importInProgress")}
            </Text>
            <Text
              as="p"
              size="2"
              color="gray"
              mb="4"
            >
              {getStageLabel()}
            </Text>
            <Progress
              value={importProgress}
              max={100}
              size="2"
            />
            <Text
              as="p"
              size="1"
              color="gray"
              mt="2"
            >
              {importProgress}%
            </Text>
            {totalEntries > 0 && (
              <Text
                as="p"
                size="2"
                color="gray"
                mt="3"
              >
                {t("worldInfo.importProgressDetail", {
                  current: Math.min(currentEntry, totalEntries),
                  total: totalEntries,
                })}
              </Text>
            )}
          </Box>
        );

      case "complete":
        return (
          <Box className="world-info-import-complete">
            <Box className="world-info-import-complete-icon">
              <Check
                size={32}
                color="var(--green-9)"
              />
            </Box>
            <Text
              as="p"
              size="5"
              weight="bold"
              mb="2"
            >
              {t("worldInfo.importSuccess")}
            </Text>
            <Text
              as="p"
              size="2"
              color="gray"
            >
              {t("worldInfo.importedEntriesInfo", { count: importedCount })}
            </Text>
          </Box>
        );
    }
  };

  const renderFooter = () => {
    switch (step) {
      case "select":
        return (
          <Button
            variant="soft"
            color="gray"
            onClick={() => handleOpenChange(false)}
          >
            {t("import.close")}
          </Button>
        );
      case "preview":
        return (
          <Flex
            gap="3"
            justify="between"
            className="world-info-import-preview-footer"
          >
            <Button
              variant="soft"
              color="gray"
              onClick={() => setStep("select")}
            >
              <ChevronLeft size={16} />
              {t("import.back")}
            </Button>
            <Button
              onClick={handleImport}
              disabled={!file || !worldInfoId}
              loading={loading}
            >
              {t("worldInfo.startImport")}
              <ChevronRight size={16} />
            </Button>
          </Flex>
        );
      case "importing":
        return null;
      case "complete":
        return <Button onClick={() => handleOpenChange(false)}>{t("import.finish")}</Button>;
    }
  };

  const getStepTitle = () => {
    switch (step) {
      case "select":
        return t("worldInfo.importSelectFile");
      case "preview":
        return t("worldInfo.importPreview");
      case "importing":
        return t("worldInfo.importInProgress");
      case "complete":
        return t("worldInfo.importSuccess");
    }
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={handleOpenChange}
    >
      <Dialog.Content maxWidth="640px">
        <Dialog.Title>{t("worldInfo.importTitle")}</Dialog.Title>
        <Dialog.Description
          size="2"
          color="gray"
          mb="4"
        >
          {getStepTitle()}
        </Dialog.Description>

        {renderStepContent()}

        {error && (
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

        <Flex
          gap="3"
          mt="5"
          justify="end"
        >
          {renderFooter()}
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

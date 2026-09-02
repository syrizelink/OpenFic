import { Badge, Box, Button, Card, Dialog, Flex, Progress, Text } from "@radix-ui/themes";
import axios from "axios";
import {
  AlertCircle,
  Archive,
  Check,
  ChevronLeft,
  ChevronRight,
  FileText,
  Upload,
} from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";
import { importNotes, previewNoteImport } from "@/lib/api-client";
import type { NoteImportPreview, NoteImportResult } from "@/lib/note.types";

import "./note-import-dialog.css";

interface NoteImportDialogProps {
  open: boolean;
  projectId: string;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (result: NoteImportResult) => void;
}

type NoteImportStep = "select" | "preview" | "importing" | "complete";

interface ApiErrorPayload {
  detail?: unknown;
}

function getImportErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<ApiErrorPayload>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
  }
  return error instanceof Error ? error.message : fallback;
}

function isSupportedNoteImportFile(file: File): boolean {
  return /\.(md|zip)$/i.test(file.name);
}

export function NoteImportDialog({
  open,
  projectId,
  onOpenChange,
  onSuccess,
}: NoteImportDialogProps) {
  const { t } = useTranslation();
  const [step, setStep] = useState<NoteImportStep>("select");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<NoteImportPreview | null>(null);
  const [result, setResult] = useState<NoteImportResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetState = useCallback(() => {
    setStep("select");
    setFile(null);
    setPreview(null);
    setResult(null);
    setIsLoading(false);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen) resetState();
      onOpenChange(nextOpen);
    },
    [onOpenChange, resetState],
  );

  const handleFileSelect = useCallback(
    async (selectedFile: File) => {
      if (!isSupportedNoteImportFile(selectedFile)) {
        setError(t("writing.noteImport.invalidFileType"));
        return;
      }

      setFile(selectedFile);
      setPreview(null);
      setError(null);
      setIsLoading(true);

      try {
        const nextPreview = await previewNoteImport(projectId, selectedFile);
        setPreview(nextPreview);
        setStep("preview");
      } catch (importError) {
        setError(getImportErrorMessage(importError, t("writing.noteImport.parseFailed")));
      } finally {
        setIsLoading(false);
      }
    },
    [projectId, t],
  );

  const handleDrop = useCallback(
    (event: React.DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      const droppedFile = event.dataTransfer.files[0];
      if (droppedFile) void handleFileSelect(droppedFile);
    },
    [handleFileSelect],
  );

  const handleImport = useCallback(async () => {
    if (!file) return;
    setStep("importing");
    setIsLoading(true);
    setError(null);

    try {
      const importResult = await importNotes(projectId, file);
      setResult(importResult);
      setStep("complete");
      onSuccess?.(importResult);
    } catch (importError) {
      setError(getImportErrorMessage(importError, t("writing.noteImport.importFailed")));
      setStep("preview");
    } finally {
      setIsLoading(false);
    }
  }, [file, onSuccess, projectId, t]);

  const handleBackToSelect = useCallback(() => {
    setStep("select");
    setFile(null);
    setPreview(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const getStepTitle = () => {
    switch (step) {
      case "select":
        return t("writing.noteImport.selectFile");
      case "preview":
        return t("writing.noteImport.preview");
      case "importing":
        return t("writing.noteImport.importing");
      case "complete":
        return t("writing.noteImport.success");
    }
  };

  const renderStepContent = () => {
    switch (step) {
      case "select":
        return (
          <Box>
            <input
              ref={fileInputRef}
              className="note-import-file-input"
              type="file"
              accept=".md,.zip"
              onChange={(event) => {
                const selectedFile = event.target.files?.[0];
                if (selectedFile) void handleFileSelect(selectedFile);
              }}
            />
            <Box
              className="note-import-dropzone"
              onDragOver={(event) => event.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload
                size={48}
                className="note-import-upload-icon"
              />
              <Text
                as="p"
                size="3"
                weight="medium"
                mb="2"
              >
                {t("writing.noteImport.dragDropHint")}
              </Text>
              <Text
                as="p"
                size="2"
                color="gray"
              >
                {t("writing.noteImport.supportedFormats")}
              </Text>
            </Box>
            {isLoading && (
              <Flex
                align="center"
                justify="center"
                gap="2"
                mt="4"
              >
                <Spinner size={18} />
                <Text
                  size="2"
                  color="gray"
                >
                  {t("writing.noteImport.parsing")}
                </Text>
              </Flex>
            )}
          </Box>
        );
      case "preview":
        return (
          <Box>
            {preview && file && (
              <>
                <Flex
                  className="note-import-preview-stats"
                  mb="4"
                >
                  <Card className="note-import-stat-card">
                    <Text
                      size="2"
                      color="gray"
                      mb="1"
                      className="note-import-stat-label"
                    >
                      {t("writing.noteImport.noteCount")}
                    </Text>
                    <Text
                      size="5"
                      weight="bold"
                    >
                      {preview.noteCount}
                    </Text>
                  </Card>
                  <Card className="note-import-stat-card">
                    <Text
                      size="2"
                      color="gray"
                      mb="1"
                      className="note-import-stat-label"
                    >
                      {t("writing.noteImport.categoryCount")}
                    </Text>
                    <Text
                      size="5"
                      weight="bold"
                    >
                      {preview.categoryCount}
                    </Text>
                  </Card>
                </Flex>
                <Flex
                  align="center"
                  gap="2"
                  mb="3"
                >
                  {preview.fileType === "zip" ? <Archive size={18} /> : <FileText size={18} />}
                  <Text
                    size="2"
                    weight="medium"
                    className="note-import-preview-file"
                  >
                    {file.name}
                  </Text>
                  <Badge
                    size="1"
                    color={preview.fileType === "zip" ? "blue" : "gray"}
                  >
                    .{preview.fileType}
                  </Badge>
                </Flex>
                {preview.ignoredFileCount > 0 && (
                  <Text
                    size="2"
                    color="gray"
                    className="note-import-preview-hint"
                  >
                    {t("writing.noteImport.ignoredFileCount", {
                      count: preview.ignoredFileCount,
                    })}
                  </Text>
                )}
                <Text
                  size="2"
                  color="gray"
                  className="note-import-preview-hint"
                >
                  {t("writing.noteImport.rootImportHint")}
                </Text>
              </>
            )}
          </Box>
        );
      case "importing":
        return (
          <Box className="note-import-progress">
            <Spinner size={32} />
            <Text
              as="p"
              size="3"
              weight="medium"
              mt="4"
            >
              {t("writing.noteImport.importing")}
            </Text>
            <Progress
              value={100}
              max={100}
              size="2"
              mt="4"
            />
          </Box>
        );
      case "complete":
        return (
          <Flex
            direction="column"
            align="center"
            justify="center"
            className="note-import-complete"
          >
            <Flex
              align="center"
              justify="center"
              className="note-import-complete-icon"
            >
              <Check
                size={32}
                color="var(--green-9)"
              />
            </Flex>
            <Text
              as="p"
              size="5"
              weight="bold"
              mb="2"
            >
              {t("writing.noteImport.success")}
            </Text>
            {result && (
              <Text
                as="p"
                size="2"
                color="gray"
              >
                {t("writing.noteImport.successInfo", {
                  notes: result.importedNoteCount,
                  categories: result.importedCategoryCount,
                })}
              </Text>
            )}
          </Flex>
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
            {t("common.close")}
          </Button>
        );
      case "preview":
        return (
          <Flex
            className="note-import-footer"
            justify="between"
          >
            <Button
              variant="soft"
              color="gray"
              onClick={handleBackToSelect}
            >
              <ChevronLeft size={16} />
              {t("common.back")}
            </Button>
            <Button
              loading={isLoading}
              onClick={() => void handleImport()}
            >
              {t("writing.noteImport.startImport")}
              <ChevronRight size={16} />
            </Button>
          </Flex>
        );
      case "importing":
        return null;
      case "complete":
        return <Button onClick={() => handleOpenChange(false)}>{t("common.close")}</Button>;
    }
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={handleOpenChange}
    >
      <Dialog.Content maxWidth="560px">
        <Dialog.Title>{t("writing.noteImport.title")}</Dialog.Title>
        {step !== "complete" && (
          <Dialog.Description
            size="2"
            color="gray"
            mb="4"
          >
            {getStepTitle()}
          </Dialog.Description>
        )}

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

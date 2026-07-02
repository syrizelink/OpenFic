import { useCallback, useRef, useState } from "react";
import {
  Badge,
  Box,
  Button,
  Dialog,
  Flex,
  ScrollArea,
  Text,
} from "@radix-ui/themes";
import { Spinner } from "@/components";
import {
  AlertCircle,
  Check,
  ChevronLeft,
  FileText,
  Upload,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import type { SkillCreate } from "@/lib/skill.types";
import { parseSkillMarkdown } from "../lib/skill-import";
import "./import-skill-dialog.css";

interface ImportSkillDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreate: (payload: SkillCreate) => void;
}

type Step = "select" | "preview" | "complete";

interface PreviewState {
  payload: SkillCreate;
  fileName: string;
  isRecognized: boolean;
}

export function ImportSkillDialog({
  open,
  onOpenChange,
  onCreate,
}: ImportSkillDialogProps) {
  const { t } = useTranslation();
  const [step, setStep] = useState<Step>("select");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetState = useCallback(() => {
    setStep("select");
    setLoading(false);
    setError(null);
    setPreview(null);
  }, []);

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (!nextOpen) {
        resetState();
      }
      onOpenChange(nextOpen);
    },
    [onOpenChange, resetState]
  );

  const handleFileSelect = useCallback(
    async (selectedFile: File) => {
      if (!selectedFile.name.toLowerCase().endsWith(".md")) {
        setError(t("settingsExtra.skills.importDialog.invalidFileType"));
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const text = await selectedFile.text();
        const payload = parseSkillMarkdown(text);
        const isRecognized = !!(payload.name || payload.summary);

        if (!payload.name) {
          payload.name = selectedFile.name.replace(/\.md$/i, "");
        }

        setPreview({ payload, fileName: selectedFile.name, isRecognized });
        setStep("preview");
      } catch {
        setError(t("settingsExtra.skills.importDialog.readFailed"));
      } finally {
        setLoading(false);
      }
    },
    [t]
  );

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const droppedFile = event.dataTransfer.files[0];
      if (droppedFile) {
        void handleFileSelect(droppedFile);
      }
    },
    [handleFileSelect]
  );

  const handleConfirm = useCallback(() => {
    if (!preview) return;
    onCreate(preview.payload);
    setStep("complete");
  }, [preview, onCreate]);

  const renderStepContent = () => {
    switch (step) {
      case "select":
        return (
          <Box>
            <input
              className="import-skill-file-input"
              ref={fileInputRef}
              type="file"
              accept=".md"
              onChange={(event) => {
                const selectedFile = event.target.files?.[0];
                if (selectedFile) {
                  void handleFileSelect(selectedFile);
                }
              }}
            />
            <Box
              className="import-skill-dropzone"
              onDragOver={(event) => event.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload size={48} className="import-skill-upload-icon" />
              <Text as="p" size="3" weight="medium" mb="2">
                {t("settingsExtra.skills.importDialog.dropzoneTitle")}
              </Text>
              <Text as="p" size="2" color="gray">
                {t("settingsExtra.skills.importDialog.dropzoneDescription")}
              </Text>
            </Box>

            {loading && (
              <Flex align="center" gap="2" mt="4" justify="center">
                <Spinner size={18} />
                <Text size="2" color="gray">
                  {t("settingsExtra.skills.importDialog.parsing")}
                </Text>
              </Flex>
            )}
          </Box>
        );

      case "preview":
        return (
          <Box>
            {preview && (
              <ScrollArea className="import-skill-preview-scroll">
                <Flex gap="3" mb="3" align="center">
                  <FileText size={16} color="var(--gray-9)" />
                  <Text size="2" weight="medium" truncate style={{ flex: 1 }}>
                    {preview.fileName}
                  </Text>
                  <Badge size="1" color={preview.isRecognized ? "green" : "amber"}>
                    {preview.isRecognized
                      ? t("settingsExtra.skills.importDialog.recognized")
                      : t("settingsExtra.skills.importDialog.unrecognized")}
                  </Badge>
                </Flex>

                <Flex direction="column" gap="3">
                  <Box>
                    <Text size="1" color="gray" mb="1" className="import-skill-label">
                      {t("settingsExtra.skills.name")}
                    </Text>
                    <Text size="2">
                      {preview.payload.name || t("settingsExtra.skills.importDialog.emptyValue")}
                    </Text>
                  </Box>

                  {preview.payload.skillId && (
                    <Box>
                      <Text size="1" color="gray" mb="1" className="import-skill-label">
                        {t("settingsExtra.skills.id")}
                      </Text>
                      <Text size="2">
                        {preview.payload.skillId}
                      </Text>
                    </Box>
                  )}

                  {preview.payload.summary && (
                    <Box>
                      <Text size="1" color="gray" mb="1" className="import-skill-label">
                        {t("settingsExtra.skills.summary")}
                      </Text>
                      <ScrollArea className="import-skill-summary-preview">
                        <Text size="2" style={{ whiteSpace: "pre-wrap" }}>
                          {preview.payload.summary}
                        </Text>
                      </ScrollArea>
                    </Box>
                  )}

                  {preview.payload.content && (
                    <Box>
                      <Text size="1" color="gray" mb="1" className="import-skill-label">
                        {t("settingsExtra.skills.importDialog.contentPreview")}
                      </Text>
                      <ScrollArea className="import-skill-content-preview">
                        <Box p="2">
                          <Text size="2" style={{ whiteSpace: "pre-wrap" }}>
                            {preview.payload.content.length > 2000
                              ? preview.payload.content.slice(0, 2000) + "..."
                              : preview.payload.content}
                          </Text>
                        </Box>
                      </ScrollArea>
                    </Box>
                  )}
                </Flex>

                {!preview.isRecognized && (
                  <Flex align="center" gap="2" mt="3">
                    <AlertCircle size={14} color="var(--amber-9)" />
                    <Text size="1" color="amber">
                      {t("settingsExtra.skills.importDialog.unrecognizedHint")}
                    </Text>
                  </Flex>
                )}
              </ScrollArea>
            )}
          </Box>
        );

      case "complete":
        return (
          <Box className="import-skill-complete">
            <Box className="import-skill-complete-icon">
              <Check size={32} color="var(--green-9)" />
            </Box>
            <Text as="p" size="5" weight="bold" mb="2">
              {t("settingsExtra.skills.importDialog.successTitle")}
            </Text>
            <Text as="p" size="2" color="gray">
              {t("settingsExtra.skills.importDialog.successDescription", {
                name: preview?.payload.name,
              })}
            </Text>
          </Box>
        );
    }
  };

  const renderFooter = () => {
    switch (step) {
      case "select":
        return (
          <Button variant="soft" color="gray" onClick={() => handleOpenChange(false)}>
            {t("common.close")}
          </Button>
        );
      case "preview":
        return (
          <Flex gap="3" justify="between" className="import-skill-preview-footer">
            <Button variant="soft" color="gray" onClick={() => setStep("select")}>
              <ChevronLeft size={16} />
              {t("common.back")}
            </Button>
            <Button onClick={handleConfirm}>{t("settingsExtra.skills.importDialog.confirmImport")}</Button>
          </Flex>
        );
      case "complete":
        return <Button onClick={() => handleOpenChange(false)}>{t("import.finish")}</Button>;
    }
  };

  const getStepTitle = () => {
    switch (step) {
      case "select":
        return t("settingsExtra.skills.importDialog.selectTitle");
      case "preview":
        return t("settingsExtra.skills.importDialog.previewTitle");
      case "complete":
        return t("settingsExtra.skills.importDialog.completeTitle");
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={handleOpenChange}>
      <Dialog.Content maxWidth="680px">
        <Dialog.Title>{t("settingsExtra.skills.importSkill")}</Dialog.Title>
        <Dialog.Description size="2" color="gray" mb="4">
          {getStepTitle()}
        </Dialog.Description>

        {renderStepContent()}

        {error && (
          <Flex align="center" gap="2" mt="3">
            <AlertCircle size={14} color="var(--red-9)" />
            <Text size="2" color="red">
              {error}
            </Text>
          </Flex>
        )}

        <Flex gap="3" mt="5" justify="end">
          {renderFooter()}
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

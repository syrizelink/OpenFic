import { Badge, Box, Button, Dialog, Flex, ScrollArea, Text } from "@radix-ui/themes";
import { AlertCircle, Check, FileText, Upload } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";
import { importSkill } from "@/lib/api-client";
import type { Skill, SkillImportResult } from "@/lib/skill.types";

import "./import-skill-dialog.css";

interface ImportSkillDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: (skill: Skill) => void;
  disabled?: boolean;
}

type Step = "select" | "complete";

export function ImportSkillDialog({
  open,
  onOpenChange,
  onImported,
  disabled = false,
}: ImportSkillDialogProps) {
  const { t } = useTranslation();
  const [step, setStep] = useState<Step>("select");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SkillImportResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetState = useCallback(() => {
    setStep("select");
    setLoading(false);
    setError(null);
    setResult(null);
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
      if (disabled) return;
      const lower = selectedFile.name.toLowerCase();
      if (!lower.endsWith(".md") && !lower.endsWith(".zip")) {
        setError(t("settingsExtra.skills.importDialog.invalidFileType"));
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const importResult = await importSkill(selectedFile);
        setResult(importResult);
        onImported(importResult.skill);
        setStep("complete");
      } catch {
        setError(t("settingsExtra.skills.importDialog.readFailed"));
      } finally {
        setLoading(false);
      }
    },
    [disabled, onImported, t],
  );

  const handleDrop = useCallback(
    (event: React.DragEvent) => {
      if (disabled) return;
      event.preventDefault();
      const droppedFile = event.dataTransfer.files[0];
      if (droppedFile) handleFileSelect(droppedFile);
    },
    [disabled, handleFileSelect],
  );

  const renderSelectStep = () => (
    <Box>
      <input
        className="import-skill-file-input"
        ref={fileInputRef}
        type="file"
        accept=".md,.zip"
        disabled={disabled}
        onChange={(event) => {
          const selectedFile = event.target.files?.[0];
          if (selectedFile) handleFileSelect(selectedFile);
          event.target.value = "";
        }}
      />
      <Box
        className="import-skill-dropzone"
        onDragOver={(event) => {
          if (!disabled) event.preventDefault();
        }}
        onDrop={handleDrop}
        onClick={() => {
          if (!disabled) fileInputRef.current?.click();
        }}
        data-disabled={disabled ? "true" : "false"}
      >
        <Upload
          size={48}
          className="import-skill-upload-icon"
        />
        <Text
          as="p"
          size="3"
          weight="medium"
          mb="2"
        >
          {t("settingsExtra.skills.importDialog.dropzoneTitle")}
        </Text>
        <Text
          as="p"
          size="2"
          color="gray"
        >
          {t("settingsExtra.skills.importDialog.dropzoneDescription")}
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
            {t("settingsExtra.skills.importDialog.parsing")}
          </Text>
        </Flex>
      )}
    </Box>
  );

  const renderCompleteStep = () => {
    if (!result) return null;
    return (
      <ScrollArea className="import-skill-preview-scroll">
        <Flex
          gap="3"
          mb="3"
          align="center"
        >
          <FileText
            size={16}
            color="var(--gray-9)"
          />
          <Text
            size="2"
            weight="medium"
            truncate
            style={{ flex: 1 }}
          >
            {result.skill.name || t("settingsExtra.skills.importDialog.emptyValue")}
          </Text>
          <Badge
            size="1"
            color={result.isRecognized ? "green" : "amber"}
          >
            {result.isRecognized
              ? t("settingsExtra.skills.importDialog.recognized")
              : t("settingsExtra.skills.importDialog.unrecognized")}
          </Badge>
        </Flex>

        {result.skill.summary && (
          <Box mb="3">
            <Text
              size="1"
              color="gray"
              mb="1"
              className="import-skill-label"
            >
              {t("settingsExtra.skills.summary")}
            </Text>
            <Text
              size="2"
              style={{ whiteSpace: "pre-wrap" }}
            >
              {result.skill.summary}
            </Text>
          </Box>
        )}

        {result.referenceDocs.length > 0 && (
          <Box>
            <Text
              size="1"
              color="gray"
              mb="1"
              className="import-skill-label"
            >
              {t("settingsExtra.skills.importDialog.referenceDocsLabel", {
                count: result.referenceDocs.length,
              })}
            </Text>
            <Flex
              direction="column"
              gap="1"
            >
              {result.referenceDocs.map((doc) => (
                <Flex
                  key={doc.id}
                  align="center"
                  justify="between"
                  gap="2"
                >
                  <Flex
                    align="center"
                    gap="2"
                    minWidth="0"
                  >
                    <FileText
                      size={14}
                      color="var(--gray-9)"
                    />
                    <Text
                      size="2"
                      truncate
                    >
                      {doc.title}
                    </Text>
                  </Flex>
                  <Text
                    size="1"
                    color="gray"
                    className="import-skill-refdoc-tokens"
                  >
                    {doc.tokens} {t("settingsExtra.skills.tokens")}
                  </Text>
                </Flex>
              ))}
            </Flex>
          </Box>
        )}
      </ScrollArea>
    );
  };

  const renderStepContent = () => {
    switch (step) {
      case "select":
        return renderSelectStep();
      case "complete":
        return renderCompleteStep();
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
      case "complete":
        return <Button onClick={() => handleOpenChange(false)}>{t("import.finish")}</Button>;
    }
  };

  const getStepTitle = () => {
    switch (step) {
      case "select":
        return t("settingsExtra.skills.importDialog.selectTitle");
      case "complete":
        return t("settingsExtra.skills.importDialog.completeTitle");
    }
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={handleOpenChange}
    >
      <Dialog.Content maxWidth="680px">
        <Dialog.Title>{t("settingsExtra.skills.importSkill")}</Dialog.Title>
        <Dialog.Description
          size="2"
          color="gray"
          mb="4"
        >
          {getStepTitle()}
        </Dialog.Description>

        {step === "complete" && (
          <Flex
            justify="center"
            mb="3"
          >
            <Box className="import-skill-complete-icon">
              <Check
                size={32}
                color="var(--green-9)"
              />
            </Box>
          </Flex>
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

/**
 * ImportDialog Component
 *
 * 多步骤 TXT 文件导入弹窗组件。
 * 步骤：选择文件 → 解析预览 → 填写书名和封面 → 完成
 */

import {
  Dialog,
  Button,
  Flex,
  Text,
  Box,
  TextField,
  TextArea,
  ScrollArea,
  Badge,
  Progress,
  Card,
} from "@radix-ui/themes";
import { Upload, FileText, ChevronLeft, ChevronRight, Check, AlertCircle } from "lucide-react";
import { useState, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";

import "./import-dialog.css";
import { previewTxtFile, confirmImportStream, type ImportPreviewResponse } from "../lib/import-api";
import { CoverCropper } from "./cover-cropper";

interface ImportDialogProps {
  /** 是否打开对话框 */
  open: boolean;
  /** 关闭对话框回调 */
  onOpenChange: (open: boolean) => void;
  /** 导入成功回调 */
  onSuccess?: () => void;
}

type Step = "select" | "preview" | "info" | "importing" | "complete";

export function ImportDialog({ open, onOpenChange, onSuccess }: ImportDialogProps) {
  const { t, i18n } = useTranslation();

  // 步骤状态
  const [step, setStep] = useState<Step>("select");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 文件和解析结果
  const [file, setFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<ImportPreviewResponse | null>(null);

  // 项目信息
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [cover, setCover] = useState<File | null>(null);

  // 导入结果
  const [importResult, setImportResult] = useState<{
    projectId: string;
    chapterCount: number;
    wordCount: number;
  } | null>(null);

  // 文件输入引用
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 导入进度
  const [importProgress, setImportProgress] = useState(0);
  const [importStage, setImportStage] = useState("");

  // 重置状态
  const resetState = useCallback(() => {
    setStep("select");
    setLoading(false);
    setError(null);
    setFile(null);
    setPreviewData(null);
    setTitle("");
    setDescription("");
    setCover(null);
    setImportResult(null);
    setImportProgress(0);
    setImportStage("");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }, []);

  // 处理对话框关闭
  const handleOpenChange = useCallback(
    (newOpen: boolean) => {
      if (!newOpen) {
        resetState();
      }
      onOpenChange(newOpen);
    },
    [onOpenChange, resetState],
  );

  // 处理文件选择
  const handleFileSelect = useCallback(
    async (selectedFile: File) => {
      if (!selectedFile.name.toLowerCase().endsWith(".txt")) {
        setError(t("import.invalidFileType"));
        return;
      }

      setFile(selectedFile);
      setError(null);
      setLoading(true);

      try {
        const result = await previewTxtFile(selectedFile);
        setPreviewData(result);
        setTitle(selectedFile.name.replace(/\.txt$/i, ""));
        setStep("preview");
      } catch (err) {
        console.error("预览失败:", err);
        setError(t("import.parseFailed"));
      } finally {
        setLoading(false);
      }
    },
    [t],
  );

  // 处理文件拖放
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) {
        handleFileSelect(droppedFile);
      }
    },
    [handleFileSelect],
  );

  // 处理确认导入
  const handleConfirmImport = useCallback(async () => {
    if (!file || !title.trim()) {
      setError(t("import.bookTitleRequired"));
      return;
    }

    setLoading(true);
    setError(null);
    setImportProgress(0);
    setStep("importing");

    try {
      const result = await confirmImportStream(
        file,
        title.trim(),
        description.trim() || undefined,
        cover,
        (event) => {
          if (event.type === "progress") {
            setImportProgress(event.progress);
            setImportStage(event.stage);
          }
        },
      );

      if (result) {
        setImportResult({
          projectId: result.project_id,
          chapterCount: result.chapter_count,
          wordCount: result.total_word_count,
        });
        setStep("complete");
        onSuccess?.();
      }
    } catch (err) {
      console.error("导入失败:", err);
      setError(err instanceof Error ? err.message : t("import.importFailed"));
      setStep("info");
    } finally {
      setLoading(false);
    }
  }, [file, title, description, cover, t, onSuccess]);

  // 格式化字数
  const formatWordCount = (count: number) => {
    return new Intl.NumberFormat(i18n.language, {
      notation: count >= 10000 ? "compact" : "standard",
      maximumFractionDigits: count >= 10000 ? 1 : 0,
    }).format(count);
  };

  const getImportStageText = () => {
    switch (importStage) {
      case "reading":
        return t("import.stageReading");
      case "parsing":
        return t("import.stageParsing");
      case "creating_project":
        return t("import.stageCreatingProject");
      case "saving_chapters":
        return t("import.stageSavingChapters");
      default:
        return "";
    }
  };

  // 渲染步骤内容
  const renderStepContent = () => {
    switch (step) {
      case "select":
        return (
          <Box>
            <input
              className="import-dialog-file-input"
              ref={fileInputRef}
              type="file"
              accept=".txt"
              onChange={(e) => {
                const selectedFile = e.target.files?.[0];
                if (selectedFile) {
                  handleFileSelect(selectedFile);
                }
              }}
            />
            <Box
              className="import-dialog-dropzone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload
                size={48}
                className="import-dialog-upload-icon"
              />
              <Text
                as="p"
                size="3"
                weight="medium"
                mb="2"
              >
                {t("import.dragDropHint")}
              </Text>
              <Text
                as="p"
                size="2"
                color="gray"
              >
                {t("import.supportedFormats")}
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
                  {t("import.parsing")}
                </Text>
              </Flex>
            )}

            {error && (
              <Flex
                align="center"
                gap="2"
                mt="4"
                justify="center"
              >
                <AlertCircle
                  size={16}
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
          </Box>
        );

      case "preview":
        return (
          <Box>
            {previewData && (
              <>
                {/* 统计信息 */}
                <Flex
                  gap="4"
                  mb="4"
                >
                  <Card className="import-dialog-stat-card">
                    <Text
                      size="2"
                      color="gray"
                      mb="1"
                      className="import-dialog-label"
                    >
                      {t("import.chapterCount")}
                    </Text>
                    <Text
                      size="5"
                      weight="bold"
                    >
                      {previewData.chapter_count}
                    </Text>
                  </Card>
                  <Card className="import-dialog-stat-card">
                    <Text
                      size="2"
                      color="gray"
                      mb="1"
                      className="import-dialog-label"
                    >
                      {t("import.totalWordCount")}
                    </Text>
                    <Text
                      size="5"
                      weight="bold"
                    >
                      {formatWordCount(previewData.total_word_count)}
                    </Text>
                  </Card>
                </Flex>

                {/* 章节预览列表 */}
                <Text
                  size="2"
                  weight="medium"
                  mb="2"
                  className="import-dialog-section-title"
                >
                  {t("import.chapterPreview")}
                </Text>
                <ScrollArea className="import-dialog-preview-scroll">
                  <Box p="2">
                    {previewData.chapters.map((chapter, index) => (
                      <Flex
                        key={index}
                        align="center"
                        gap="2"
                        py="2"
                        px="2"
                        className={
                          index < previewData.chapters.length - 1
                            ? "import-dialog-preview-row--bordered"
                            : undefined
                        }
                      >
                        <FileText
                          size={16}
                          color="var(--gray-9)"
                        />
                        <Text
                          size="2"
                          className="import-dialog-preview-title"
                          truncate
                        >
                          {chapter.title}
                        </Text>
                        <Badge
                          size="1"
                          color="gray"
                        >
                          {chapter.word_count} {t("projects.words")}
                        </Badge>
                      </Flex>
                    ))}
                  </Box>
                </ScrollArea>

                {previewData.chapter_count === 1 && (
                  <Flex
                    align="center"
                    gap="2"
                    mt="3"
                  >
                    <AlertCircle
                      size={14}
                      color="var(--amber-9)"
                    />
                    <Text
                      size="1"
                      color="amber"
                    >
                      {t("import.noChaptersFound")}
                    </Text>
                  </Flex>
                )}
              </>
            )}
          </Box>
        );

      case "info":
        return (
          <Flex gap="5">
            {/* 左侧：封面 */}
            <Box className="import-dialog-cover-column">
              <CoverCropper
                value={cover}
                onChange={setCover}
              />
            </Box>

            {/* 右侧：项目信息 */}
            <Flex
              direction="column"
              gap="4"
              className="import-dialog-info-content"
            >
              {/* 书名 */}
              <Box>
                <Text
                  as="label"
                  size="2"
                  weight="medium"
                  mb="1"
                  className="import-dialog-label"
                >
                  {t("import.bookTitle")} <Text color="red">*</Text>
                </Text>
                <TextField.Root
                  placeholder={t("import.bookTitlePlaceholder")}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </Box>

              {/* 简介 */}
              <Box>
                <Text
                  as="label"
                  size="2"
                  weight="medium"
                  mb="1"
                  className="import-dialog-label"
                >
                  {t("projectForm.descriptionLabel")}
                </Text>
                <TextArea
                  placeholder={t("projectForm.descriptionPlaceholder")}
                  rows={4}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </Box>

              {/* 导入预览 */}
              {previewData && (
                <Flex gap="3">
                  <Badge size="2">
                    {previewData.chapter_count} {t("projects.chapters")}
                  </Badge>
                  <Badge size="2">
                    {formatWordCount(previewData.total_word_count)} {t("projects.words")}
                  </Badge>
                </Flex>
              )}
            </Flex>
          </Flex>
        );

      case "importing":
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
            <Text
              as="p"
              size="2"
              color="gray"
              mb="4"
            >
              {getImportStageText()}
            </Text>
            <Progress
              value={importProgress}
              max={100}
              size="2"
              style={{ width: "100%" }}
            />
            <Text
              as="p"
              size="1"
              color="gray"
              mt="2"
            >
              {importProgress}%
            </Text>
          </Box>
        );

      case "complete":
        return (
          <Box style={{ textAlign: "center", padding: "24px 0" }}>
            <Box
              style={{
                width: 64,
                height: 64,
                borderRadius: "50%",
                backgroundColor: "var(--green-3)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 16px",
              }}
            >
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
              {t("import.importSuccess")}
            </Text>
            {importResult && (
              <Text
                as="p"
                size="2"
                color="gray"
              >
                {t("import.importedInfo", {
                  chapters: importResult.chapterCount,
                  words: formatWordCount(importResult.wordCount),
                })}
              </Text>
            )}
          </Box>
        );
    }
  };

  // 渲染底部按钮
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
            style={{ width: "100%" }}
          >
            <Button
              variant="soft"
              color="gray"
              onClick={() => setStep("select")}
            >
              <ChevronLeft size={16} />
              {t("import.back")}
            </Button>
            <Button onClick={() => setStep("info")}>
              {t("import.next")}
              <ChevronRight size={16} />
            </Button>
          </Flex>
        );

      case "info":
        return (
          <Flex
            gap="3"
            justify="between"
            style={{ width: "100%" }}
          >
            <Button
              variant="soft"
              color="gray"
              onClick={() => setStep("preview")}
              disabled={loading}
            >
              <ChevronLeft size={16} />
              {t("import.back")}
            </Button>
            <Button
              onClick={handleConfirmImport}
              loading={loading}
              disabled={!title.trim()}
            >
              {t("import.startImport")}
            </Button>
          </Flex>
        );

      case "complete":
        return <Button onClick={() => handleOpenChange(false)}>{t("import.finish")}</Button>;

      case "importing":
        return null;
    }
  };

  // 根据步骤获取标题
  const getStepTitle = () => {
    switch (step) {
      case "select":
        return t("import.selectFile");
      case "preview":
        return t("import.parseResult");
      case "info":
        return t("import.projectInfo");
      case "importing":
        return t("import.importing");
      case "complete":
        return t("import.importSuccess");
    }
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={handleOpenChange}
    >
      <Dialog.Content maxWidth="600px">
        <Dialog.Title>{t("import.title")}</Dialog.Title>
        <Dialog.Description
          size="2"
          color="gray"
          mb="4"
        >
          {getStepTitle()}
        </Dialog.Description>

        {renderStepContent()}

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

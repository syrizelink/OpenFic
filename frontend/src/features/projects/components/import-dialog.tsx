/**
 * ImportDialog Component
 *
 * 多步骤项目文件导入弹窗组件。
 * 步骤：选择文件 → 选择分割方式 → 解析预览 → 填写书名和封面 → 完成
 */

import {
  Dialog,
  Button,
  Flex,
  Text,
  Box,
  TextField,
  TextArea,
  Badge,
  Progress,
  Card,
} from "@radix-ui/themes";
import { FileText, ChevronDown, ChevronLeft, ChevronRight, Check, AlertCircle } from "lucide-react";
import { useState, useCallback, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { GroupedVirtuoso } from "react-virtuoso";

import "./import-dialog.css";
import {
  confirmDocumentProject,
  DEFAULT_DOCUMENT_IMPORT_OPTIONS,
  getDocumentImportErrorMessage,
  previewDocuments,
  validateDocumentImportOptions,
  type DocumentImportOptions,
  type ImportPreviewResponse,
} from "../lib/import-api";
import { CoverCropper } from "./cover-cropper";
import { ImportDocumentOptions } from "./import-document-options";
import { ImportFileList } from "./import-file-list";

interface ImportDialogProps {
  /** 是否打开对话框 */
  open: boolean;
  /** 关闭对话框回调 */
  onOpenChange: (open: boolean) => void;
  /** 导入成功回调 */
  onSuccess?: () => void;
}

type Step = "select" | "split" | "preview" | "info" | "importing" | "complete";

function getImportFileTitle(filename: string): string {
  return filename.replace(/\.(txt|md)$/i, "");
}

export function ImportDialog({ open, onOpenChange, onSuccess }: ImportDialogProps) {
  const { t, i18n } = useTranslation();

  // 步骤状态
  const [step, setStep] = useState<Step>("select");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 文件和解析结果
  const [files, setFiles] = useState<File[]>([]);
  const [options, setOptions] = useState<DocumentImportOptions>(DEFAULT_DOCUMENT_IMPORT_OPTIONS);
  const [previewData, setPreviewData] = useState<ImportPreviewResponse | null>(null);
  const [expandedVolumeIndexes, setExpandedVolumeIndexes] = useState<number[]>([0]);
  const previewRequestSequence = useRef(0);

  // 项目信息
  const [title, setTitle] = useState("");
  const [titleEdited, setTitleEdited] = useState(false);
  const [mergedVolumeTitleEdited, setMergedVolumeTitleEdited] = useState(false);
  const [description, setDescription] = useState("");
  const [cover, setCover] = useState<File | null>(null);

  // 导入结果
  const [importResult, setImportResult] = useState<{
    projectId: string;
    chapterCount: number;
    wordCount: number;
  } | null>(null);

  // 重置状态
  const resetState = useCallback(() => {
    previewRequestSequence.current += 1;
    setStep("select");
    setLoading(false);
    setError(null);
    setFiles([]);
    setOptions(DEFAULT_DOCUMENT_IMPORT_OPTIONS);
    setPreviewData(null);
    setExpandedVolumeIndexes([0]);
    setTitle("");
    setTitleEdited(false);
    setMergedVolumeTitleEdited(false);
    setDescription("");
    setCover(null);
    setImportResult(null);
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

  const invalidatePreview = useCallback(() => {
    previewRequestSequence.current += 1;
    setPreviewData(null);
    setExpandedVolumeIndexes([0]);
  }, []);

  const handleFilesChange = useCallback(
    (nextFiles: File[]) => {
      invalidatePreview();
      setFiles(nextFiles);
      setError(null);

      if (!titleEdited) {
        setTitle(nextFiles[0] ? getImportFileTitle(nextFiles[0].name) : "");
      }

      if (!mergedVolumeTitleEdited) {
        setOptions((currentOptions) => ({
          ...currentOptions,
          mergedVolumeTitle: nextFiles[0] ? getImportFileTitle(nextFiles[0].name) : "",
        }));
      }
    },
    [invalidatePreview, mergedVolumeTitleEdited, titleEdited],
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

  const handlePreview = useCallback(async () => {
    if (files.length === 0) {
      setError(t("import.documents.invalidFileTotal"));
      return;
    }

    const validationKey = validateDocumentImportOptions(options);
    if (validationKey) {
      setError(t(validationKey));
      return;
    }

    const requestSequence = previewRequestSequence.current + 1;
    previewRequestSequence.current = requestSequence;

    setLoading(true);
    setError(null);

    try {
      const result = await previewDocuments(files, options);
      if (requestSequence !== previewRequestSequence.current) return;

      setPreviewData(result);
      setExpandedVolumeIndexes([0]);
      setStep("preview");
    } catch (err) {
      if (requestSequence !== previewRequestSequence.current) return;

      console.error("预览失败:", err);
      setError(getDocumentImportErrorMessage(err, t("import.parseFailed")));
    } finally {
      if (requestSequence === previewRequestSequence.current) {
        setLoading(false);
      }
    }
  }, [files, options, t]);

  // 处理确认导入
  const handleConfirmImport = useCallback(async () => {
    if (files.length === 0) {
      setError(t("import.documents.invalidFileTotal"));
      setStep("select");
      return;
    }

    const validationKey = validateDocumentImportOptions(options);
    if (validationKey) {
      setError(t(validationKey));
      setStep("split");
      return;
    }

    if (!title.trim()) {
      setError(t("import.bookTitleRequired"));
      return;
    }

    setLoading(true);
    setError(null);
    setStep("importing");

    try {
      const result = await confirmDocumentProject(
        files,
        {
          title: title.trim(),
          description: description.trim() || undefined,
          cover,
        },
        options,
      );

      setImportResult({
        projectId: result.project_id,
        chapterCount: result.chapter_count,
        wordCount: result.total_word_count,
      });
      setStep("complete");
      onSuccess?.();
    } catch (err) {
      console.error("导入失败:", err);
      setError(getDocumentImportErrorMessage(err, t("import.importFailed")));
      setStep("info");
    } finally {
      setLoading(false);
    }
  }, [cover, description, files, onSuccess, options, t, title]);

  // 格式化字数
  const formatWordCount = (count: number) => {
    return new Intl.NumberFormat(i18n.language, {
      notation: count >= 10000 ? "compact" : "standard",
      maximumFractionDigits: count >= 10000 ? 1 : 0,
    }).format(count);
  };

  const handleToggleVolume = (volumeIndex: number) => {
    setExpandedVolumeIndexes((currentIndexes) =>
      currentIndexes.includes(volumeIndex)
        ? currentIndexes.filter((index) => index !== volumeIndex)
        : [...currentIndexes, volumeIndex],
    );
  };

  const previewGroupCounts = useMemo(
    () =>
      previewData?.volumes.map((volume, volumeIndex) =>
        expandedVolumeIndexes.includes(volumeIndex) ? volume.chapters.length : 0,
      ) ?? [],
    [expandedVolumeIndexes, previewData?.volumes],
  );
  const previewChapters = useMemo(
    () =>
      previewData?.volumes.flatMap((volume, volumeIndex) =>
        expandedVolumeIndexes.includes(volumeIndex)
          ? volume.chapters.map((chapter, chapterIndex) => ({ chapter, chapterIndex, volumeIndex }))
          : [],
      ) ?? [],
    [expandedVolumeIndexes, previewData?.volumes],
  );

  const optionsValidationKey = validateDocumentImportOptions(options);

  // 渲染步骤内容
  const renderStepContent = () => {
    switch (step) {
      case "select":
        return (
          <Box>
            <ImportFileList
              files={files}
              onChange={handleFilesChange}
              disabled={loading}
            />
          </Box>
        );

      case "split":
        return (
          <Flex
            direction="column"
            gap="4"
            className="import-dialog-split-content"
          >
            <ImportDocumentOptions
              value={options}
              onChange={handleOptionsChange}
              disabled={loading}
            />
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

                {/* 分卷章节预览 */}
                <Text
                  size="2"
                  weight="medium"
                  mb="2"
                  className="import-dialog-section-title"
                >
                  {t("import.chapterPreview")}
                </Text>
                <Box className="import-dialog-preview-panel">
                  <GroupedVirtuoso
                    className="import-dialog-volume-list"
                    groupCounts={previewGroupCounts}
                    overscan={6}
                    groupContent={(volumeIndex) => {
                      const volume = previewData.volumes[volumeIndex];
                      if (!volume) return null;

                      const wordCount = volume.chapters.reduce(
                        (total, chapter) => total + chapter.word_count,
                        0,
                      );
                      const isExpanded = expandedVolumeIndexes.includes(volumeIndex);

                      return (
                        <Box
                          className="import-dialog-volume-group"
                          data-expanded={isExpanded ? "true" : "false"}
                        >
                          <button
                            type="button"
                            className="import-dialog-volume-header"
                            aria-expanded={isExpanded}
                            aria-controls={`import-volume-${volumeIndex}`}
                            onClick={() => handleToggleVolume(volumeIndex)}
                          >
                            <ChevronDown
                              size={16}
                              className="import-dialog-volume-chevron"
                              data-expanded={isExpanded ? "true" : "false"}
                            />
                            <span className="import-dialog-volume-index">{volumeIndex + 1}</span>
                            <span
                              className="import-dialog-volume-title"
                              title={volume.title}
                            >
                              {volume.title}
                            </span>
                            <span className="import-dialog-volume-meta">
                              {volume.chapter_count} {t("projects.chapters")} ·{" "}
                              {formatWordCount(wordCount)} {t("projects.words")}
                            </span>
                          </button>
                        </Box>
                      );
                    }}
                    itemContent={(chapterListIndex) => {
                      const previewChapter = previewChapters[chapterListIndex];
                      if (!previewChapter) return null;

                      const { chapter, chapterIndex, volumeIndex } = previewChapter;
                      const volume = previewData.volumes[volumeIndex];
                      if (!volume) return null;

                      return (
                        <Box
                          px="3"
                          className="import-dialog-volume-chapters"
                        >
                          <Flex
                            align="center"
                            gap="2"
                            py="2"
                            className={
                              chapterIndex < volume.chapters.length - 1
                                ? "import-dialog-preview-row--bordered"
                                : undefined
                            }
                          >
                            <Text
                              size="1"
                              color="gray"
                              className="import-dialog-chapter-index"
                            >
                              {chapterIndex + 1}
                            </Text>
                            <FileText
                              size={15}
                              color="var(--gray-9)"
                            />
                            <Text
                              size="2"
                              className="import-dialog-preview-title"
                              truncate
                              title={chapter.title}
                            >
                              {chapter.title}
                            </Text>
                            <Badge
                              size="1"
                              color="gray"
                            >
                              {formatWordCount(chapter.word_count)} {t("projects.words")}
                            </Badge>
                          </Flex>
                        </Box>
                      );
                    }}
                  />
                </Box>

                {previewData.chapter_count === 1 &&
                  options.splitMode === "auto" &&
                  files.length === 1 && (
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
                  onChange={(e) => {
                    setTitle(e.target.value);
                    setTitleEdited(true);
                  }}
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
            <Progress
              value={null}
              max={100}
              size="2"
              style={{ width: "100%" }}
            />
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
          <Flex
            gap="3"
            justify="between"
            style={{ width: "100%" }}
          >
            <Button
              variant="soft"
              color="gray"
              onClick={() => handleOpenChange(false)}
            >
              {t("import.close")}
            </Button>
            <Button
              onClick={() => setStep("split")}
              disabled={files.length === 0 || loading}
            >
              {t("import.next")}
              <ChevronRight size={16} />
            </Button>
          </Flex>
        );

      case "split":
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
              disabled={loading}
            >
              <ChevronLeft size={16} />
              {t("import.back")}
            </Button>
            <Button
              onClick={handlePreview}
              loading={loading}
              disabled={files.length === 0 || Boolean(optionsValidationKey)}
            >
              {t("import.next")}
              <ChevronRight size={16} />
            </Button>
          </Flex>
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
              onClick={() => setStep("split")}
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
      case "split":
        return t("import.splitMode");
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

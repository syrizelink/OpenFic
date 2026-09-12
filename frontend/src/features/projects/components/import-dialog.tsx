/**
 * ImportDialog Component
 *
 * Komponen dialog impor berkas proyek bertahap.
 * Tahap: pilih berkas -> pilih cara pemisahan -> pratinjau penguraian -> isi judul dan sampul -> selesai
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
  SegmentedControl,
} from "@radix-ui/themes";
import {
  Upload,
  FileText,
  Archive,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Check,
  AlertCircle,
} from "lucide-react";
import { useState, useCallback, useMemo, useRef } from "react";
import { useTranslation } from "react-i18next";
import { GroupedVirtuoso } from "react-virtuoso";

import "./import-dialog.css";
import {
  confirmImportStream,
  DEFAULT_IMPORT_CHUNK_SIZE,
  MAX_IMPORT_CHUNK_SIZE,
  previewImportFile,
  type ImportPreviewResponse,
  type ImportSplitMode,
} from "../lib/import-api";
import { CoverCropper } from "./cover-cropper";

interface ImportDialogProps {
  /** Status terbuka dialog */
  open: boolean;
  /** Callback penutupan dialog */
  onOpenChange: (open: boolean) => void;
  /** Callback impor berhasil */
  onSuccess?: () => void;
}

type Step = "select" | "split" | "preview" | "info" | "importing" | "complete";

function isSupportedImportFile(filename: string): boolean {
  return /\.(txt|md|zip)$/i.test(filename);
}

function getImportFileTitle(filename: string): string {
  return filename.replace(/\.(txt|md|zip)$/i, "");
}

export function ImportDialog({ open, onOpenChange, onSuccess }: ImportDialogProps) {
  const { t, i18n } = useTranslation();

  // Status tahap
  const [step, setStep] = useState<Step>("select");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Berkas dan hasil penguraian
  const [file, setFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<ImportPreviewResponse | null>(null);
  const [expandedVolumeIndexes, setExpandedVolumeIndexes] = useState<number[]>([0]);
  const [splitMode, setSplitMode] = useState<ImportSplitMode>("auto");
  const [chunkSize, setChunkSize] = useState(String(DEFAULT_IMPORT_CHUNK_SIZE));

  // Informasi proyek
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [cover, setCover] = useState<File | null>(null);

  // Hasil impor
  const [importResult, setImportResult] = useState<{
    projectId: string;
    chapterCount: number;
    wordCount: number;
  } | null>(null);

  // Referensi masukan berkas
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Progres impor
  const [importProgress, setImportProgress] = useState(0);
  const [importStage, setImportStage] = useState("");

  // Mereset status
  const resetState = useCallback(() => {
    setStep("select");
    setLoading(false);
    setError(null);
    setFile(null);
    setPreviewData(null);
    setExpandedVolumeIndexes([0]);
    setSplitMode("auto");
    setChunkSize(String(DEFAULT_IMPORT_CHUNK_SIZE));
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

  // Menangani penutupan dialog
  const handleOpenChange = useCallback(
    (newOpen: boolean) => {
      if (!newOpen) {
        resetState();
      }
      onOpenChange(newOpen);
    },
    [onOpenChange, resetState],
  );

  // Menangani pemilihan berkas
  const handleFileSelect = useCallback(
    (selectedFile: File) => {
      if (!isSupportedImportFile(selectedFile.name)) {
        setError(t("import.invalidFileType"));
        return;
      }

      setFile(selectedFile);
      setPreviewData(null);
      setSplitMode("auto");
      setChunkSize(String(DEFAULT_IMPORT_CHUNK_SIZE));
      setError(null);
      setTitle(getImportFileTitle(selectedFile.name));
      setStep("split");
    },
    [t],
  );

  // Menangani tarik-lepas berkas
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

  const handlePreview = useCallback(async () => {
    if (!file) return;

    const parsedChunkSize = Number(chunkSize);
    if (
      splitMode === "manual" &&
      (!Number.isInteger(parsedChunkSize) ||
        parsedChunkSize < 1 ||
        parsedChunkSize > MAX_IMPORT_CHUNK_SIZE)
    ) {
      setError(t("import.invalidChunkSize"));
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await previewImportFile(
        file,
        splitMode,
        Number.isInteger(parsedChunkSize) ? parsedChunkSize : DEFAULT_IMPORT_CHUNK_SIZE,
      );
      setPreviewData(result);
      setExpandedVolumeIndexes([0]);
      setStep("preview");
    } catch (err) {
      console.error("Gagal membuat pratinjau:", err);
      setError(err instanceof Error ? err.message : t("import.parseFailed"));
    } finally {
      setLoading(false);
    }
  }, [chunkSize, file, splitMode, t]);

  // Menangani konfirmasi impor
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
      const parsedChunkSize = Number(chunkSize);
      const result = await confirmImportStream(
        file,
        title.trim(),
        description.trim() || undefined,
        cover,
        splitMode,
        Number.isInteger(parsedChunkSize) ? parsedChunkSize : DEFAULT_IMPORT_CHUNK_SIZE,
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
      console.error("Gagal mengimpor:", err);
      setError(err instanceof Error ? err.message : t("import.importFailed"));
      setStep("info");
    } finally {
      setLoading(false);
    }
  }, [file, title, description, cover, splitMode, chunkSize, t, onSuccess]);

  // Memformat jumlah kata
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

  // Merender isi tahap
  const renderStepContent = () => {
    switch (step) {
      case "select":
        return (
          <Box>
            <input
              className="import-dialog-file-input"
              ref={fileInputRef}
              type="file"
              accept=".txt,.md,.zip"
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

      case "split":
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
                mb="1"
              >
                {t("import.splitMode")}
              </Text>
              <Text
                as="p"
                size="2"
                color="gray"
              >
                {file?.name}
              </Text>
            </Box>

            {file?.name.toLowerCase().endsWith(".zip") ? (
              <Box className="import-dialog-archive-hint">
                <Archive
                  size={20}
                  className="import-dialog-archive-icon"
                />
                <Box>
                  <Text
                    as="p"
                    size="2"
                    weight="medium"
                  >
                    {t("import.archiveImportTitle")}
                  </Text>
                  <Text
                    as="p"
                    size="2"
                    color="gray"
                  >
                    {t("import.archiveImportDescription")}
                  </Text>
                </Box>
              </Box>
            ) : (
              <>
                <SegmentedControl.Root
                  value={splitMode}
                  onValueChange={(value) => {
                    setSplitMode(value as ImportSplitMode);
                    setError(null);
                  }}
                  size="2"
                  className="import-dialog-split-mode"
                >
                  <SegmentedControl.Item value="auto">
                    {t("import.autoSplit")}
                  </SegmentedControl.Item>
                  <SegmentedControl.Item value="manual">
                    {t("import.manualSplit")}
                  </SegmentedControl.Item>
                </SegmentedControl.Root>

                {splitMode === "manual" ? (
                  <Box>
                    <Text
                      as="label"
                      size="2"
                      weight="medium"
                      mb="1"
                      className="import-dialog-label"
                    >
                      {t("import.chunkSize")}
                    </Text>
                    <TextField.Root
                      type="number"
                      min={1}
                      max={MAX_IMPORT_CHUNK_SIZE}
                      value={chunkSize}
                      onChange={(event) => {
                        setChunkSize(event.target.value);
                        setError(null);
                      }}
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
              </>
            )}
          </Flex>
        );

      case "preview":
        return (
          <Box>
            {previewData && (
              <>
                {/* Informasi statistik */}
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

                {/* Pratinjau volume dan bab */}
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
                  splitMode === "auto" &&
                  file?.name.toLowerCase().endsWith(".zip") !== true && (
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
            {/* Kiri: sampul */}
            <Box className="import-dialog-cover-column">
              <CoverCropper
                value={cover}
                onChange={setCover}
              />
            </Box>

            {/* Kanan: informasi proyek */}
            <Flex
              direction="column"
              gap="4"
              className="import-dialog-info-content"
            >
              {/* Judul buku */}
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

              {/* Deskripsi */}
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

              {/* Pratinjau impor */}
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

  // Merender tombol bawah
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

  // Mengambil judul sesuai tahap
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

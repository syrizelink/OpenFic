import { Button, Checkbox, Dialog, Flex, Progress, SegmentedControl, Text } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  ChevronRight,
  Download,
  FileText,
  Folder,
  FolderOpen,
  LoaderCircle,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Virtuoso } from "react-virtuoso";

import "./chapter-export-dialog.css";

import {
  cancelChapterExport,
  createChapterExport,
  fetchChapter,
  fetchChapterExport,
  fetchProject,
} from "@/lib/api-client";
import { subscribeBackgroundEvents } from "@/lib/background-socket";
import type { ChapterExport } from "@/lib/chapter-export.types";
import type { Chapter, VolumeWithChapters } from "@/lib/chapter.types";
import { getSocketConnectionStatus, subscribeSocketConnectionStatus } from "@/lib/socket-client";

import {
  createChapterExportSelection,
  getExportableVolumes,
  getProjectCheckState,
  getSelectedChapterIds,
  getVolumeCheckState,
  toggleChapterRangeSelection,
  toggleChapterSelection,
  toggleProjectSelection,
  toggleVolumeSelection,
  type ChapterExportCheckState,
  type ChapterExportSelection,
} from "../lib/chapter-export-selection";

interface ChapterExportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectId: string;
  volumes: VolumeWithChapters[];
}

interface ChapterExportTreeRow {
  key: string;
  type: "volume" | "chapter";
  volume: VolumeWithChapters;
  chapter?: VolumeWithChapters["chapters"][number];
}

type ChapterExportStep = "selecting" | "exporting" | "complete" | "error";
type ChapterExportMobileSection = "selection" | "preview";

const ACTIVE_EXPORT_STATUSES = new Set(["pending", "running", "cancel_requested"]);
const EXPORT_I18N_KEY = "writing.chapterExport";

function getLocalDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function toCheckboxValue(state: ChapterExportCheckState): boolean | "indeterminate" {
  if (state === "indeterminate") return "indeterminate";
  return state === "checked";
}

function triggerExportDownload(exportJob: ChapterExport): void {
  if (!exportJob.downloadUrl) return;
  const anchor = document.createElement("a");
  anchor.href = exportJob.downloadUrl;
  anchor.download = exportJob.filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
}

export function ChapterExportDialog({
  open,
  onOpenChange,
  projectId,
  volumes,
}: ChapterExportDialogProps) {
  const { t } = useTranslation();
  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => fetchProject(projectId),
    enabled: open,
  });
  const exportableVolumes = useMemo(() => getExportableVolumes(volumes), [volumes]);
  const [selection, setSelection] = useState<ChapterExportSelection>(createChapterExportSelection);
  const [expandedVolumeIds, setExpandedVolumeIds] = useState<Set<string>>(new Set());
  const [previewChapter, setPreviewChapter] = useState<Chapter | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [step, setStep] = useState<ChapterExportStep>("selecting");
  const [exportJob, setExportJob] = useState<ChapterExport | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [mobileSection, setMobileSection] = useState<ChapterExportMobileSection>("selection");
  const previewRequestIdRef = useRef(0);
  const downloadedExportIdRef = useRef<string | null>(null);
  const exportableVolumesRef = useRef(exportableVolumes);
  exportableVolumesRef.current = exportableVolumes;

  const selectedChapterIds = useMemo(
    () => getSelectedChapterIds(exportableVolumes, selection),
    [exportableVolumes, selection],
  );
  const projectCheckState = useMemo(
    () => getProjectCheckState(exportableVolumes, selectedChapterIds),
    [exportableVolumes, selectedChapterIds],
  );
  const selectedWordCount = useMemo(
    () =>
      exportableVolumes
        .flatMap((volume) => volume.chapters)
        .filter((chapter) => selectedChapterIds.has(chapter.id))
        .reduce((total, chapter) => total + chapter.wordCount, 0),
    [exportableVolumes, selectedChapterIds],
  );
  const rows = useMemo<ChapterExportTreeRow[]>(() => {
    const nextRows: ChapterExportTreeRow[] = [];
    for (const volume of exportableVolumes) {
      nextRows.push({ key: `volume:${volume.id}`, type: "volume", volume });
      if (!expandedVolumeIds.has(volume.id)) continue;
      for (const chapter of volume.chapters) {
        nextRows.push({ key: `chapter:${chapter.id}`, type: "chapter", volume, chapter });
      }
    }
    return nextRows;
  }, [expandedVolumeIds, exportableVolumes]);
  const progress =
    exportJob && exportJob.total > 0 ? (exportJob.current / exportJob.total) * 100 : 0;
  const activeExportJobId = exportJob?.id;
  const activeExportJobStatus = exportJob?.status;

  useEffect(() => {
    if (!open) return;
    previewRequestIdRef.current += 1;
    setSelection(createChapterExportSelection());
    setExpandedVolumeIds(new Set(exportableVolumesRef.current.map((volume) => volume.id)));
    setPreviewChapter(null);
    setStep("selecting");
    setExportJob(null);
    setErrorMessage(null);
    setIsSubmitting(false);
    setIsCancelling(false);
    setMobileSection("selection");
    downloadedExportIdRef.current = null;
  }, [open, projectId]);

  useEffect(() => {
    if (
      !open ||
      !activeExportJobId ||
      !activeExportJobStatus ||
      !ACTIVE_EXPORT_STATUSES.has(activeExportJobStatus)
    )
      return;
    let disposed = false;
    const refresh = async () => {
      try {
        const nextExport = await fetchChapterExport(projectId, activeExportJobId);
        if (!disposed) setExportJob(nextExport);
      } catch (error) {
        if (!disposed) {
          setErrorMessage(
            error instanceof Error ? error.message : t(`${EXPORT_I18N_KEY}.statusLoadFailed`),
          );
          setStep("error");
        }
      }
    };
    let pollingInterval: number | null = null;
    let disconnectTimer: number | null = null;
    const startPolling = () => {
      if (pollingInterval !== null) return;
      void refresh();
      pollingInterval = window.setInterval(() => void refresh(), 1200);
    };
    const stopPolling = () => {
      if (pollingInterval === null) return;
      window.clearInterval(pollingInterval);
      pollingInterval = null;
    };
    const scheduleDisconnectedPolling = () => {
      if (disconnectTimer !== null || pollingInterval !== null) return;
      disconnectTimer = window.setTimeout(() => {
        disconnectTimer = null;
        if (getSocketConnectionStatus() === "disconnected") startPolling();
      }, 5000);
    };
    const subscription = subscribeBackgroundEvents(
      projectId,
      (event) => {
        if (event.job_id !== activeExportJobId || !event.type.startsWith("background_job_")) return;
        if (event.type === "background_job_progress") {
          const current = event.payload?.current;
          const total = event.payload?.total;
          const stage = event.payload?.stage;
          const chapterTitle = event.payload?.chapter_title;
          if (typeof current !== "number" || typeof total !== "number") return;
          setExportJob((currentExport) => {
            if (!currentExport || currentExport.id !== event.job_id) return currentExport;
            return {
              ...currentExport,
              current,
              total,
              stage: typeof stage === "string" ? stage : currentExport.stage,
              chapterTitle: typeof chapterTitle === "string" ? chapterTitle : null,
            };
          });
          return;
        }
        void refresh();
      },
      () => scheduleDisconnectedPolling(),
    );
    const unsubscribeSocketStatus = subscribeSocketConnectionStatus(() => {
      if (getSocketConnectionStatus() === "connected") {
        if (disconnectTimer !== null) {
          window.clearTimeout(disconnectTimer);
          disconnectTimer = null;
        }
        stopPolling();
        return;
      }
      scheduleDisconnectedPolling();
    });
    if (getSocketConnectionStatus() === "disconnected") scheduleDisconnectedPolling();
    void refresh();
    return () => {
      disposed = true;
      subscription.close();
      unsubscribeSocketStatus();
      if (disconnectTimer !== null) window.clearTimeout(disconnectTimer);
      if (pollingInterval !== null) window.clearInterval(pollingInterval);
    };
  }, [activeExportJobId, activeExportJobStatus, open, projectId, t]);

  useEffect(() => {
    if (!exportJob) return;
    if (exportJob.status === "succeeded") {
      setStep("complete");
      setIsCancelling(false);
      if (downloadedExportIdRef.current !== exportJob.id) {
        downloadedExportIdRef.current = exportJob.id;
        triggerExportDownload(exportJob);
      }
      return;
    }
    if (["failed", "timeout", "cancelled", "skipped"].includes(exportJob.status)) {
      setStep("error");
      setIsCancelling(false);
      setErrorMessage(
        exportJob.status === "cancelled"
          ? t(`${EXPORT_I18N_KEY}.cancelled`)
          : (exportJob.errorMessage ?? t(`${EXPORT_I18N_KEY}.failed`)),
      );
    }
  }, [exportJob, t]);

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen && step === "exporting") return;
    onOpenChange(nextOpen);
  };

  const handlePreviewChapter = async (chapterId: string) => {
    const requestId = previewRequestIdRef.current + 1;
    previewRequestIdRef.current = requestId;
    setIsPreviewLoading(true);
    setMobileSection("preview");
    try {
      const chapter = await fetchChapter(chapterId);
      if (previewRequestIdRef.current === requestId) setPreviewChapter(chapter);
    } catch (error) {
      if (previewRequestIdRef.current === requestId) {
        setErrorMessage(
          error instanceof Error ? error.message : t(`${EXPORT_I18N_KEY}.previewFailed`),
        );
      }
    } finally {
      if (previewRequestIdRef.current === requestId) setIsPreviewLoading(false);
    }
  };

  const handleChapterClick = (event: React.MouseEvent<HTMLButtonElement>, chapterId: string) => {
    if (event.shiftKey) {
      setSelection((current) => toggleChapterRangeSelection(current, exportableVolumes, chapterId));
      return;
    }
    if (event.ctrlKey || event.metaKey) {
      setSelection((current) => toggleChapterSelection(current, exportableVolumes, chapterId));
      return;
    }
    void handlePreviewChapter(chapterId);
  };

  const handleStartExport = async () => {
    if (selectedChapterIds.size === 0) return;
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const nextExport = await createChapterExport(projectId, {
        selectedVolumeIds: [...selection.selectedVolumeIds],
        includedChapterIds: [...selection.includedChapterIds],
        excludedChapterIds: [...selection.excludedChapterIds],
        localDate: getLocalDate(),
      });
      setExportJob(nextExport);
      setStep("exporting");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : t(`${EXPORT_I18N_KEY}.failed`));
      setStep("error");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancelExport = async () => {
    if (!exportJob || isCancelling) return;
    setIsCancelling(true);
    try {
      setExportJob(await cancelChapterExport(projectId, exportJob.id));
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : t(`${EXPORT_I18N_KEY}.cancelFailed`),
      );
      setIsCancelling(false);
    }
  };

  const handleBackToSelection = () => {
    setStep("selecting");
    setExportJob(null);
    setErrorMessage(null);
  };

  return (
    <Dialog.Root
      open={open}
      onOpenChange={handleOpenChange}
    >
      <Dialog.Content
        className="chapter-export-dialog-content"
        data-step={step}
        maxWidth="1080px"
      >
        <Dialog.Title>{t(`${EXPORT_I18N_KEY}.title`)}</Dialog.Title>
        {step === "selecting" && (
          <Flex
            className="chapter-export-dialog-layout"
            data-mobile-section={mobileSection}
          >
            <div className="chapter-export-mobile-section-tabs">
              <SegmentedControl.Root
                value={mobileSection}
                onValueChange={(value) => setMobileSection(value as ChapterExportMobileSection)}
                size="1"
              >
                <SegmentedControl.Item value="selection">
                  {t(`${EXPORT_I18N_KEY}.selectionTab`)}
                </SegmentedControl.Item>
                <SegmentedControl.Item value="preview">
                  {t(`${EXPORT_I18N_KEY}.previewTab`)}
                </SegmentedControl.Item>
              </SegmentedControl.Root>
            </div>
            <section className="chapter-export-tree-panel">
              <div className="chapter-export-project-row">
                <Checkbox
                  checked={toCheckboxValue(projectCheckState)}
                  onCheckedChange={() =>
                    setSelection(() => toggleProjectSelection(exportableVolumes, projectCheckState))
                  }
                  aria-label={t(`${EXPORT_I18N_KEY}.selectProject`)}
                />
                <Text
                  size="2"
                  weight="bold"
                  truncate
                >
                  {project?.title ?? t(`${EXPORT_I18N_KEY}.project`)}
                </Text>
              </div>
              {rows.length > 0 ? (
                <Virtuoso
                  className="chapter-export-tree"
                  data={rows}
                  itemContent={(_index, row) => {
                    if (row.type === "volume") {
                      const volumeState = getVolumeCheckState(row.volume, selectedChapterIds);
                      const isExpanded = expandedVolumeIds.has(row.volume.id);
                      return (
                        <div className="chapter-export-volume-row">
                          <Checkbox
                            className="chapter-export-row-checkbox"
                            checked={toCheckboxValue(volumeState)}
                            onCheckedChange={() =>
                              setSelection((current) =>
                                toggleVolumeSelection(current, row.volume, volumeState),
                              )
                            }
                            aria-label={t(`${EXPORT_I18N_KEY}.selectVolume`, {
                              title: row.volume.title,
                            })}
                          />
                          <button
                            type="button"
                            className="chapter-export-tree-button"
                            onClick={() =>
                              setExpandedVolumeIds((current) => {
                                const next = new Set(current);
                                if (next.has(row.volume.id)) next.delete(row.volume.id);
                                else next.add(row.volume.id);
                                return next;
                              })
                            }
                          >
                            <ChevronRight
                              size={15}
                              className="chapter-export-chevron"
                              data-expanded={isExpanded ? "true" : "false"}
                            />
                            {isExpanded ? <FolderOpen size={15} /> : <Folder size={15} />}
                            <span>{row.volume.title || t("volume.untitled")}</span>
                            <small>{row.volume.chapterCount}</small>
                          </button>
                        </div>
                      );
                    }

                    const chapter = row.chapter;
                    if (!chapter) return null;
                    return (
                      <div className="chapter-export-chapter-row">
                        <Checkbox
                          className="chapter-export-row-checkbox"
                          checked={selectedChapterIds.has(chapter.id)}
                          onClick={(event) => {
                            if (!event.shiftKey) return;
                            event.preventDefault();
                            setSelection((current) =>
                              toggleChapterRangeSelection(current, exportableVolumes, chapter.id),
                            );
                          }}
                          onCheckedChange={() =>
                            setSelection((current) =>
                              toggleChapterSelection(current, exportableVolumes, chapter.id),
                            )
                          }
                          aria-label={t(`${EXPORT_I18N_KEY}.selectChapter`, {
                            title: chapter.title,
                          })}
                        />
                        <button
                          type="button"
                          className="chapter-export-tree-button"
                          data-active={previewChapter?.id === chapter.id ? "true" : "false"}
                          onClick={(event) => handleChapterClick(event, chapter.id)}
                        >
                          <FileText size={14} />
                          <span>{chapter.title || t("writing.untitledChapter")}</span>
                          <small>{chapter.wordCount}</small>
                        </button>
                      </div>
                    );
                  }}
                />
              ) : (
                <Text
                  size="2"
                  color="gray"
                  className="chapter-export-empty"
                >
                  {t(`${EXPORT_I18N_KEY}.noChapters`)}
                </Text>
              )}
            </section>

            <section className="chapter-export-preview-panel">
              {isPreviewLoading ? (
                <Flex
                  align="center"
                  justify="center"
                  gap="2"
                  className="chapter-export-preview-empty"
                >
                  <LoaderCircle
                    className="chapter-export-spinner"
                    size={18}
                  />
                  <Text
                    size="2"
                    color="gray"
                  >
                    {t("common.loading")}
                  </Text>
                </Flex>
              ) : previewChapter ? (
                <article className="chapter-export-preview-content">
                  <Text
                    as="p"
                    size="4"
                    weight="bold"
                  >
                    {previewChapter.title || t("writing.untitledChapter")}
                  </Text>
                  <Text
                    size="2"
                    color="gray"
                  >
                    {t(`${EXPORT_I18N_KEY}.previewWords`, { count: previewChapter.wordCount })}
                  </Text>
                  <div className="chapter-export-preview-body">{previewChapter.content}</div>
                </article>
              ) : (
                <Flex
                  direction="column"
                  align="center"
                  justify="center"
                  gap="2"
                  className="chapter-export-preview-empty"
                >
                  <FileText size={28} />
                  <Text
                    size="2"
                    color="gray"
                  >
                    {t(`${EXPORT_I18N_KEY}.previewPlaceholder`)}
                  </Text>
                </Flex>
              )}
            </section>
          </Flex>
        )}

        {step === "exporting" && exportJob && (
          <Flex
            direction="column"
            align="center"
            gap="3"
            className="chapter-export-state"
          >
            <LoaderCircle
              className="chapter-export-spinner"
              size={32}
            />
            <Text weight="bold">
              {isCancelling
                ? t(`${EXPORT_I18N_KEY}.cancelling`)
                : t(`${EXPORT_I18N_KEY}.exporting`)}
            </Text>
            <Text
              size="2"
              color="gray"
            >
              {exportJob.chapterTitle ?? t(`${EXPORT_I18N_KEY}.preparing`)}
            </Text>
            <Progress
              value={progress}
              max={100}
              size="2"
              className="chapter-export-progress"
            />
            <Text
              size="2"
              color="gray"
            >
              {t(`${EXPORT_I18N_KEY}.progress`, {
                current: exportJob.current,
                total: exportJob.total,
              })}
            </Text>
          </Flex>
        )}

        {step === "complete" && exportJob && (
          <Flex
            direction="column"
            align="center"
            gap="3"
            className="chapter-export-state"
          >
            <CheckCircle2
              className="chapter-export-success-icon"
              size={42}
            />
            <Text
              size="4"
              weight="bold"
            >
              {t(`${EXPORT_I18N_KEY}.success`)}
            </Text>
            <Text
              size="2"
              color="gray"
              align="center"
            >
              {t(`${EXPORT_I18N_KEY}.successInfo`, {
                volumes: exportJob.volumeCount,
                chapters: exportJob.chapterCount,
                words: exportJob.wordCount,
              })}
            </Text>
            <div className="chapter-export-file-name">{exportJob.filename}</div>
          </Flex>
        )}

        {step === "error" && (
          <Flex
            direction="column"
            align="center"
            gap="3"
            className="chapter-export-state"
          >
            <AlertCircle
              className="chapter-export-error-icon"
              size={38}
            />
            <Text
              size="4"
              weight="bold"
            >
              {t(`${EXPORT_I18N_KEY}.errorTitle`)}
            </Text>
            <Text
              size="2"
              color="gray"
              align="center"
            >
              {errorMessage ?? t(`${EXPORT_I18N_KEY}.failed`)}
            </Text>
          </Flex>
        )}

        <Flex
          justify="between"
          align="center"
          gap="3"
          mt="4"
          className="chapter-export-footer"
        >
          {step === "selecting" ? (
            <Text
              size="2"
              color="gray"
            >
              {t(`${EXPORT_I18N_KEY}.selectionInfo`, {
                chapters: selectedChapterIds.size,
                words: selectedWordCount,
              })}
            </Text>
          ) : (
            <span />
          )}
          <Flex gap="2">
            {step === "selecting" && (
              <>
                <Button
                  variant="soft"
                  color="gray"
                  onClick={() => handleOpenChange(false)}
                >
                  {t("common.cancel")}
                </Button>
                <Button
                  onClick={() => void handleStartExport()}
                  loading={isSubmitting}
                  disabled={selectedChapterIds.size === 0}
                >
                  <Download size={16} />
                  {t(`${EXPORT_I18N_KEY}.export`)}
                </Button>
              </>
            )}
            {step === "exporting" && (
              <Button
                variant="soft"
                color="red"
                disabled={isCancelling}
                onClick={() => void handleCancelExport()}
              >
                <X size={16} />
                {t(`${EXPORT_I18N_KEY}.cancelExport`)}
              </Button>
            )}
            {step === "complete" && exportJob && (
              <>
                <Button
                  variant="soft"
                  color="gray"
                  onClick={() => handleOpenChange(false)}
                >
                  {t("common.close")}
                </Button>
                <Button onClick={() => triggerExportDownload(exportJob)}>
                  <Download size={16} />
                  {t(`${EXPORT_I18N_KEY}.downloadAgain`)}
                </Button>
              </>
            )}
            {step === "error" && (
              <Button onClick={handleBackToSelection}>
                {t(`${EXPORT_I18N_KEY}.backToSelection`)}
              </Button>
            )}
          </Flex>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

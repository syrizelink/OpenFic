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
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components";
import {
  fetchNoteTree,
  fetchProjects,
  importNotes,
  importNotesFromProject,
  previewNoteImport,
  previewProjectNoteImport,
} from "@/lib/api-client";
import type {
  NoteCategoryItem,
  NoteConflictStrategy,
  NoteImportPreview,
  NoteImportResult,
  NoteTreeResponse,
  ProjectNoteImportPreview,
  ProjectNoteImportRequest,
  ProjectNoteImportResult,
} from "@/lib/note.types";
import type { Project } from "@/lib/project.types";

import "./note-import-dialog.css";

interface NoteImportDialogProps {
  open: boolean;
  projectId: string;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (result: NoteImportResult | ProjectNoteImportResult) => void;
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
  const [sourceMode, setSourceMode] = useState<"file" | "project">("file");
  const [projects, setProjects] = useState<Project[]>([]);
  const [sourceProjectId, setSourceProjectId] = useState("");
  const [sourceTree, setSourceTree] = useState<NoteTreeResponse | null>(null);
  const [selectedCategoryIds, setSelectedCategoryIds] = useState<string[]>([]);
  const [selectedNoteIds, setSelectedNoteIds] = useState<string[]>([]);
  const [conflictStrategy, setConflictStrategy] = useState<NoteConflictStrategy>("rename");
  const [conflictOverrides, setConflictOverrides] = useState<Record<string, NoteConflictStrategy>>(
    {},
  );
  const [projectPreview, setProjectPreview] = useState<ProjectNoteImportPreview | null>(null);
  const [projectResult, setProjectResult] = useState<ProjectNoteImportResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const previewRequestRef = useRef(0);

  useEffect(() => {
    if (!open) return;
    void fetchProjects({ page: 1, pageSize: 100 }).then((value) =>
      setProjects(value.items.filter((item) => item.id !== projectId)),
    );
  }, [open, projectId]);

  useEffect(() => {
    if (!sourceProjectId) {
      setSourceTree(null);
      return;
    }
    void fetchNoteTree(sourceProjectId).then(setSourceTree);
  }, [sourceProjectId]);

  const resetState = useCallback(() => {
    setStep("select");
    setFile(null);
    setPreview(null);
    setResult(null);
    setIsLoading(false);
    setError(null);
    setSourceMode("file");
    setSourceProjectId("");
    setSourceTree(null);
    setSelectedCategoryIds([]);
    setSelectedNoteIds([]);
    setProjectPreview(null);
    setProjectResult(null);
    setConflictOverrides({});
    previewRequestRef.current += 1;
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
      const requestId = ++previewRequestRef.current;
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
        if (requestId !== previewRequestRef.current) return;
        setPreview(nextPreview);
        setStep("preview");
      } catch (importError) {
        if (requestId === previewRequestRef.current) {
          setError(getImportErrorMessage(importError, t("writing.noteImport.parseFailed")));
        }
      } finally {
        if (requestId === previewRequestRef.current) setIsLoading(false);
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

  const buildProjectRequest = useCallback(
    (): ProjectNoteImportRequest => ({
      sourceProjectId,
      selectedCategoryIds,
      selectedNoteIds,
      defaultConflictStrategy: conflictStrategy,
      conflictOverrides,
    }),
    [sourceProjectId, selectedCategoryIds, selectedNoteIds, conflictStrategy, conflictOverrides],
  );

  const handleImport = useCallback(async () => {
    if (sourceMode === "project") {
      const request = buildProjectRequest();
      setStep("importing");
      setIsLoading(true);
      setError(null);
      try {
        const nextResult = await importNotesFromProject(projectId, request);
        setProjectResult(nextResult);
        setStep("complete");
        onSuccess?.(nextResult);
      } catch (importError) {
        setError(getImportErrorMessage(importError, t("writing.noteImport.importFailed")));
        setStep("preview");
      } finally {
        setIsLoading(false);
      }
      return;
    }
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
  }, [buildProjectRequest, file, onSuccess, projectId, sourceMode, t]);

  const handleProjectPreview = useCallback(async () => {
    const requestId = ++previewRequestRef.current;
    setIsLoading(true);
    setError(null);
    try {
      const nextPreview = await previewProjectNoteImport(projectId, buildProjectRequest());
      if (requestId !== previewRequestRef.current) return;
      setProjectPreview(nextPreview);
      setStep("preview");
    } catch (importError) {
      if (requestId === previewRequestRef.current)
        setError(getImportErrorMessage(importError, t("writing.noteImport.parseFailed")));
    } finally {
      if (requestId === previewRequestRef.current) setIsLoading(false);
    }
  }, [buildProjectRequest, projectId, t]);

  const toggleNote = useCallback((id: string, checked: boolean) => {
    setSelectedNoteIds((items) =>
      checked ? [...new Set([...items, id])] : items.filter((item) => item !== id),
    );
  }, []);

  const toggleCategory = useCallback((category: NoteCategoryItem, checked: boolean) => {
    const categoryIds: string[] = [];
    const noteIds: string[] = [];
    const collect = (item: NoteCategoryItem) => {
      categoryIds.push(item.id);
      noteIds.push(...item.notes.map((note) => note.id));
      item.categories.forEach(collect);
    };
    collect(category);
    setSelectedCategoryIds((items) =>
      checked
        ? [...new Set([...items, ...categoryIds])]
        : items.filter((id) => !categoryIds.includes(id)),
    );
    setSelectedNoteIds((items) =>
      checked ? [...new Set([...items, ...noteIds])] : items.filter((id) => !noteIds.includes(id)),
    );
  }, []);

  const renderProjectTree = (categories: NoteCategoryItem[], depth = 0): React.ReactNode =>
    categories.map((category) => (
      <Box
        key={category.id}
        style={{ paddingLeft: depth * 16 }}
      >
        <label className="note-import-check-row">
          <input
            type="checkbox"
            checked={selectedCategoryIds.includes(category.id)}
            onChange={(event) => toggleCategory(category, event.target.checked)}
          />
          <span>📁 {category.title}</span>
        </label>
        {category.notes.map((note) => (
          <label
            key={note.id}
            className="note-import-check-row"
            style={{ marginLeft: 16 }}
          >
            <input
              type="checkbox"
              checked={selectedNoteIds.includes(note.id)}
              onChange={(event) => toggleNote(note.id, event.target.checked)}
            />
            <span>{note.title}</span>
          </label>
        ))}
        {renderProjectTree(category.categories, depth + 1)}
      </Box>
    ));

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
            <Flex
              gap="2"
              mb="4"
            >
              <Button
                variant={sourceMode === "file" ? "solid" : "soft"}
                onClick={() => setSourceMode("file")}
              >
                文件导入
              </Button>
              <Button
                variant={sourceMode === "project" ? "solid" : "soft"}
                onClick={() => setSourceMode("project")}
              >
                其他项目
              </Button>
            </Flex>
            {sourceMode === "project" ? (
              <Box>
                <Text
                  as="label"
                  size="2"
                >
                  来源项目
                </Text>
                <select
                  className="note-import-select"
                  value={sourceProjectId}
                  onChange={(event) => {
                    setSourceProjectId(event.target.value);
                    setSelectedCategoryIds([]);
                    setSelectedNoteIds([]);
                  }}
                >
                  <option value="">请选择项目</option>
                  {projects.map((project) => (
                    <option
                      key={project.id}
                      value={project.id}
                    >
                      {project.title}
                    </option>
                  ))}
                </select>
                {sourceTree && (
                  <Box className="note-import-project-tree">
                    {sourceTree.rootNotes.map((note) => (
                      <label
                        key={note.id}
                        className="note-import-check-row"
                      >
                        <input
                          type="checkbox"
                          checked={selectedNoteIds.includes(note.id)}
                          onChange={(event) => toggleNote(note.id, event.target.checked)}
                        />
                        <span>{note.title}</span>
                      </label>
                    ))}
                    {renderProjectTree(sourceTree.categories)}
                  </Box>
                )}
                <Text
                  as="label"
                  size="2"
                >
                  同名笔记默认处理
                </Text>
                <select
                  className="note-import-select"
                  value={conflictStrategy}
                  onChange={(event) =>
                    setConflictStrategy(event.target.value as NoteConflictStrategy)
                  }
                >
                  <option value="rename">重命名后导入</option>
                  <option value="overwrite">覆盖目标笔记</option>
                  <option value="skip">跳过</option>
                </select>
              </Box>
            ) : (
              <>
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
              </>
            )}
          </Box>
        );
      case "preview":
        return (
          <Box>
            {sourceMode === "project" && projectPreview ? (
              <>
                <Flex
                  gap="3"
                  mb="4"
                  wrap="wrap"
                >
                  <Badge>新增笔记 {projectPreview.createNoteCount}</Badge>
                  <Badge color="orange">覆盖 {projectPreview.overwriteNoteCount}</Badge>
                  <Badge color="gray">跳过 {projectPreview.skipNoteCount}</Badge>
                  <Badge color="blue">新建分类 {projectPreview.createCategoryCount}</Badge>
                </Flex>
                <Box className="note-import-conflicts">
                  {projectPreview.actions.map((action) => (
                    <Flex
                      key={action.sourceNoteId}
                      justify="between"
                      align="center"
                      gap="3"
                      className="note-import-action-row"
                    >
                      <Text size="2">
                        {action.sourcePath ? `${action.sourcePath} / ` : ""}
                        {action.targetTitle}
                      </Text>
                      <select
                        value={conflictOverrides[action.sourceNoteId] ?? conflictStrategy}
                        onChange={(event) =>
                          setConflictOverrides((items) => ({
                            ...items,
                            [action.sourceNoteId]: event.target.value as NoteConflictStrategy,
                          }))
                        }
                      >
                        <option value="rename">重命名</option>
                        <option value="overwrite">覆盖</option>
                        <option value="skip">跳过</option>
                      </select>
                    </Flex>
                  ))}
                </Box>
              </>
            ) : null}
            {sourceMode === "file" && preview && file && (
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
              value={null}
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
            {sourceMode === "project" && projectResult ? (
              <Text
                as="p"
                size="2"
                color="gray"
              >
                已导入 {projectResult.createdNoteCount} 个笔记，覆盖{" "}
                {projectResult.overwrittenNoteCount} 个，跳过 {projectResult.skippedNoteCount} 个
              </Text>
            ) : (
              result && (
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
              )
            )}
          </Flex>
        );
    }
  };

  const renderFooter = () => {
    switch (step) {
      case "select":
        return sourceMode === "project" ? (
          <Flex
            className="note-import-footer"
            justify="between"
          >
            <Button
              variant="soft"
              color="gray"
              onClick={() => handleOpenChange(false)}
            >
              {t("common.close")}
            </Button>
            <Button
              loading={isLoading}
              disabled={
                !sourceProjectId || selectedCategoryIds.length + selectedNoteIds.length === 0
              }
              onClick={() => void handleProjectPreview()}
            >
              预览导入
              <ChevronRight size={16} />
            </Button>
          </Flex>
        ) : (
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

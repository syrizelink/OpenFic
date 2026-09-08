import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { restrictToVerticalAxis } from "@dnd-kit/modifiers";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Box, Button, Flex, IconButton, Text, Tooltip } from "@radix-ui/themes";
import { FileText, GripVertical, Trash2, Upload } from "lucide-react";
import { useCallback, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { useTranslation } from "react-i18next";

import "./import-dialog.css";

const SUPPORTED_FILE_PATTERN = /\.(txt|md)$/i;
const MAX_DOCUMENT_IMPORT_FILES = 100;

interface ImportFileListProps {
  files: File[];
  onChange: (files: File[]) => void;
  disabled?: boolean;
}

function isSupportedDocumentFile(file: File): boolean {
  return SUPPORTED_FILE_PATTERN.test(file.name);
}

interface SortableFileRowProps {
  file: File;
  fileId: string;
  index: number;
  disabled: boolean;
  onRemove: () => void;
}

interface ImportFileRow {
  file: File;
  id: string;
}

function SortableFileRow({ file, fileId, index, disabled, onRemove }: SortableFileRowProps) {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: fileId,
    disabled,
  });

  return (
    <Flex
      ref={setNodeRef}
      className="import-dialog-file-row"
      align="center"
      gap="2"
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
      }}
    >
      <IconButton
        {...attributes}
        {...listeners}
        variant="ghost"
        color="gray"
        size="1"
        disabled={disabled}
        aria-label={t("import.documents.reorderFiles")}
        className="import-dialog-file-drag-handle"
      >
        <GripVertical size={16} />
      </IconButton>
      <Text
        size="2"
        color="gray"
        className="import-dialog-file-index"
      >
        {index + 1}
      </Text>
      <FileText
        size={18}
        className="import-dialog-file-icon"
      />
      <Text
        size="2"
        weight="medium"
        className="import-dialog-file-name"
      >
        {file.name}
      </Text>
      <Tooltip content={t("import.documents.removeFile", { name: file.name })}>
        <IconButton
          variant="ghost"
          color="gray"
          size="1"
          disabled={disabled}
          aria-label={t("import.documents.removeFile", { name: file.name })}
          onClick={onRemove}
        >
          <Trash2 size={16} />
        </IconButton>
      </Tooltip>
    </Flex>
  );
}

/** Select, order, and remove the documents submitted to an import endpoint. */
export function ImportFileList({ files, onChange, disabled = false }: ImportFileListProps) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const fileRowsRef = useRef<ImportFileRow[]>([]);
  const nextId = useRef(0);
  const [fileError, setFileError] = useState<string | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const createFileRow = useCallback((file: File): ImportFileRow => {
    nextId.current += 1;
    return { file, id: `import-file-${nextId.current}` };
  }, []);

  if (
    fileRowsRef.current.length !== files.length ||
    fileRowsRef.current.some((row, index) => row.file !== files[index])
  ) {
    const usedRows = new Set<ImportFileRow>();
    fileRowsRef.current = files.map((file) => {
      const existingRow = fileRowsRef.current.find(
        (row) => !usedRows.has(row) && row.file === file,
      );
      if (existingRow) {
        usedRows.add(existingRow);
        return existingRow;
      }
      return createFileRow(file);
    });
  }

  const fileRows = fileRowsRef.current;

  const addFiles = useCallback(
    (addedFiles: File[]) => {
      const supportedFiles = addedFiles.filter(isSupportedDocumentFile);
      if (files.length + supportedFiles.length > MAX_DOCUMENT_IMPORT_FILES) {
        setFileError(t("import.documents.invalidFileTotal"));
        return;
      }
      if (supportedFiles.length > 0) {
        setFileError(
          supportedFiles.length === addedFiles.length
            ? null
            : t("import.documents.invalidFileType"),
        );
        const addedRows = supportedFiles.map(createFileRow);
        fileRowsRef.current = [...fileRowsRef.current, ...addedRows];
        onChange([...files, ...addedRows.map((row) => row.file)]);
      } else if (addedFiles.length > 0) {
        setFileError(t("import.documents.invalidFileType"));
      }
    },
    [createFileRow, files, onChange, t],
  );

  const handleInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      addFiles(Array.from(event.target.files ?? []));
      event.target.value = "";
    },
    [addFiles],
  );

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      if (!disabled) addFiles(Array.from(event.dataTransfer.files));
    },
    [addFiles, disabled],
  );

  const handleDragEnd = useCallback(
    ({ active, over }: DragEndEvent) => {
      if (!over || active.id === over.id) return;

      const oldIndex = fileRowsRef.current.findIndex((row) => row.id === active.id);
      const newIndex = fileRowsRef.current.findIndex((row) => row.id === over.id);
      if (oldIndex >= 0 && newIndex >= 0) {
        const reorderedRows = arrayMove(fileRowsRef.current, oldIndex, newIndex);
        fileRowsRef.current = reorderedRows;
        onChange(reorderedRows.map((row) => row.file));
      }
    },
    [onChange],
  );

  return (
    <Flex
      direction="column"
      gap="3"
    >
      <input
        ref={inputRef}
        className="import-dialog-file-input"
        type="file"
        accept=".txt,.md"
        multiple
        disabled={disabled}
        onChange={handleInputChange}
      />
      <Box
        className="import-dialog-file-dropzone"
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleDrop}
      >
        <Button
          type="button"
          variant="soft"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
        >
          <Upload size={16} />
          {t("import.documents.addFiles")}
        </Button>
        <Text
          size="1"
          color="gray"
        >
          {t("import.documents.supportedFormats")}
        </Text>
      </Box>
      {fileError && (
        <Text
          size="1"
          color="red"
        >
          {fileError}
        </Text>
      )}

      {files.length > 0 && (
        <>
          <Text
            size="1"
            color="gray"
          >
            {t("import.documents.fileOrderHint")}
          </Text>
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            modifiers={[restrictToVerticalAxis]}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={fileRows.map((row) => row.id)}
              strategy={verticalListSortingStrategy}
            >
              <Flex
                direction="column"
                className="import-dialog-file-list"
              >
                {fileRows.map((row, index) => (
                  <SortableFileRow
                    key={row.id}
                    file={row.file}
                    fileId={row.id}
                    index={index}
                    disabled={disabled}
                    onRemove={() => {
                      fileRowsRef.current = fileRowsRef.current.filter(
                        (_, currentIndex) => currentIndex !== index,
                      );
                      onChange(fileRowsRef.current.map((currentRow) => currentRow.file));
                    }}
                  />
                ))}
              </Flex>
            </SortableContext>
          </DndContext>
        </>
      )}
    </Flex>
  );
}

import i18n from "@/i18n";
import type { AgentAttachment } from "@/lib/agent.types";

export const MAX_AGENT_ATTACHMENTS = 20;
export const MAX_AGENT_ATTACHMENT_BYTES = 10 * 1024 * 1024;

const SUPPORTED_AGENT_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const SUPPORTED_AGENT_FILE_EXTENSIONS = new Set([
  "txt",
  "md",
  "go",
  "py",
  "java",
  "sh",
  "bat",
  "ps1",
  "cmd",
  "js",
  "ts",
  "css",
  "cpp",
  "hpp",
  "h",
  "c",
  "cs",
  "sql",
  "log",
  "ini",
  "pl",
  "pm",
  "r",
  "dart",
  "dockerfile",
  "env",
  "php",
  "hs",
  "hsc",
  "lua",
  "nginxconf",
  "conf",
  "m",
  "mm",
  "plsql",
  "perl",
  "rb",
  "rs",
  "db2",
  "scala",
  "bash",
  "swift",
  "vue",
  "svelte",
  "ex",
  "exs",
  "erl",
  "tsx",
  "jsx",
  "lhs",
  "json",
  "yaml",
  "yml",
  "toml",
  "pdf",
  "csv",
  "docx",
  "doc",
  "xlsx",
  "xls",
  "pptx",
  "ppt",
  "xml",
  "rst",
  "epub",
  "odt",
  "msg",
  "html",
  "htm",
  "jpg",
  "jpeg",
  "png",
  "webp",
]);

export interface PendingAgentAttachment {
  id: string;
  file?: File;
  uploadedAttachment?: AgentAttachment;
  previewUrl: string;
  status: "pending" | "uploading" | "ready";
}

export function createRestoredPendingAgentAttachments(
  attachments: AgentAttachment[],
): PendingAgentAttachment[] {
  return attachments.map((attachment) => ({
    id: attachment.id,
    previewUrl: isImageAttachment(attachment) ? attachment.url : "",
    uploadedAttachment: attachment,
    status: "ready",
  }));
}

export function getAgentFiles(dataTransfer: DataTransfer): File[] {
  const files = Array.from(dataTransfer.files);
  if (files.length > 0) return files;

  return Array.from(dataTransfer.items).flatMap((item) => {
    if (item.kind !== "file") return [];
    const file = item.getAsFile();
    return file ? [file] : [];
  });
}

export function hasLeftAgentDropZone(
  relatedTarget: EventTarget | null,
  contains: (target: Node) => boolean,
): boolean {
  return relatedTarget === null || !contains(relatedTarget as Node);
}

export function getAgentFileExtension(fileName: string): string {
  const normalizedName = fileName.trim().toLowerCase().split(/[\\/]/).pop() ?? "";
  const lastDot = normalizedName.lastIndexOf(".");
  const extension =
    lastDot > 0
      ? normalizedName.slice(lastDot + 1)
      : lastDot === 0
        ? normalizedName.slice(1)
        : normalizedName;
  return extension.toUpperCase() || "FILE";
}

export function formatAgentFileSize(sizeBytes: number): string {
  if (!Number.isFinite(sizeBytes) || sizeBytes < 0) return "0B";
  if (sizeBytes < 1024) return `${Math.round(sizeBytes)}B`;

  const units = ["KB", "MB", "GB"];
  const unitIndex = Math.min(
    Math.floor(Math.log(sizeBytes) / Math.log(1024)) - 1,
    units.length - 1,
  );
  const value = sizeBytes / 1024 ** (unitIndex + 1);
  return `${value.toFixed(2)}${units[unitIndex]}`;
}

export function isSupportedAgentImage(file: File): boolean {
  return (
    SUPPORTED_AGENT_IMAGE_TYPES.has(file.type.toLowerCase()) ||
    ["jpg", "jpeg", "png", "webp"].includes(getAgentFileExtension(file.name).toLowerCase())
  );
}

export function requiresAgentAttachmentProcessing(file: File): boolean {
  return !isSupportedAgentImage(file);
}

export function isSupportedAgentFile(file: File): boolean {
  return (
    isSupportedAgentImage(file) ||
    file.type.toLowerCase().startsWith("text/") ||
    SUPPORTED_AGENT_FILE_EXTENSIONS.has(getAgentFileExtension(file.name).toLowerCase())
  );
}

export interface AgentFileValidationResult {
  validFiles: File[];
  rejectedFiles: File[];
  errors: string[];
}

export function validateAgentFiles(
  files: File[],
  existingCount: number,
  canAttachImages: boolean,
): AgentFileValidationResult {
  const validFiles: File[] = [];
  const rejectedFiles: File[] = [];
  const errors: string[] = [];
  const remainingSlots = Math.max(MAX_AGENT_ATTACHMENTS - existingCount, 0);

  for (const file of files) {
    const error =
      validFiles.length >= remainingSlots
        ? i18n.t("writing.aiSidebar.attachmentLimit", { count: MAX_AGENT_ATTACHMENTS })
        : !isSupportedAgentFile(file)
          ? i18n.t("writing.aiSidebar.unsupportedAttachmentType")
          : isSupportedAgentImage(file) && !canAttachImages
            ? i18n.t("writing.aiSidebar.modelImageInputUnsupported")
            : file.size > MAX_AGENT_ATTACHMENT_BYTES
              ? i18n.t("writing.aiSidebar.attachmentTooLarge")
              : null;

    if (error) {
      rejectedFiles.push(file);
      if (!errors.includes(error)) errors.push(error);
      continue;
    }

    validFiles.push(file);
  }

  return { validFiles, rejectedFiles, errors };
}

export function modelAllowsAgentImages(
  inputModalities: string[] | undefined,
  isCatalogMatched: boolean,
): boolean {
  if (!isCatalogMatched) return true;
  return inputModalities?.some((modality) => modality.toLowerCase() === "image") ?? false;
}

export function isImageAttachment(attachment: AgentAttachment): boolean {
  return SUPPORTED_AGENT_IMAGE_TYPES.has(attachment.mimeType.toLowerCase());
}

export function isAgentAttachment(value: unknown): value is AgentAttachment {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const attachment = value as Record<string, unknown>;
  return (
    typeof attachment.id === "string" &&
    typeof attachment.url === "string" &&
    typeof attachment.mime_type === "string"
  );
}

export function normalizeAgentAttachments(value: unknown): AgentAttachment[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!isAgentAttachment(item)) return [];
    const attachment = item as unknown as Record<string, unknown>;
    const error = typeof attachment.error === "string" ? attachment.error : undefined;
    return [
      {
        id: attachment.id as string,
        clientId:
          typeof attachment.client_attachment_id === "string"
            ? attachment.client_attachment_id
            : undefined,
        sessionId: typeof attachment.session_id === "string" ? attachment.session_id : "",
        storageName: typeof attachment.storage_name === "string" ? attachment.storage_name : "",
        fileName: typeof attachment.file_name === "string" ? attachment.file_name : "",
        mimeType: attachment.mime_type as string,
        sizeBytes: typeof attachment.size_bytes === "number" ? attachment.size_bytes : 0,
        contentLength:
          typeof attachment.content_length === "number" ? attachment.content_length : 0,
        lineCount: typeof attachment.line_count === "number" ? attachment.line_count : 0,
        width: typeof attachment.width === "number" ? attachment.width : null,
        height: typeof attachment.height === "number" ? attachment.height : null,
        url: attachment.url as string,
        ...(error ? { status: "error" as const, error } : {}),
      },
    ];
  });
}

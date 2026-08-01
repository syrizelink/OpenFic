import i18n from "@/i18n";
import type { AgentImageAttachment } from "@/lib/agent.types";

export const MAX_AGENT_IMAGE_ATTACHMENTS = 20;
export const MAX_AGENT_IMAGE_BYTES = 10 * 1024 * 1024;

const SUPPORTED_AGENT_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

export interface PendingAgentImageAttachment {
  id: string;
  file?: File;
  uploadedAttachment?: AgentImageAttachment;
  previewUrl: string;
}

export function createRestoredPendingAgentAttachments(
  attachments: AgentImageAttachment[],
): PendingAgentImageAttachment[] {
  return attachments.map((attachment) => ({
    id: attachment.id,
    previewUrl: attachment.url,
    uploadedAttachment: attachment,
  }));
}

export function getAgentImageFiles(dataTransfer: DataTransfer): File[] {
  const files = Array.from(dataTransfer.files);
  if (files.length > 0) return files;

  return Array.from(dataTransfer.items).flatMap((item) => {
    if (item.kind !== "file") return [];
    const file = item.getAsFile();
    return file ? [file] : [];
  });
}

export function hasLeftAgentImageDropZone(
  relatedTarget: EventTarget | null,
  contains: (target: Node) => boolean,
): boolean {
  return relatedTarget === null || !contains(relatedTarget as Node);
}

export function validateAgentImageFiles(files: File[], existingCount: number): string | null {
  if (existingCount + files.length > MAX_AGENT_IMAGE_ATTACHMENTS) {
    return i18n.t("writing.aiSidebar.imageAttachmentLimit", {
      count: MAX_AGENT_IMAGE_ATTACHMENTS,
    });
  }
  for (const file of files) {
    if (!SUPPORTED_AGENT_IMAGE_TYPES.has(file.type)) {
      return i18n.t("writing.aiSidebar.unsupportedImageType");
    }
    if (file.size > MAX_AGENT_IMAGE_BYTES) return i18n.t("writing.aiSidebar.imageTooLarge");
  }
  return null;
}

export function modelAllowsAgentImages(
  inputModalities: string[] | undefined,
  isCatalogMatched: boolean,
): boolean {
  if (!isCatalogMatched) return true;
  return inputModalities?.some((modality) => modality.toLowerCase() === "image") ?? false;
}

export function isAgentImageAttachment(value: unknown): value is AgentImageAttachment {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const attachment = value as Record<string, unknown>;
  return (
    typeof attachment.id === "string" &&
    typeof attachment.url === "string" &&
    typeof attachment.mime_type === "string"
  );
}

export function normalizeAgentImageAttachments(value: unknown): AgentImageAttachment[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return [];
    const attachment = item as Record<string, unknown>;
    if (
      typeof attachment.id !== "string" ||
      typeof attachment.url !== "string" ||
      typeof attachment.mime_type !== "string"
    )
      return [];
    return [
      {
        id: attachment.id,
        sessionId: typeof attachment.session_id === "string" ? attachment.session_id : "",
        storageName: typeof attachment.storage_name === "string" ? attachment.storage_name : "",
        fileName: typeof attachment.file_name === "string" ? attachment.file_name : "",
        mimeType: attachment.mime_type as AgentImageAttachment["mimeType"],
        sizeBytes: typeof attachment.size_bytes === "number" ? attachment.size_bytes : 0,
        width: typeof attachment.width === "number" ? attachment.width : 0,
        height: typeof attachment.height === "number" ? attachment.height : 0,
        url: attachment.url,
      },
    ];
  });
}

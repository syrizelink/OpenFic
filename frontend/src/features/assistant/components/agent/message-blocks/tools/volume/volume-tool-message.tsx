import i18n from "@/i18n";
import type { AgentMessage } from "@/lib/agent.types";

import { ToolBody, ToolNotice, ToolTextBlock } from "../shared/tool-message-shared";
import {
  asBoolean,
  formatChapterRefLabel,
  formatVolumeDisplayName,
  formatVolumeRefLabel,
  getChapterPayload,
  getToolRef,
  getToolResultData,
  getToolResultMessage,
  getVolumePayload,
  isRecord,
} from "../shared/tool-message-utils";

interface VolumeToolMessageProps {
  message: AgentMessage;
}

function VolumeSummary({
  message,
  emptyTitle,
  emptyDescription,
}: VolumeToolMessageProps & {
  emptyTitle: string;
  emptyDescription: string;
}) {
  const volume = getVolumePayload(message);

  if (!volume) {
    return (
      <ToolNotice title={emptyTitle}>
        {getToolResultMessage(message) ?? emptyDescription}
      </ToolNotice>
    );
  }

  return (
    <>
      <ToolTextBlock
        label={i18n.t("assistant.tools.volume")}
        value={formatVolumeDisplayName(volume)}
      />
      <ToolTextBlock
        label={i18n.t("assistant.tools.descriptionLabel")}
        value={volume.description}
      />
      <ToolTextBlock
        label={i18n.t("assistant.tools.chapterCountLabel")}
        value={
          typeof volume.chapter_count === "number"
            ? i18n.t("assistant.tools.chapterCount", { count: volume.chapter_count })
            : undefined
        }
      />
      <ToolTextBlock
        label={i18n.t("assistant.tools.result")}
        value={getToolResultMessage(message)}
      />
    </>
  );
}

export function CreateVolumeToolMessage({ message }: VolumeToolMessageProps) {
  return (
    <ToolBody>
      <VolumeSummary
        message={message}
        emptyTitle={i18n.t("assistant.tools.noVolumeInfoReturned")}
        emptyDescription={i18n.t("assistant.tools.noVolumeInfoDescription")}
      />
    </ToolBody>
  );
}

export function EditVolumeToolMessage({ message }: VolumeToolMessageProps) {
  return (
    <ToolBody>
      <VolumeSummary
        message={message}
        emptyTitle={i18n.t("assistant.tools.noUpdatedVolumeInfo")}
        emptyDescription={i18n.t("assistant.tools.noUpdatedVolumeInfoDescription")}
      />
    </ToolBody>
  );
}

export function DeleteVolumeToolMessage({ message }: VolumeToolMessageProps) {
  const volumeLabel = formatVolumeRefLabel(getToolRef(message, "volume_ref"));
  const data = message.toolArgs ?? {};
  const cascade = asBoolean(data.cascade);

  return (
    <ToolBody>
      <ToolTextBlock
        label={i18n.t("assistant.tools.targetVolume")}
        value={volumeLabel}
      />
      <ToolTextBlock
        label={i18n.t("assistant.tools.cascadeDeleteChapters")}
        value={
          cascade
            ? i18n.t("assistant.tools.yes")
            : cascade === false
              ? i18n.t("assistant.tools.no")
              : undefined
        }
      />
      <ToolNotice title={i18n.t("assistant.tools.volumeDeleteSubmitted")}>
        {getToolResultMessage(message) ?? i18n.t("assistant.tools.volumeDeleteSuccess")}
      </ToolNotice>
    </ToolBody>
  );
}

export function MoveChapterToVolumeToolMessage({ message }: VolumeToolMessageProps) {
  const sourceVolumeLabel = formatVolumeRefLabel(getToolRef(message, "volume_ref"));
  const targetVolumeLabel = formatVolumeRefLabel(getToolRef(message, "target_volume_ref"));
  const chapterLabel = formatChapterRefLabel(getToolRef(message, "chapter_ref"));
  const chapter = getChapterPayload(message);
  const resultData = getToolResultData(message);
  const affectedCount =
    isRecord(resultData) && Array.isArray(resultData.affected_chapters)
      ? resultData.affected_chapters.length
      : undefined;

  return (
    <ToolBody>
      <ToolTextBlock
        label={i18n.t("assistant.tools.chapter")}
        value={chapter.title ?? chapterLabel}
      />
      <ToolTextBlock
        label={i18n.t("assistant.tools.sourceVolume")}
        value={sourceVolumeLabel}
      />
      <ToolTextBlock
        label={i18n.t("assistant.tools.targetVolume")}
        value={targetVolumeLabel}
      />
      <ToolTextBlock
        label={i18n.t("assistant.tools.affectedChapters")}
        value={
          typeof affectedCount === "number"
            ? i18n.t("assistant.tools.affectedCount", { count: affectedCount })
            : undefined
        }
      />
      <ToolNotice title={i18n.t("assistant.tools.moveChapterSubmitted")}>
        {getToolResultMessage(message) ?? i18n.t("assistant.tools.moveChapterSuccess")}
      </ToolNotice>
    </ToolBody>
  );
}

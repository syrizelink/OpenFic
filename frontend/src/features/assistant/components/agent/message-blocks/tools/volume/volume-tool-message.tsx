import type { AgentMessage } from "@/lib/agent.types";
import i18n from "@/i18n";

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
import {
  ToolBody,
  ToolNotice,
  ToolTextBlock,
} from "../shared/tool-message-shared";

interface VolumeToolMessageProps {
  message: AgentMessage;
}

function VolumeSummary({ message, emptyTitle, emptyDescription }: VolumeToolMessageProps & {
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
      <ToolTextBlock label="卷" value={formatVolumeDisplayName(volume)} />
      <ToolTextBlock label="说明" value={volume.description} />
      <ToolTextBlock
        label="章节数"
        value={typeof volume.chapter_count === "number" ? `${volume.chapter_count} 章` : undefined}
      />
      <ToolTextBlock label="结果" value={getToolResultMessage(message)} />
    </>
  );
}

export function CreateVolumeToolMessage({ message }: VolumeToolMessageProps) {
  return (
    <ToolBody>
      <VolumeSummary
        message={message}
        emptyTitle="未返回新卷信息"
        emptyDescription="这次创建没有返回可显示的卷信息。"
      />
    </ToolBody>
  );
}

export function EditVolumeToolMessage({ message }: VolumeToolMessageProps) {
  return (
    <ToolBody>
      <VolumeSummary
        message={message}
        emptyTitle="未返回更新后的卷信息"
        emptyDescription="这次编辑没有返回可显示的卷信息。"
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
      <ToolTextBlock label={i18n.t("assistant.tools.targetVolume")} value={volumeLabel} />
      <ToolTextBlock label={i18n.t("assistant.tools.cascadeDeleteChapters")} value={cascade ? i18n.t("assistant.tools.yes") : cascade === false ? i18n.t("assistant.tools.no") : undefined} />
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
      <ToolTextBlock label={i18n.t("assistant.tools.chapter")} value={chapter.title ?? chapterLabel} />
      <ToolTextBlock label={i18n.t("assistant.tools.sourceVolume")} value={sourceVolumeLabel} />
      <ToolTextBlock label={i18n.t("assistant.tools.targetVolume")} value={targetVolumeLabel} />
      <ToolTextBlock
        label={i18n.t("assistant.tools.affectedChapters")}
        value={typeof affectedCount === "number" ? `${affectedCount} 个` : undefined}
      />
      <ToolNotice title={i18n.t("assistant.tools.moveChapterSubmitted")}>
        {getToolResultMessage(message) ?? i18n.t("assistant.tools.moveChapterSuccess")}
      </ToolNotice>
    </ToolBody>
  );
}

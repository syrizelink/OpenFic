import type { AgentMessage } from "@/lib/agent.types";

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
      <ToolTextBlock label="目标卷" value={volumeLabel} />
      <ToolTextBlock label="级联删除章节" value={cascade ? "是" : cascade === false ? "否" : undefined} />
      <ToolNotice title="卷删除已提交">
        {getToolResultMessage(message) ?? "卷删除成功。"}
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
      <ToolTextBlock label="章节" value={chapter.title ?? chapterLabel} />
      <ToolTextBlock label="来源卷" value={sourceVolumeLabel} />
      <ToolTextBlock label="目标卷" value={targetVolumeLabel} />
      <ToolTextBlock
        label="影响章节"
        value={typeof affectedCount === "number" ? `${affectedCount} 个` : undefined}
      />
      <ToolNotice title="章节移动已提交">
        {getToolResultMessage(message) ?? "章节已移动到目标卷末尾。"}
      </ToolNotice>
    </ToolBody>
  );
}

import { Database } from "lucide-react";
import { Tooltip } from "@radix-ui/themes";
import { useTranslation } from "react-i18next";

import {
  getIndexStatusColor,
  useProjectIndexStatus,
  type IndexStatus,
} from "@/lib/index-status";

const STATUS_LABEL_KEY: Record<IndexStatus, string> = {
  disabled: "writing.aiSidebar.indexStatusDisabled",
  not_configured: "writing.aiSidebar.indexStatusNotConfigured",
  no_chapters: "writing.aiSidebar.indexStatusNoChapters",
  no_index: "writing.aiSidebar.indexStatusNoIndex",
  indexing: "writing.aiSidebar.indexStatusIndexing",
  needs_rebuild: "writing.aiSidebar.indexStatusNeedsRebuild",
  stale: "writing.aiSidebar.indexStatusStale",
  fresh: "writing.aiSidebar.indexStatusFresh",
  failed: "writing.aiSidebar.indexStatusFailed",
};

interface AgentIndexStatusIndicatorProps {
  projectId: string;
}

/**
 * Agent 输入工具栏的索引状态指示器：不可点击，以颜色反映索引状态。
 * 初始状态由 API 获取，后续由 socket 事件推送更新。
 */
export function AgentIndexStatusIndicator({ projectId }: AgentIndexStatusIndicatorProps) {
  const { t } = useTranslation();
  const { data } = useProjectIndexStatus(projectId);
  const status = data?.status ?? null;
  const color = getIndexStatusColor(status);
  const labelKey = status ? STATUS_LABEL_KEY[status] : "writing.aiSidebar.openRetrievalIndex";

  return (
    <Tooltip content={t(labelKey)}>
      <span
        aria-label={t(labelKey)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: "26px",
          height: "26px",
          borderRadius: "999px",
          color,
        }}
      >
        <Database size={14} />
      </span>
    </Tooltip>
  );
}

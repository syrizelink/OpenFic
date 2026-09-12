import { Tooltip } from "@radix-ui/themes";
import { Database } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getIndexStatusColor, useProjectIndexStatus, type IndexStatus } from "@/lib/index-status";

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
 * Indikator status indeks pada bilah alat masukan Agent: tidak dapat diklik, status indeks dinyatakan lewat warna.
 * Status awal diambil lewat API, pembaruan berikutnya dikirim lewat peristiwa socket.
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

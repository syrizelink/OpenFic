import { HoverCard, Text } from "@radix-ui/themes";
import { useMemo, useSyncExternalStore, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { useAppShell } from "@/features/app-shell/components/app-shell-context";
import { useOverallIndexStatus, type ProjectIndexStatus } from "@/lib/index-status";
import { getSocketConnectionStatus, subscribeSocketConnectionStatus } from "@/lib/socket-client";

import "./status-bar.css";

interface StatusBarItem {
  id: string;
  content: ReactNode;
  isVisible?: boolean;
}

interface StatusBarProps {
  version: string;
}

interface IndexProgressState {
  activeProjects: ProjectIndexStatus[];
  hasFailure: boolean;
  indexableTotal: number;
  indexedTotal: number;
  progress: number;
}

function StatusBarSection({ items, side }: { items: StatusBarItem[]; side: "left" | "right" }) {
  const visibleItems = items.filter((item) => item.isVisible !== false);
  if (visibleItems.length === 0) return null;

  return (
    <div
      className="app-status-bar__section"
      data-side={side}
      data-slot="status-bar-section"
    >
      {visibleItems.map((item) => (
        <div
          className="app-status-bar__item"
          data-slot="status-bar-item"
          key={item.id}
        >
          {item.content}
        </div>
      ))}
    </div>
  );
}

function SocketStatusItem() {
  const status = useSyncExternalStore(
    subscribeSocketConnectionStatus,
    getSocketConnectionStatus,
    getSocketConnectionStatus,
  );
  const isConnected = status === "connected";

  return (
    <span
      className="app-status-bar__connection"
      data-state={status}
      data-slot="socket-status"
      aria-label={isConnected ? "Socket 已连接" : "Socket 连接断开"}
    >
      <span
        className="app-status-bar__connection-dot"
        aria-hidden="true"
      />
      {isConnected ? "已连接" : "连接断开"}
    </span>
  );
}

function getIndexableChapterCount(project: ProjectIndexStatus): number {
  return Math.max(0, project.total_chapters - project.empty_content_count);
}

function getProgressPercentage(indexed: number, total: number): number {
  if (total === 0) return 0;
  return Math.min(100, Math.max(0, (indexed / total) * 100));
}

function getIndexProgressState(projects: ProjectIndexStatus[]): IndexProgressState {
  const indexableTotal = projects.reduce(
    (total, project) => total + getIndexableChapterCount(project),
    0,
  );
  const indexedTotal = projects.reduce((total, project) => total + project.indexed_count, 0);

  return {
    activeProjects: projects.filter((project) => project.in_progress_count > 0),
    hasFailure: projects.some((project) => project.failed_count > 0),
    indexableTotal,
    indexedTotal,
    progress: getProgressPercentage(indexedTotal, indexableTotal),
  };
}

function IndexProgressStatusItem({
  activeProjects,
  hasFailure,
  indexableTotal,
  indexedTotal,
  progress,
}: IndexProgressState) {
  const { t } = useTranslation();
  const { openSettings } = useAppShell();
  const state = hasFailure ? "error" : "indexing";
  const progressText = t("index.progress", { indexed: indexedTotal, total: indexableTotal });

  return (
    <HoverCard.Root>
      <HoverCard.Trigger>
        <button
          type="button"
          className="app-status-bar__index-button"
          data-state={state}
          aria-label={t("index.statusBar.openSettings")}
          onClick={() => openSettings({ category: "index" })}
        >
          <span>{hasFailure ? t("index.statusBar.error") : t("index.statusBar.indexing")}</span>
          <span
            className="app-status-bar__index-progress"
            role="progressbar"
            aria-label={progressText}
            aria-valuemin={0}
            aria-valuemax={indexableTotal}
            aria-valuenow={Math.min(indexableTotal, indexedTotal)}
            aria-valuetext={progressText}
          >
            <span
              className="app-status-bar__index-progress-indicator"
              style={{ width: `${progress}%` }}
            />
          </span>
        </button>
      </HoverCard.Trigger>
      <HoverCard.Content
        side="top"
        align="end"
        size="1"
        className="app-status-bar__index-popover"
      >
        {activeProjects.length > 0 ? (
          <div className="app-status-bar__index-project-list">
            {activeProjects.map((project) => {
              const total = getIndexableChapterCount(project);
              const projectProgress = getProgressPercentage(project.indexed_count, total);
              const projectProgressText = t("index.progress", {
                indexed: project.indexed_count,
                total,
              });

              return (
                <div
                  className="app-status-bar__index-project"
                  key={project.project_id}
                >
                  <Text
                    as="span"
                    size="1"
                    weight="medium"
                    className="app-status-bar__index-project-title"
                  >
                    {project.title || t("index.untitledProject")}
                  </Text>
                  <Text
                    as="span"
                    size="1"
                    color="gray"
                  >
                    {projectProgressText}
                  </Text>
                  <span
                    className="app-status-bar__index-project-progress"
                    role="progressbar"
                    aria-label={projectProgressText}
                    aria-valuemin={0}
                    aria-valuemax={total}
                    aria-valuenow={Math.min(total, project.indexed_count)}
                    aria-valuetext={projectProgressText}
                  >
                    <span
                      className="app-status-bar__index-project-progress-indicator"
                      style={{ width: `${projectProgress}%` }}
                    />
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <Text
            as="p"
            size="1"
            color="red"
            className="app-status-bar__index-error-detail"
          >
            {t("index.statusBar.errorDetail")}
          </Text>
        )}
      </HoverCard.Content>
    </HoverCard.Root>
  );
}

export function StatusBar({ version }: StatusBarProps) {
  const { data: indexStatus } = useOverallIndexStatus();
  const indexProgressState = useMemo(
    () => getIndexProgressState(indexStatus?.projects ?? []),
    [indexStatus?.projects],
  );
  const leftItems = useMemo<StatusBarItem[]>(
    () => [
      {
        id: "version",
        content: <span data-slot="app-version">OpenFic v{version}</span>,
        isVisible: Boolean(version),
      },
    ],
    [version],
  );

  const rightItems = useMemo<StatusBarItem[]>(
    () => [
      {
        id: "index-progress",
        content: <IndexProgressStatusItem {...indexProgressState} />,
        isVisible: indexProgressState.hasFailure || indexProgressState.activeProjects.length > 0,
      },
      {
        id: "socket-status",
        content: <SocketStatusItem />,
      },
    ],
    [indexProgressState],
  );

  return (
    <footer
      className="app-status-bar"
      data-slot="status-bar"
      aria-label="应用状态栏"
    >
      <StatusBarSection
        items={leftItems}
        side="left"
      />
      <StatusBarSection
        items={rightItems}
        side="right"
      />
    </footer>
  );
}

import { useMemo, useSyncExternalStore, type ReactNode } from "react";

import {
  getSocketConnectionStatus,
  subscribeSocketConnectionStatus,
} from "@/lib/socket-client";

import "./status-bar.css";

interface StatusBarItem {
  id: string;
  content: ReactNode;
  isVisible?: boolean;
}

interface StatusBarProps {
  version: string;
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

export function StatusBar({ version }: StatusBarProps) {
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
        id: "socket-status",
        content: <SocketStatusItem />,
      },
    ],
    [],
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

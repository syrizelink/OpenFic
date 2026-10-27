import { Theme } from "@radix-ui/themes";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { createRoot } from "react-dom/client";

import { AppShellContext } from "@/features/app-shell/components/app-shell-context";
import { AgentMessages } from "@/features/assistant/components/agent/agent-messages";
import { useAgentSidebar } from "@/features/assistant/components/agent/agent-sidebar";
import "@/i18n";
import type { AgentMessage } from "@/lib/agent.types";

import "@/styles/index.css";

const noop = () => {};
const shell = {
  isMobile: false,
  isSidebarOpen: false,
  isSettingsOpen: false,
  openSidebar: noop,
  closeSidebar: noop,
  toggleSidebar: noop,
  openSettings: noop,
  closeSettings: noop,
  appendToAssistant: noop,
  isAssistantSidebarOpen: false,
  openAssistantSidebar: noop,
  closeAssistantSidebar: noop,
  registerAssistantSidebarHost: noop,
  clearAssistantSidebarHost: noop,
};
const history: AgentMessage[] = [
  { id: "user", type: "user_request", role: "user", timestamp: 1, content: "历史消息" },
  {
    id: "text",
    type: "text",
    role: "assistant",
    timestamp: 2,
    content: Array.from({ length: 60 }, (_, i) => `历史消息第 ${i} 行`).join("\n\n"),
  },
  {
    id: "tool",
    type: "tool",
    role: "tool",
    timestamp: 3,
    status: "running",
    toolName: "edit_chapter",
    toolArgs: { chapter_ref: "第一章" },
    isStreaming: true,
  },
];
const diffResult = {
  data: {
    metadata: {
      chapter_diff: {
        operation: "update",
        chapter_title: "第一章",
        sections: [
          {
            type: "content",
            lines: Array.from({ length: 30 }, (_, i) => ({
              type: "added",
              after_line_number: i + 1,
              text: `新增第 ${i + 1} 行`,
            })),
          },
        ],
      },
    },
  },
};

export function Fixture() {
  const [messages, setMessages] = useState(history);
  const [running, setRunning] = useState(true);
  const [atBottom, setAtBottom] = useState(true);
  const scrollToBottomFnRef = useRef<(() => void) | null>(null);
  const sidebar = useAgentSidebar({
    projectId: "project",
    modelId: new URLSearchParams(location.search).has("invalid") ? "" : "model",
    inputValue: "新消息",
    attachments: [],
    onClearInput: noop,
    onClearAttachments: noop,
    scrollToBottomFnRef,
  });
  const send = () => {
    void sidebar.onSend();
    if (!new URLSearchParams(location.search).has("invalid")) {
      setRunning(true);
      setMessages((current) => [
        ...current,
        { id: "new-user", type: "user_request", role: "user", timestamp: 4, content: "新消息" },
        {
          id: "reply",
          type: "text",
          role: "assistant",
          timestamp: 5,
          content: "正在回答",
          isStreaming: true,
        },
      ]);
      window.setTimeout(() => {
        setMessages((current) =>
          current.map((message) =>
            message.id === "reply"
              ? {
                  ...message,
                  content: Array.from({ length: 30 }, (_, i) => `回答第 ${i} 行`).join("\n\n"),
                }
              : message,
          ),
        );
      }, 300);
    }
  };
  const completeTool = () => {
    setRunning(false);
    setMessages((current) =>
      current.map((message) =>
        message.id === "tool"
          ? {
              ...message,
              status: "completed",
              isStreaming: false,
              toolSuccess: true,
              toolResult: diffResult,
            }
          : message,
      ),
    );
  };
  return (
    <Theme>
      <AppShellContext.Provider value={shell}>
        <button onClick={send}>发送</button>
        <button onClick={completeTool}>完成工具并结束</button>
        <output data-testid="at-bottom">{String(atBottom)}</output>
        <div
          className="ai-sidebar-messages"
          style={{ height: 400, width: 500, overflowY: "auto", position: "relative" }}
        >
          <AgentMessages
            messages={messages}
            isRunning={running}
            isRollbacking={false}
            status={running ? "running" : "completed"}
            currentStage=""
            onRollback={async () => null}
            onAtBottomChange={setAtBottom}
            scrollToBottomFnRef={scrollToBottomFnRef}
          />
        </div>
      </AppShellContext.Provider>
    </Theme>
  );
}

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <Fixture />
  </QueryClientProvider>,
);

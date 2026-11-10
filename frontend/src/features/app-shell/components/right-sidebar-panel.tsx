import { useEffect, useRef, useState, type ReactNode } from "react";
import { Panel, Separator, usePanelRef } from "react-resizable-panels";

import { useAppShell } from "./app-shell-context";

interface RightSidebarPanelProps {
  id: string;
  children: ReactNode;
}

const COLLAPSED_WIDTH = 0;

export function RightSidebarPanel({ id, children }: RightSidebarPanelProps) {
  const { isAssistantSidebarOpen, closeAssistantSidebar } = useAppShell();
  const panelRef = usePanelRef();
  const expandedWidthRef = useRef(500);
  const previousOpenRef = useRef(isAssistantSidebarOpen);
  const [isTransitioning, setIsTransitioning] = useState(false);

  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return;
    const resizePanel = () => {
      if (isAssistantSidebarOpen) {
        if (panel.isCollapsed()) panel.resize(expandedWidthRef.current);
      } else panel.collapse();
    };
    if (previousOpenRef.current === isAssistantSidebarOpen) {
      resizePanel();
      return;
    }
    previousOpenRef.current = isAssistantSidebarOpen;
    setIsTransitioning(true);
    const frame = window.requestAnimationFrame(resizePanel);
    const timeout = window.setTimeout(() => setIsTransitioning(false), 280);
    return () => {
      window.cancelAnimationFrame(frame);
      window.clearTimeout(timeout);
    };
  }, [isAssistantSidebarOpen, panelRef]);

  return (
    <>
      <Separator
        className="resize-handle right-sidebar-separator"
        disabled={!isAssistantSidebarOpen}
      />
      <Panel
        id={id}
        className="right-sidebar-resizable-panel"
        data-sidebar-transitioning={isTransitioning || undefined}
        data-sidebar-width={expandedWidthRef.current}
        panelRef={panelRef}
        defaultSize={500}
        minSize={300}
        maxSize={600}
        groupResizeBehavior="preserve-pixel-size"
        disabled={!isAssistantSidebarOpen}
        collapsible
        collapsedSize={COLLAPSED_WIDTH}
        onResize={(size, _id, previous) => {
          if (!isAssistantSidebarOpen) return;
          if (size.inPixels > COLLAPSED_WIDTH + 1) expandedWidthRef.current = size.inPixels;
          else if (previous && previous.inPixels > COLLAPSED_WIDTH + 1) closeAssistantSidebar();
        }}
      >
        <div
          className="right-sidebar-panel"
          data-open={isAssistantSidebarOpen}
        >
          <div className="right-sidebar-panel-content">{children}</div>
        </div>
      </Panel>
    </>
  );
}

export interface SelectionSnapshot {
  text: string;
  source: {
    kind: "chapter" | "note" | "character" | "world-info" | "agent-message" | "agent-input";
    id?: string;
    projectId?: string;
  };
  bounds: { x: number; y: number; width: number; height: number };
  target?: { projectId: string; tabId: string; taskId: string | null };
}

export function readSelection(): SelectionSnapshot | null {
  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || selection.rangeCount !== 1) return null;
  const range = selection.getRangeAt(0);
  const start =
    range.startContainer instanceof Element
      ? range.startContainer
      : range.startContainer.parentElement;
  const end =
    range.endContainer instanceof Element ? range.endContainer : range.endContainer.parentElement;
  const source = start?.closest<HTMLElement>("[data-plugin-selection-source]");
  if (!source || source !== end?.closest("[data-plugin-selection-source]")) return null;
  const kind = source.dataset.pluginSelectionSource as SelectionSnapshot["source"]["kind"];
  if (
    !["chapter", "note", "character", "world-info", "agent-message", "agent-input"].includes(kind)
  )
    return null;
  const text = selection.toString();
  if (!text.trim()) return null;
  const bounds = range.getBoundingClientRect();
  const target =
    source.closest<HTMLElement>("[data-plugin-agent-tab]") ??
    document.querySelector<HTMLElement>('[data-plugin-agent-active="true"]');
  const targetProject = target?.dataset.pluginAgentProject;
  const targetTab = target?.dataset.pluginAgentTab;
  return {
    text,
    source: {
      kind,
      ...(source.dataset.pluginSelectionId ? { id: source.dataset.pluginSelectionId } : {}),
      ...(source.dataset.pluginSelectionProject
        ? { projectId: source.dataset.pluginSelectionProject }
        : {}),
    },
    bounds: { x: bounds.x, y: bounds.y, width: bounds.width, height: bounds.height },
    ...(targetProject &&
    targetTab &&
    (kind !== "world-info" || source.dataset.pluginSelectionProject) &&
    target?.closest<HTMLElement>(".app-layout-assistant-sidebar")?.dataset.active === "true" &&
    (!source.dataset.pluginSelectionProject ||
      source.dataset.pluginSelectionProject === targetProject)
      ? {
          target: {
            projectId: targetProject,
            tabId: targetTab,
            taskId: target.dataset.pluginAgentTask || null,
          },
        }
      : {}),
  };
}

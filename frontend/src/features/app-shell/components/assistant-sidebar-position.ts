export function syncAssistantSidebarPosition(sidebar: HTMLElement, host: HTMLElement): void {
  const bounds = host.getBoundingClientRect();
  sidebar.style.left = `${bounds.left}px`;
  sidebar.style.top = `${bounds.top}px`;
  sidebar.style.width = `${bounds.width}px`;
  sidebar.style.height = `${bounds.height}px`;
  const panel = host.closest<HTMLElement>("[data-panel]");
  const expandedWidth = Number(panel?.dataset.sidebarWidth);
  if (
    panel?.dataset.sidebarTransitioning === "true" &&
    Number.isFinite(expandedWidth) &&
    expandedWidth > 0
  ) {
    sidebar.style.setProperty("--assistant-sidebar-content-width", `${expandedWidth}px`);
  } else {
    sidebar.style.removeProperty("--assistant-sidebar-content-width");
  }
}

export function clearAssistantSidebarPosition(sidebar: HTMLElement): void {
  sidebar.style.removeProperty("left");
  sidebar.style.removeProperty("top");
  sidebar.style.removeProperty("width");
  sidebar.style.removeProperty("height");
  sidebar.style.removeProperty("--assistant-sidebar-content-width");
}

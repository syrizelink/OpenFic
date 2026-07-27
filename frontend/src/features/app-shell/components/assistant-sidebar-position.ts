export function syncAssistantSidebarPosition(sidebar: HTMLElement, host: HTMLElement): void {
  const bounds = host.getBoundingClientRect();
  sidebar.style.left = `${bounds.left}px`;
  sidebar.style.top = `${bounds.top}px`;
  sidebar.style.width = `${bounds.width}px`;
  sidebar.style.height = `${bounds.height}px`;
}

export function clearAssistantSidebarPosition(sidebar: HTMLElement): void {
  sidebar.style.removeProperty("left");
  sidebar.style.removeProperty("top");
  sidebar.style.removeProperty("width");
  sidebar.style.removeProperty("height");
}

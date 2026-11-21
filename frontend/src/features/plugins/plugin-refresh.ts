interface PluginRefreshEvent {
  event: string;
  pluginId?: string;
  data?: { viewId?: string; resync?: boolean };
}

export function shouldRefreshPluginView(
  event: PluginRefreshEvent,
  pluginId: string,
  viewId: string,
  capabilities: string[],
): boolean {
  if (event.event === "ui.invalidate")
    return (
      (!event.pluginId || event.pluginId === pluginId) &&
      (!event.data?.viewId || event.data.viewId === viewId)
    );
  if (event.event !== "data.changed") return false;
  return (
    event.data?.resync === true ||
    capabilities.some((capability) => capability.endsWith(".read") || capability === "agent.models")
  );
}

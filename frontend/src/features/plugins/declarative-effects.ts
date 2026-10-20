const methods = new Set([
  "editor.read",
  "editor.insert",
  "editor.replaceSelection",
  "editor.setContent",
  "editor.setSelection",
  "editor.focus",
  "editor.save",
  "editor.undo",
  "editor.redo",
  "ui.navigate",
  "ui.openExternal",
  "ui.toast",
  "ui.confirm",
  "ui.copy",
  "ui.download",
  "ui.invalidate",
  "ui.context",
  "ui.tools",
  "assistant.fill",
]);

/** Effects only run in response to an action, through the capability-checked SDK bridge. */
export async function runUIEffects(
  initial: unknown,
  invoke: (method: string, params: Record<string, unknown>) => Promise<unknown>,
  followup: (id: string, results: unknown[]) => Promise<unknown>,
  active: () => boolean,
) {
  let result = initial;
  for (let step = 0; step < 4; step++) {
    if (!active() || !result || typeof result !== "object" || !("effects" in result)) return result;
    const response = result as { effects: unknown; next?: unknown };
    if (
      !Array.isArray(response.effects) ||
      response.effects.length > 16 ||
      (response.next !== undefined &&
        (typeof response.next !== "string" || !response.next || response.next.length > 128))
    )
      throw new Error("Invalid plugin UI effects");
    // Validate the entire batch before allowing side effects.
    for (const effect of response.effects) {
      if (
        !effect ||
        typeof effect !== "object" ||
        !methods.has(effect.method) ||
        (effect.discardResult !== undefined && typeof effect.discardResult !== "boolean") ||
        (effect.params !== undefined &&
          (!effect.params || typeof effect.params !== "object" || Array.isArray(effect.params)))
      )
        throw new Error("Unsupported plugin UI effect");
    }
    const values: unknown[] = [];
    for (const effect of response.effects) {
      if (!active()) return result;
      const value = await invoke(effect.method, effect.params ?? {});
      values.push(effect.discardResult ? null : (value ?? null));
    }
    if (!active() || !response.next) return result;
    if (step === 3) throw new Error("Plugin UI effect chain exceeds the limit");
    result = await followup(String(response.next), values);
  }
  return result;
}

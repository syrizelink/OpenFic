/**
 * Clipboard Utilities
 *
 * navigator.clipboard 仅在安全上下文(https/localhost)中可用,
 * 在非安全上下文(如 http 局域网部署)或权限被拒时降级为 execCommand。
 */

export type ClipboardReadResult =
  | { ok: true; text: string }
  | { ok: false; reason: "unavailable" | "denied" };

export async function readClipboardText(): Promise<ClipboardReadResult> {
  if (typeof navigator === "undefined" || !navigator.clipboard?.readText) {
    return { ok: false, reason: "unavailable" };
  }
  try {
    return { ok: true, text: await navigator.clipboard.readText() };
  } catch {
    return { ok: false, reason: "denied" };
  }
}

export async function writeClipboardText(text: string): Promise<boolean> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // 权限被拒,继续尝试降级方案
    }
  }
  return copyWithExecCommand(text);
}

function copyWithExecCommand(text: string): boolean {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.setAttribute("inputmode", "none");
  textarea.style.position = "fixed";
  textarea.style.top = "0";
  textarea.style.left = "0";
  textarea.style.opacity = "0";
  textarea.style.pointerEvents = "none";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  let copied = false;
  try {
    copied = document.execCommand("copy");
  } catch {
    copied = false;
  } finally {
    textarea.blur();
    document.body.removeChild(textarea);
  }
  return copied;
}

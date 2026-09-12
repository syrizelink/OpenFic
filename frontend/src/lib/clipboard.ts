/**
 * Clipboard Utilities
 *
 * navigator.clipboard hanya tersedia pada konteks aman (https/localhost),
 * pada konteks tidak aman (misalnya penggelaran http di jaringan lokal) atau saat izin ditolak, digunakan execCommand sebagai penurunan.
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
      // Izin ditolak, penurunan tetap dicoba
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

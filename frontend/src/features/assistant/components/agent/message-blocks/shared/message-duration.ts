export function formatElapsedDuration(ms: number): string {
  const safeMs = Math.max(0, Math.floor(ms));
  const minutes = Math.floor(safeMs / 60000);
  const seconds = Math.floor((safeMs % 60000) / 1000);
  const milliseconds = safeMs % 1000;

  if (minutes > 0) {
    return `${minutes}:${seconds.toString().padStart(2, "0")}.${milliseconds.toString().padStart(3, "0")}`;
  }

  return `${seconds}.${milliseconds.toString().padStart(3, "0")}s`;
}

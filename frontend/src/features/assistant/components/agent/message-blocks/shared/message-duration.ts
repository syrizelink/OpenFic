/**
 * 格式化累计时长：秒向上取整，最多显示到小时。
 * 例：45s、7m 35s、1h 23m 19s
 */
export function formatElapsedDuration(ms: number): string {
  const totalSeconds = Math.max(1, Math.ceil(Math.max(0, ms) / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}

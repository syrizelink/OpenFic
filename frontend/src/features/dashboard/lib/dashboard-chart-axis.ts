const maxXAxisTickCount = 7;

export function getDashboardXAxisTickValues(labels: string[]): string[] {
  if (labels.length <= maxXAxisTickCount) return labels;

  const interval = Math.ceil((labels.length - 1) / (maxXAxisTickCount - 1));
  return labels.filter((_, index) => index % interval === 0 || index === labels.length - 1);
}

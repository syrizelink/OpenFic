export const MAX_TOOLBAR_COMPRESSION_LEVEL = 4;

export interface ToolbarCompressionInput {
  currentLevel: number;
  isOverflowing: boolean;
  contentChanged: boolean;
  allowExpand: boolean;
  widthIncreased: boolean;
}

export function getNextToolbarCompressionLevel({
  currentLevel,
  isOverflowing,
  contentChanged,
  allowExpand,
  widthIncreased,
}: ToolbarCompressionInput): number {
  if (contentChanged && currentLevel > 0) return 0;
  if (isOverflowing && currentLevel < MAX_TOOLBAR_COMPRESSION_LEVEL) return currentLevel + 1;
  if (allowExpand && widthIncreased && !isOverflowing && currentLevel > 0) return currentLevel - 1;
  return currentLevel;
}

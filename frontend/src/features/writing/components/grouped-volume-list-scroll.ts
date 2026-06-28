export interface GroupedVolumeListViewportMetrics {
  groupCount: number;
  itemCount: number;
  visibleRowCount: number;
}

export type BottomAnchoredScrollAdjustment =
  | {
      type: "chapter";
      index: number;
    }
  | {
      type: "group";
      groupIndex: number;
    }
  | {
      type: "top";
    };

interface GetBottomAnchoredScrollAdjustmentForShrinkParams {
  previousMetrics: GroupedVolumeListViewportMetrics | null;
  nextMetrics: GroupedVolumeListViewportMetrics;
  wasAtBottom: boolean;
}

export function getBottomAnchoredScrollAdjustmentForShrink({
  previousMetrics,
  nextMetrics,
  wasAtBottom,
}: GetBottomAnchoredScrollAdjustmentForShrinkParams): BottomAnchoredScrollAdjustment | null {
  if (!previousMetrics || !wasAtBottom) {
    return null;
  }

  if (nextMetrics.visibleRowCount >= previousMetrics.visibleRowCount) {
    return null;
  }

  if (nextMetrics.itemCount > 0) {
    return {
      type: "chapter",
      index: nextMetrics.itemCount - 1,
    };
  }

  if (nextMetrics.groupCount > 0) {
    return {
      type: "group",
      groupIndex: nextMetrics.groupCount - 1,
    };
  }

  return {
    type: "top",
  };
}

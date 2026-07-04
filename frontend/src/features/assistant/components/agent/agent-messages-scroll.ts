export interface ScrollFrameMetrics {
  scrollHeight: number;
  clientHeight: number;
}

export interface ScrollViewportMetrics extends ScrollFrameMetrics {
  scrollTop: number;
}

const FOLLOW_BOTTOM_THRESHOLD_PX = 80;
const PROGRAMMATIC_SCROLL_EPSILON_PX = 1;

export function getDistanceFromBottom({
  scrollHeight,
  scrollTop,
  clientHeight,
}: ScrollViewportMetrics): number {
  return Math.max(0, scrollHeight - scrollTop - clientHeight);
}

export function shouldFollowBottom(metrics: ScrollViewportMetrics): boolean {
  return getDistanceFromBottom(metrics) < FOLLOW_BOTTOM_THRESHOLD_PX;
}

export function shouldTrackStreamingFollowBottom(isRunning: boolean): boolean {
  return isRunning;
}

export function shouldResetFollowBottomForRun(
  previousIsRunning: boolean,
  nextIsRunning: boolean
): boolean {
  return !previousIsRunning && nextIsRunning;
}

export function resolveFollowBottomStateOnScroll({
  previous,
  next,
  wasFollowingBottom,
}: {
  previous: ScrollViewportMetrics | null;
  next: ScrollViewportMetrics;
  wasFollowingBottom: boolean;
}): boolean {
  const isAtBottomNow = shouldFollowBottom(next);
  if (!previous) return isAtBottomNow;
  if (!wasFollowingBottom) return isAtBottomNow;

  const frameChanged =
    previous.scrollHeight !== next.scrollHeight
    || previous.clientHeight !== next.clientHeight;

  if (!frameChanged) return isAtBottomNow;

  // Layout changes can temporarily increase the distance from bottom before the
  // follow-bottom RAF runs. Preserve follow intent unless the user actually
  // moved upward beyond the non-user clamp expected from the new frame.
  const nextMaxScrollTop = Math.max(0, next.scrollHeight - next.clientHeight);
  const expectedScrollTopWithoutUser = Math.min(previous.scrollTop, nextMaxScrollTop);
  const userScrolledUp =
    next.scrollTop < expectedScrollTopWithoutUser - PROGRAMMATIC_SCROLL_EPSILON_PX;

  return !userScrolledUp;
}

export function hasPendingLoadedSessionBottomRestore(
  pendingRestoreKey: string | null | undefined,
  currentScrollKey: string | null | undefined
): boolean {
  return Boolean(pendingRestoreKey && currentScrollKey && pendingRestoreKey === currentScrollKey);
}

export function shouldScheduleLoadedSessionBottomRestoreImmediately(
  hasPendingRestore: boolean,
  hasBoundScrollContainer: boolean
): boolean {
  return hasPendingRestore && hasBoundScrollContainer;
}

export function shouldAutoScrollOnFrameChange(
  previous: ScrollFrameMetrics | null,
  next: ScrollFrameMetrics,
  isFollowingBottom: boolean
): boolean {
  if (!isFollowingBottom) return false;
  if (!previous) return true;
  return previous.scrollHeight !== next.scrollHeight || previous.clientHeight !== next.clientHeight;
}

export function shouldResetFollowBottomForLoad(
  previousKey: string | null | undefined,
  nextKey: string | null | undefined
): boolean {
  return Boolean(nextKey && previousKey !== nextKey);
}

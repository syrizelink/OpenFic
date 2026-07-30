import { useCallback, useEffect, useRef, useState } from "react";
import type { Layout } from "react-resizable-panels";

import { getPreference, setPreference } from "@/lib/local-db";

const SAVE_DELAY = 250;

function parseLayout(value: string | null, panelIds: readonly string[]): Layout | null {
  if (!value) return null;

  try {
    const layout: unknown = JSON.parse(value);
    if (typeof layout !== "object" || layout === null || Array.isArray(layout)) return null;

    const layoutEntries = Object.entries(layout);
    const totalSize = layoutEntries.reduce(
      (total, [, size]) => (typeof size === "number" ? total + size : total),
      0,
    );
    if (
      layoutEntries.length !== panelIds.length ||
      !panelIds.every((panelId) => Object.hasOwn(layout, panelId)) ||
      !layoutEntries.every(
        ([, size]) => typeof size === "number" && Number.isFinite(size) && size >= 0 && size <= 100,
      ) ||
      Math.abs(totalSize - 100) > 0.01
    ) {
      return null;
    }

    return layout as Layout;
  } catch {
    return null;
  }
}

export function usePersistedPanelLayout(
  key: string,
  panelIds: readonly string[],
  isEnabled: boolean,
) {
  const [defaultLayout, setDefaultLayout] = useState<Layout | undefined>(undefined);
  const [isLoaded, setIsLoaded] = useState(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestLayoutRef = useRef<{ key: string; layout: Layout } | null>(null);

  useEffect(() => {
    let isDiscarded = false;
    setDefaultLayout(undefined);
    if (!isEnabled) {
      setIsLoaded(true);
      return;
    }
    setIsLoaded(false);

    void getPreference(key).then((value) => {
      if (isDiscarded) return;

      setDefaultLayout(parseLayout(value, panelIds) ?? undefined);
      setIsLoaded(true);
    });

    return () => {
      isDiscarded = true;
    };
  }, [isEnabled, key, panelIds]);

  const onLayoutChanged = useCallback(
    (layout: Layout) => {
      if (!isEnabled) return;
      latestLayoutRef.current = { key, layout };
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);

      saveTimerRef.current = setTimeout(() => {
        saveTimerRef.current = null;
        const latestLayout = latestLayoutRef.current;
        if (latestLayout?.key === key) {
          void setPreference(key, JSON.stringify(latestLayout.layout));
        }
      }, SAVE_DELAY);
    },
    [isEnabled, key],
  );

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }

      const latestLayout = latestLayoutRef.current;
      if (latestLayout?.key === key) {
        void setPreference(key, JSON.stringify(latestLayout.layout));
      }
    };
  }, [isEnabled, key]);

  return { defaultLayout, isLoaded, onLayoutChanged };
}

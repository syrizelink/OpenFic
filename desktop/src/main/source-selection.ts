import type { DownloadSourcePreference } from "../shared/config.js";

export interface DownloadSource {
  kind: "default" | "mirror";
  url: string;
}

/** Keep unavailable candidates as fallbacks: a probe is only a point-in-time observation. */
export async function orderDownloadSources<T extends DownloadSource>(
  sources: readonly T[],
  preference: DownloadSourcePreference,
  probe: (source: T) => Promise<void>,
): Promise<T[]> {
  if (preference !== "auto") {
    return [...sources].sort((a, b) => Number(b.kind === preference) - Number(a.kind === preference));
  }
  const measurements = await Promise.all(sources.map(async (source, index) => {
    const start = performance.now();
    try {
      await probe(source);
      return { source, index, elapsed: performance.now() - start };
    } catch {
      return { source, index, elapsed: Number.POSITIVE_INFINITY };
    }
  }));
  return measurements.sort((a, b) => (a.elapsed - b.elapsed) || a.index - b.index).map(({ source }) => source);
}

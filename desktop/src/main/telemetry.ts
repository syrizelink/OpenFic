import { PostHog } from "posthog-node";

const POSTHOG_API_KEY = "phc_kHbik4h8n5KHfZxyTbddA2p6y8zxRNGpsDBNycizyK68";
const POSTHOG_HOST = "https://us.i.posthog.com";

let client: PostHog | null = null;

interface RuntimeConfigResponse {
  posthog_enabled: boolean;
  posthog_api_key: string;
  posthog_host: string;
}

function sanitizeError(error: unknown): Record<string, unknown> {
  if (error instanceof Error) {
    return {
      name: error.name,
      message: error.message.slice(0, 2000),
      stack: error.stack?.slice(0, 5000),
    };
  }
  if (typeof error === "string") {
    return { message: error.slice(0, 2000) };
  }
  return {};
}

/** Diinisialisasi saat aplikasi dijalankan (key publik hardcode), mencakup galat proses utama pada tahap setup/boot. */
export function startErrorTelemetry(): void {
  if (client) return;
  try {
    client = new PostHog(POSTHOG_API_KEY, { host: POSTHOG_HOST });
  } catch {
    client = null;
  }
}

/** Sinkronkan sakelar setelah backend siap: berhenti melapor saat pengguna menonaktifkan telemetri di pengaturan. */
export async function syncTelemetryEnabled(backendBaseUrl: string): Promise<void> {
  try {
    const response = await fetch(`${backendBaseUrl}/api/v1/runtime-config`, {
      cache: "no-store",
    });
    if (!response.ok) return;
    const config = (await response.json()) as RuntimeConfigResponse;
    if (config.posthog_enabled) return;

    const previous = client;
    client = null;
    if (previous) {
      try {
        await previous.flush();
      } catch {
        // Diabaikan.
      }
    }
  } catch {
    // Diabaikan.
  }
}

/** Laporkan pengecualian (proses tetap berjalan, event masuk ke antrean batch). */
export function captureException(error: unknown, properties?: Record<string, unknown>): void {
  if (!client) return;
  try {
    client.captureException(error, undefined, {
      source: "desktop-main",
      ...sanitizeError(error),
      ...properties,
    });
  } catch {
    // Abaikan kegagalan pelaporan.
  }
}

/** Laporkan pengecualian secara langsung (dipakai sebelum proses keluar). */
export async function captureExceptionImmediate(error: unknown): Promise<void> {
  if (!client) return;
  try {
    await client.captureExceptionImmediate(error, undefined, {
      source: "desktop-main",
      ...sanitizeError(error),
    });
  } catch {
    // Abaikan kegagalan pelaporan.
  }
}

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

/** 应用启动即初始化（硬编码公开 key），覆盖 setup/boot 阶段的主进程错误。 */
export function startErrorTelemetry(): void {
  if (client) return;
  try {
    client = new PostHog(POSTHOG_API_KEY, { host: POSTHOG_HOST });
  } catch {
    client = null;
  }
}

/** 后端就绪后同步开关：用户在设置里关闭遥测时停止上报。 */
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
        // 忽略。
      }
    }
  } catch {
    // 忽略。
  }
}

/** 上报异常（进程继续运行，事件进入批量队列）。 */
export function captureException(error: unknown, properties?: Record<string, unknown>): void {
  if (!client) return;
  try {
    client.captureException(error, undefined, {
      source: "desktop-main",
      ...sanitizeError(error),
      ...properties,
    });
  } catch {
    // 忽略上报失败。
  }
}

/** 立即上报异常（供进程即将退出前使用）。 */
export async function captureExceptionImmediate(error: unknown): Promise<void> {
  if (!client) return;
  try {
    await client.captureExceptionImmediate(error, undefined, {
      source: "desktop-main",
      ...sanitizeError(error),
    });
  } catch {
    // 忽略上报失败。
  }
}

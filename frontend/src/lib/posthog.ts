/**
 * PostHog Error Telemetry
 *
 * 前端错误遥测：从后端 runtime-config 读取配置并初始化 posthog-js，
 * 捕获未处理的 JS 异常与 Promise rejection。仅上报错误，不采集产品行为。
 */

import posthog from "posthog-js";

import { getApiBaseUrl } from "./api-client";

let initialized = false;
let cachedConfig: { apiKey: string; host: string } | null = null;
let onErrorHandler: ((event: ErrorEvent) => void) | null = null;
let onRejectionHandler: ((event: PromiseRejectionEvent) => void) | null = null;

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

async function fetchRuntimeConfig(): Promise<RuntimeConfigResponse | null> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/runtime-config`, {
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) return null;
    return (await response.json()) as RuntimeConfigResponse;
  } catch {
    return null;
  }
}

function installGlobalErrorHandlers(): void {
  onErrorHandler = (event: ErrorEvent) => {
    const error = event.error ?? event.message;
    if (!error) return;
    captureException(error, { source: "window-error" });
  };
  onRejectionHandler = (event: PromiseRejectionEvent) => {
    captureException(event.reason, { source: "unhandled-rejection" });
  };
  window.addEventListener("error", onErrorHandler);
  window.addEventListener("unhandledrejection", onRejectionHandler);
}

function removeGlobalErrorHandlers(): void {
  if (onErrorHandler) window.removeEventListener("error", onErrorHandler);
  if (onRejectionHandler) window.removeEventListener("unhandledrejection", onRejectionHandler);
  onErrorHandler = null;
  onRejectionHandler = null;
}

function startCapturing(): void {
  if (!cachedConfig) return;

  posthog.init(cachedConfig.apiKey, {
    api_host: cachedConfig.host,
    autocapture: false,
    capture_pageview: false,
    capture_pageleave: false,
    disable_session_recording: true,
    advanced_disable_flags: true,
    disable_external_dependency_loading: true,
  });
  installGlobalErrorHandlers();
  initialized = true;
}

/**
 * 初始化错误遥测（非阻塞，失败静默忽略）。
 * 仅在后端返回 posthog_enabled 且配置了 key 时生效。
 */
export async function initErrorTelemetry(): Promise<void> {
  try {
    const config = await fetchRuntimeConfig();
    if (!config || !config.posthog_enabled || !config.posthog_api_key) return;

    cachedConfig = { apiKey: config.posthog_api_key, host: config.posthog_host };
    startCapturing();
  } catch {
    // 遥测失败不影响应用运行。
  }
}

/** 上报一个异常（供 React ErrorBoundary 使用）。 */
export function captureException(error: unknown, metadata?: Record<string, unknown>): void {
  if (!initialized) return;
  try {
    posthog.captureException(error, {
      ...sanitizeError(error),
      ...metadata,
    });
  } catch {
    // 忽略上报失败。
  }
}

/** 关闭遥测（供设置页关闭开关时使用）。 */
export function shutdownTelemetry(): void {
  if (!initialized) return;
  try {
    posthog.shutdown();
  } catch {
    // 忽略。
  }
  removeGlobalErrorHandlers();
  initialized = false;
}

/** 供设置页开关切换时同步前端上报状态。 */
export function setTelemetryEnabled(enabled: boolean): void {
  if (enabled) {
    if (cachedConfig) {
      startCapturing();
    } else {
      void initErrorTelemetry();
    }
  } else {
    shutdownTelemetry();
  }
}

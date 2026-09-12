/**
 * PostHog Error Telemetry
 *
 * Telemetri galat frontend: membaca konfigurasi dari runtime-config backend lalu menginisialisasi posthog-js,
 * menangkap anomali JS dan Promise rejection yang tidak tertangani. Hanya galat yang dilaporkan, perilaku produk tidak dikumpulkan.
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
 * Menginisialisasi telemetri galat (tidak memblokir, kegagalan diabaikan diam-diam).
 * Hanya berlaku bila backend mengembalikan posthog_enabled dan key sudah dikonfigurasi.
 */
export async function initErrorTelemetry(): Promise<void> {
  try {
    const config = await fetchRuntimeConfig();
    if (!config || !config.posthog_enabled || !config.posthog_api_key) return;

    cachedConfig = { apiKey: config.posthog_api_key, host: config.posthog_host };
    startCapturing();
  } catch {
    // Kegagalan telemetri tidak memengaruhi jalannya aplikasi.
  }
}

/** Melaporkan satu anomali (dipakai oleh React ErrorBoundary). */
export function captureException(error: unknown, metadata?: Record<string, unknown>): void {
  if (!initialized) return;
  try {
    posthog.captureException(error, {
      ...sanitizeError(error),
      ...metadata,
    });
  } catch {
    // Kegagalan pelaporan diabaikan.
  }
}

/** Menonaktifkan telemetri (dipakai saat saklar di halaman pengaturan dimatikan). */
export function shutdownTelemetry(): void {
  if (!initialized) return;
  try {
    posthog.shutdown();
  } catch {
    // Diabaikan.
  }
  removeGlobalErrorHandlers();
  initialized = false;
}

/** Menyinkronkan status pelaporan frontend saat saklar di halaman pengaturan diubah. */
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

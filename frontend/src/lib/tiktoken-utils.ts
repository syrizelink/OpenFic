/**
 * Tiktoken Utilities
 *
 * 使用 js-tiktoken/lite 按需加载编码表，避免将 wasm 版本打进首屏包。
 */

import type { Tiktoken } from "js-tiktoken/lite";

const DEFAULT_ENCODING = "o200k_base";
const FALLBACK_ENCODING = "cl100k_base";

let globalEncoding: Tiktoken | null = null;
let currentEncodingName: string | null = null;
let encodingPromise: Promise<Tiktoken> | null = null;

async function loadEncodingModule(encodingName: string) {
  if (encodingName === "o200k_base") {
    return import("js-tiktoken/ranks/o200k_base");
  }

  if (encodingName === "cl100k_base") {
    return import("js-tiktoken/ranks/cl100k_base");
  }

  throw new Error(`Unsupported encoding: ${encodingName}`);
}

function setEncodingInstance(encodingName: string, encoding: Tiktoken): Tiktoken {
  globalEncoding = encoding;
  currentEncodingName = encodingName;
  return encoding;
}

async function createEncoding(encodingName: string): Promise<Tiktoken> {
  const { Tiktoken: LiteTiktoken } = await import("js-tiktoken/lite");
  const module = await loadEncodingModule(encodingName);
  return new LiteTiktoken(module.default);
}

export async function preloadTiktokenEncoding(
  encodingName: string = DEFAULT_ENCODING,
): Promise<Tiktoken> {
  if (globalEncoding && currentEncodingName === encodingName) {
    return globalEncoding;
  }

  if (encodingPromise) {
    return encodingPromise;
  }

  if (globalEncoding) {
    freeEncoding();
  }

  encodingPromise = createEncoding(encodingName)
    .then((encoding) => setEncodingInstance(encodingName, encoding))
    .catch(async (error) => {
      console.warn(
        `Failed to initialize encoding "${encodingName}", falling back to "${FALLBACK_ENCODING}":`,
        error,
      );

      if (encodingName === FALLBACK_ENCODING) {
        throw error;
      }

      const fallbackEncoding = await createEncoding(FALLBACK_ENCODING);
      return setEncodingInstance(FALLBACK_ENCODING, fallbackEncoding);
    })
    .catch((fallbackError) => {
      console.error("Failed to initialize fallback encoding:", fallbackError);
      throw new Error("Failed to initialize Tiktoken encoding");
    })
    .finally(() => {
      encodingPromise = null;
    });

  return encodingPromise;
}

export function countTokens(text: string, encodingName: string = DEFAULT_ENCODING): number {
  if (!text || text.trim().length === 0) {
    return 0;
  }

  try {
    if (!globalEncoding || currentEncodingName !== encodingName) {
      void preloadTiktokenEncoding(encodingName).catch((error) => {
        console.warn("Failed to preload Tiktoken encoding:", error);
      });

      return Math.ceil(text.length / 3);
    }

    return globalEncoding.encode(text).length;
  } catch (error) {
    console.warn("Failed to count tokens with Tiktoken, using fallback estimation:", error);
    return Math.ceil(text.length / 3);
  }
}

export function freeEncoding(): void {
  if (globalEncoding) {
    globalEncoding = null;
    currentEncodingName = null;
  }
}

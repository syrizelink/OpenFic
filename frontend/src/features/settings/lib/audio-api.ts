import { apiClient } from "@/lib/api-client";

export const ASR_PROVIDERS = [
  "sensevoice",
  "openai",
  "groq",
  "mistral",
  "deepgram",
  "azure",
] as const;
export type ASRProvider = (typeof ASR_PROVIDERS)[number];
export type ModelDownloadSource = "auto" | "huggingface" | "hf-mirror";
export interface ASRPreparationProgress {
  status: "idle" | "selecting_source" | "downloading" | "verifying" | "ready" | "failed";
  downloaded_bytes: number;
  total_bytes: number;
  file_name: string;
  source: string;
}
export function isPreparationActive(progress?: ASRPreparationProgress): boolean {
  return Boolean(
    progress && ["selecting_source", "downloading", "verifying"].includes(progress.status),
  );
}
export interface ASRProviderConfig {
  base_url: string;
  model: string;
  download_source: ModelDownloadSource;
  model_path: string;
  tokens_path: string;
  vad_path: string;
  has_api_key?: boolean;
}
export interface ASRSettings {
  enabled: boolean;
  provider: ASRProvider;
  language: string;
  providers: Record<ASRProvider, ASRProviderConfig>;
}
export const ASR_DEFAULTS: Partial<Record<ASRProvider, [string, string]>> = {
  openai: ["https://api.openai.com/v1", "whisper-1"],
  groq: ["https://api.groq.com/openai/v1", "whisper-large-v3-turbo"],
  mistral: ["https://api.mistral.ai/v1", "voxtral-mini-latest"],
  deepgram: ["https://api.deepgram.com/v1", "nova-3"],
  azure: ["https://eastus.api.cognitive.microsoft.com", ""],
};
export const EMPTY_ASR_CONFIG: ASRProviderConfig = {
  base_url: "",
  model: "",
  download_source: "auto",
  model_path: "",
  tokens_path: "",
  vad_path: "",
};
export async function fetchASRSettings(): Promise<ASRSettings> {
  return (await apiClient.get("/audio/config")).data;
}
export async function saveASRSettings(
  settings: ASRSettings,
  apiKey?: string,
): Promise<ASRSettings> {
  const config = { ...settings.providers[settings.provider] };
  delete config.has_api_key;
  return (
    await apiClient.put("/audio/config", {
      enabled: settings.enabled,
      provider: settings.provider,
      language: settings.language,
      config,
      ...(apiKey !== undefined ? { api_key: apiKey } : {}),
    })
  ).data;
}
export async function transcribeAudio(
  audio: Blob,
  signal: AbortSignal,
  requestId: string,
): Promise<string> {
  const form = new FormData();
  form.append("file", audio, "audio.wav");
  form.append("request_id", requestId);
  const result = await apiClient.post("/audio/transcriptions", form, {
    headers: { "Content-Type": "multipart/form-data" },
    signal,
    timeout: 190000,
  });
  return result.data.text;
}

export async function cancelTranscription(requestId: string): Promise<void> {
  await apiClient.delete(`/audio/transcriptions/${requestId}`);
}

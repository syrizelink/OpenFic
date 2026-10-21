import type { ASRProvider } from "./audio-api";
import { ProviderIcon } from "./provider-icons";

// Vendored thesvg assets; provenance and license live alongside the SVGs.
const ICONS: Record<ASRProvider, string> = {
  sensevoice: "qwen",
  openai: "openai",
  groq: "groq",
  mistral: "mistral",
  deepgram: "deepgram",
  azure: "azure",
};

export function ASRProviderIcon({ provider }: { provider: ASRProvider }) {
  return (
    <span
      className="audio-settings-provider-icon"
      data-asr-provider={provider}
    >
      <ProviderIcon
        iconPath={`/provider-icons/asr/${ICONS[provider]}.svg`}
        preserveColors={provider !== "openai" && provider !== "sensevoice"}
        size={16}
      />
    </span>
  );
}

import { IconButton } from "@radix-ui/themes";
import { ArrowUp, Square, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components/spinner";

import type { VoiceInputController } from "../../hooks/use-voice-input";

import "./agent-voice-input.css";

const WAVEFORM_STEP_MS = 120;

function VoiceWaveform({ analyser }: { analyser: AnalyserNode | null }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const ctx = element.getContext("2d");
    if (!ctx) return;
    const samples = new Float32Array(analyser?.fftSize ?? 1024);
    const levels = new Array<number>(49).fill(0);
    let frame = 0;
    let previous = 0;
    function draw(time: number) {
      if (!element || !ctx) return;
      if (time - previous >= WAVEFORM_STEP_MS) {
        previous = time;
        let energy = 0;
        if (analyser) {
          analyser.getFloatTimeDomainData(samples);
          energy = Math.sqrt(
            samples.reduce((sum, value) => sum + value * value, 0) / samples.length,
          );
        }
        levels.push(Math.min(1, energy * 5));
        levels.shift();
      }
      const width = element.clientWidth;
      const height = element.clientHeight;
      const ratio = window.devicePixelRatio || 1;
      if (
        element.width !== Math.round(width * ratio) ||
        element.height !== Math.round(height * ratio)
      ) {
        element.width = Math.round(width * ratio);
        element.height = Math.round(height * ratio);
      }
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = getComputedStyle(element).color;
      const step = width / (levels.length - 1);
      const offset = Math.min(1, (time - previous) / WAVEFORM_STEP_MS);
      levels.forEach((level, index) => {
        const bar = 4 + level * (height - 8);
        ctx.globalAlpha = 0.3 + (index / levels.length) * 0.7;
        ctx.beginPath();
        ctx.roundRect(
          (index - offset) * step,
          (height - bar) / 2,
          Math.min(4, step * 0.55),
          bar,
          2,
        );
        ctx.fill();
      });
      frame = requestAnimationFrame(draw);
    }
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [analyser]);
  const { t } = useTranslation();
  return (
    <canvas
      ref={canvas}
      className="agent-voice-waveform"
      role="img"
      aria-label={t("speech.waveform")}
    />
  );
}

export function AgentVoiceInput({
  voice,
  canSend,
}: {
  voice: VoiceInputController;
  canSend: boolean;
}) {
  const { t } = useTranslation();
  const actionable = voice.state === "recording" || voice.retryable;
  const cancel = voice.cancel;
  useEffect(() => {
    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !event.defaultPrevented) {
        event.preventDefault();
        cancel();
      }
    };
    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, [cancel]);
  return (
    <div
      className="agent-voice-input"
      data-state={voice.state}
    >
      <div className="agent-voice-row">
        <IconButton
          type="button"
          className="agent-voice-button agent-voice-cancel"
          variant="ghost"
          color="gray"
          size="1"
          aria-label={t("common.cancel")}
          title={t("common.cancel")}
          onClick={voice.cancel}
        >
          <X size={14} />
        </IconButton>
        <div className="agent-voice-content">
          {voice.state === "recording" ? (
            <VoiceWaveform analyser={voice.analyser} />
          ) : (
            <div
              className="agent-voice-status"
              role="status"
            >
              {voice.state !== "error" ? <Spinner size={12} /> : null}
              {t(
                voice.state === "error"
                  ? voice.retryable
                    ? "speech.retry"
                    : "speech.title"
                  : `speech.${voice.state}`,
              )}
            </div>
          )}
        </div>
        <IconButton
          type="button"
          className="agent-voice-button agent-voice-stop"
          variant="ghost"
          color="gray"
          size="1"
          disabled={!actionable}
          aria-label={t("speech.stop")}
          title={t("speech.stop")}
          onClick={() => voice.finish("stop")}
        >
          <Square
            size={12}
            fill="currentColor"
          />
        </IconButton>
        <IconButton
          type="button"
          className="agent-voice-button agent-voice-send ai-sidebar-send-button"
          variant="solid"
          size="1"
          disabled={!actionable || !canSend}
          aria-label={t("speech.send")}
          title={t("speech.send")}
          onClick={() => voice.finish("send")}
        >
          <ArrowUp size={14} />
        </IconButton>
      </div>
      {voice.error ? (
        <div
          role="alert"
          className="agent-voice-error"
        >
          {voice.error}
        </div>
      ) : (
        <span
          className="agent-voice-sr-status"
          role="status"
        >
          {t(`speech.${voice.state}`)}
        </span>
      )}
    </div>
  );
}

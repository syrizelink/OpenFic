import { IconButton } from "@radix-ui/themes";
import { ArrowUp, Square, X } from "lucide-react";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import { Spinner } from "@/components/spinner";

import type { VoiceInputController } from "../../hooks/use-voice-input";

import "./agent-voice-input.css";

function VoiceWaveform({ analyser }: { analyser: AnalyserNode | null }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const ctx = element.getContext("2d");
    if (!ctx) return;
    const samples = new Float32Array(analyser?.fftSize ?? 1024);
    const levels = new Array<number>(48).fill(0);
    let frame = 0;
    let previous = 0;
    function draw(time: number) {
      if (!element || !ctx) return;
      if (time - previous >= 45) {
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
        const step = width / levels.length;
        levels.forEach((level, index) => {
          const bar = 4 + level * (height - 8);
          ctx.globalAlpha = 0.3 + (index / levels.length) * 0.7;
          ctx.beginPath();
          ctx.roundRect(index * step, (height - bar) / 2, Math.min(4, step * 0.55), bar, 2);
          ctx.fill();
        });
      }
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
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => {
    root.current?.focus();
  }, []);
  return (
    <div
      ref={root}
      className="agent-voice-input"
      data-state={voice.state}
      tabIndex={-1}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          voice.cancel();
        }
      }}
    >
      <div className="agent-voice-row">
        <div className="agent-voice-content">
          {voice.state === "recording" ? (
            <VoiceWaveform analyser={voice.analyser} />
          ) : (
            <div
              className="agent-voice-status"
              role="status"
            >
              {voice.state !== "error" ? <Spinner size={18} /> : null}
              {t(
                voice.state === "error"
                  ? voice.retryable
                    ? "speech.retryHint"
                    : "speech.title"
                  : `speech.${voice.state}`,
              )}
            </div>
          )}
        </div>
        <IconButton
          type="button"
          className="agent-voice-stop"
          variant="soft"
          color="gray"
          radius="full"
          size="3"
          aria-label={t(actionable ? "speech.stop" : "common.cancel")}
          title={t(actionable ? "speech.stop" : "common.cancel")}
          onClick={() => (actionable ? voice.finish("stop") : voice.cancel())}
        >
          {actionable ? (
            <Square
              size={15}
              fill="currentColor"
            />
          ) : (
            <X size={18} />
          )}
        </IconButton>
        <IconButton
          type="button"
          className="agent-voice-send"
          variant="solid"
          color="gray"
          highContrast
          radius="full"
          size="3"
          disabled={!actionable || !canSend}
          aria-label={t("speech.send")}
          title={t("speech.send")}
          onClick={() => voice.finish("send")}
        >
          <ArrowUp size={22} />
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

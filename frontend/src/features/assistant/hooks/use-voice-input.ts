import axios from "axios";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { v4 as uuidv4 } from "uuid";

import { cancelTranscription, transcribeAudio } from "@/features/settings/lib/audio-api";
import { toSpeechWave } from "@/lib/speech-audio";

type VoiceState = "idle" | "permission" | "recording" | "transcribing" | "error";
export type VoiceAction = "stop" | "send";

/** Owns microphone, analyser and ASR cancellation for one composer session. */
export function useVoiceInput({
  disabled,
  scope,
  onResult,
}: {
  disabled: boolean;
  scope: string;
  onResult: (text: string, action: VoiceAction) => void;
}) {
  const { t } = useTranslation();
  const [state, setState] = useState<VoiceState>("idle");
  const [error, setError] = useState("");
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);
  const generation = useRef(0);
  const media = useRef<MediaStream | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const context = useRef<AudioContext | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abort = useRef<AbortController | null>(null);
  const requestId = useRef<string | null>(null);
  const audio = useRef<Blob | null>(null);
  const action = useRef<VoiceAction>("stop");
  const inFlight = useRef(false);
  const latest = useRef({ disabled, onResult });
  latest.current = { disabled, onResult };

  function releaseMicrophone() {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
    media.current?.getTracks().forEach((track) => track.stop());
    media.current = null;
    if (context.current) void context.current.close().catch(() => undefined);
    context.current = null;
  }
  function dispose() {
    generation.current++;
    abort.current?.abort();
    if (requestId.current) void cancelTranscription(requestId.current).catch(() => undefined);
    requestId.current = null;
    if (recorder.current?.state === "recording") recorder.current.stop();
    recorder.current = null;
    releaseMicrophone();
    audio.current = null;
    inFlight.current = false;
  }
  function cancel() {
    dispose();
    setState("idle");
    setAnalyser(null);
    setError("");
  }
  useEffect(() => {
    cancel();
    return dispose;
  }, [scope]);
  useEffect(() => {
    if (disabled) cancel();
  }, [disabled]);

  async function recognize(blob: Blob, token: number) {
    setState("transcribing");
    setAnalyser(null);
    setError("");
    audio.current = blob;
    const controller = new AbortController();
    abort.current = controller;
    try {
      const wave = await toSpeechWave(blob);
      if (token !== generation.current) return;
      const identity = uuidv4();
      requestId.current = identity;
      const text = await transcribeAudio(wave, controller.signal, identity);
      if (token !== generation.current || latest.current.disabled) return;
      requestId.current = null;
      if (!text.trim()) throw new Error("noSpeech");
      latest.current.onResult(text, action.current);
      audio.current = null;
      setState("idle");
      inFlight.current = false;
    } catch (reason) {
      if (token !== generation.current) return;
      requestId.current = null;
      const detail = axios.isAxiosError(reason) ? reason.response?.data?.detail : null;
      setError(
        typeof detail === "string"
          ? `${t("speech.failed")}: ${detail}`
          : t(
              reason instanceof Error &&
                ["noSpeech", "audioTooLong", "audioTooLarge"].includes(reason.message)
                ? `speech.${reason.message}`
                : "speech.failed",
            ),
      );
      setState("error");
      inFlight.current = false;
    }
  }
  async function start() {
    if (inFlight.current || latest.current.disabled) return;
    inFlight.current = true;
    setState("permission");
    setError("");
    const token = generation.current;
    try {
      if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined")
        throw new Error("unsupported");
      const ctx = new AudioContext();
      context.current = ctx;
      await ctx.resume();
      if (token !== generation.current) return;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (token !== generation.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      media.current = stream;
      const source = ctx.createMediaStreamSource(stream);
      const meter = ctx.createAnalyser();
      meter.fftSize = 1024;
      source.connect(meter);
      setAnalyser(meter);
      const recording = new MediaRecorder(stream);
      recorder.current = recording;
      const chunks: Blob[] = [];
      recording.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      recording.onerror = () => {
        if (token !== generation.current) return;
        dispose();
        setAnalyser(null);
        setState("error");
        setError(t("speech.microphoneFailed"));
      };
      recording.onstop = () => {
        if (token !== generation.current) return;
        releaseMicrophone();
        void recognize(new Blob(chunks, { type: recording.mimeType }), token);
      };
      action.current = "stop";
      recording.start(250);
      setState("recording");
      timer.current = setTimeout(() => finish("stop"), 299000);
    } catch (reason) {
      if (token !== generation.current) return;
      releaseMicrophone();
      setAnalyser(null);
      inFlight.current = false;
      setState("error");
      setError(
        t(
          reason instanceof Error && reason.message === "unsupported"
            ? `speech.${reason.message}`
            : "speech.microphoneFailed",
        ),
      );
    }
  }
  function finish(next: VoiceAction) {
    if (recorder.current?.state === "recording") {
      action.current = next;
      // Disable both actions synchronously to prevent duplicate stop/send clicks.
      setState("transcribing");
      recorder.current.stop();
    } else if (state === "error" && audio.current && !inFlight.current) {
      inFlight.current = true;
      action.current = next;
      void recognize(audio.current, generation.current);
    }
  }
  return {
    state,
    active: state !== "idle",
    error,
    analyser,
    retryable: state === "error" && Boolean(audio.current),
    start,
    finish,
    cancel,
  };
}

export type VoiceInputController = ReturnType<typeof useVoiceInput>;

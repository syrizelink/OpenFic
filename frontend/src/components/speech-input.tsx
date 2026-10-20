import { Button, Dialog, Flex, IconButton, Text, TextArea } from "@radix-ui/themes";
import { useQuery } from "@tanstack/react-query";
import axios from "axios";
import { FileAudio, Mic } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { v4 as uuidv4 } from "uuid";

import {
  cancelTranscription,
  fetchASRSettings,
  transcribeAudio,
} from "@/features/settings/lib/audio-api";
import { toSpeechWave } from "@/lib/speech-audio";

export function SpeechInput({
  onInsert,
  disabled = false,
  uploadOnly = false,
}: {
  onInsert: (text: string) => void;
  disabled?: boolean;
  uploadOnly?: boolean;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<"idle" | "permission" | "recording" | "transcribing">("idle");
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const [audio, setAudio] = useState<Blob | null>(null);
  const generation = useRef(0);
  const stream = useRef<MediaStream | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const abort = useRef<AbortController | null>(null);
  const requestId = useRef<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { data: settings, isError } = useQuery({
    queryKey: ["asr-settings"],
    queryFn: fetchASRSettings,
    enabled: open,
  });

  function cleanup() {
    generation.current++;
    abort.current?.abort();
    if (requestId.current) void cancelTranscription(requestId.current).catch(() => undefined);
    requestId.current = null;
    if (timer.current) clearTimeout(timer.current);
    if (recorder.current?.state === "recording") recorder.current.stop();
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
    recorder.current = null;
  }
  useEffect(() => () => cleanup(), []);
  useEffect(() => {
    if (disabled) {
      cleanup();
      setState("idle");
    }
  }, [disabled]);

  async function recognize(blob: Blob, token = generation.current) {
    setState("transcribing");
    setError("");
    setAudio(blob);
    const controller = new AbortController();
    abort.current = controller;
    try {
      const wave = await toSpeechWave(blob);
      if (token !== generation.current) return;
      const identity = uuidv4();
      requestId.current = identity;
      const transcript = await transcribeAudio(wave, controller.signal, identity);
      if (token !== generation.current) return;
      setText(transcript);
      if (!transcript.trim()) setError(t("speech.noSpeech"));
    } catch (reason) {
      if (token !== generation.current) return;
      const detail = axios.isAxiosError(reason) ? reason.response?.data?.detail : null;
      setError(
        typeof detail === "string"
          ? `${t("speech.failed")}: ${detail}`
          : t(
              reason instanceof Error && ["audioTooLong", "audioTooLarge"].includes(reason.message)
                ? `speech.${reason.message}`
                : "speech.failed",
            ),
      );
    } finally {
      if (token === generation.current) {
        requestId.current = null;
        setState("idle");
      }
    }
  }
  async function record() {
    setError("");
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError(t("speech.unsupported"));
      return;
    }
    setState("permission");
    const token = generation.current;
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (token !== generation.current) {
        media.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = media;
      const recording = new MediaRecorder(media);
      recorder.current = recording;
      const chunks: Blob[] = [];
      recording.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      recording.onerror = () => {
        cleanup();
        setState("idle");
        setError(t("speech.microphoneFailed"));
      };
      recording.onstop = () => {
        if (timer.current) clearTimeout(timer.current);
        media.getTracks().forEach((track) => track.stop());
        if (token === generation.current)
          void recognize(new Blob(chunks, { type: recording.mimeType }), token);
      };
      recording.start(1000);
      setState("recording");
      timer.current = setTimeout(() => {
        if (recording.state === "recording") recording.stop();
      }, 299000);
    } catch {
      if (token === generation.current) {
        cleanup();
        setState("idle");
        setError(t("speech.microphoneFailed"));
      }
    }
  }
  const ready = settings?.enabled && !disabled;
  const busy = state !== "idle";
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        cleanup();
        setOpen(next);
        setState("idle");
        setError("");
        setText("");
        setAudio(null);
      }}
    >
      <Dialog.Trigger>
        <IconButton
          type="button"
          size="1"
          variant="ghost"
          color="gray"
          disabled={disabled}
          aria-label={t(uploadOnly ? "speech.upload" : "speech.title")}
          title={t(uploadOnly ? "speech.upload" : "speech.title")}
        >
          {uploadOnly ? <FileAudio size={16} /> : <Mic size={16} />}
        </IconButton>
      </Dialog.Trigger>
      <Dialog.Content
        maxWidth="600px"
        aria-describedby="speech-input-description"
      >
        <Dialog.Title>{t("speech.title")}</Dialog.Title>
        <Dialog.Description
          id="speech-input-description"
          size="2"
          mb="4"
        >
          {t("speech.inputHint")}
        </Dialog.Description>
        <Flex
          direction="column"
          gap="3"
        >
          {!settings?.enabled ? (
            <Text
              color="orange"
              role="status"
            >
              {t(
                isError ? "speech.loadFailed" : settings ? "speech.enableFirst" : "common.loading",
              )}
            </Text>
          ) : (
            <Text size="2">{t(`speech.providers.${settings.provider}`)}</Text>
          )}
          <Flex
            gap="3"
            align="center"
            wrap="wrap"
          >
            {!uploadOnly ? (
              <Button
                disabled={!ready || (busy && state !== "recording")}
                onClick={() => (state === "recording" ? recorder.current?.stop() : void record())}
              >
                {t(state === "recording" ? "speech.stop" : "speech.record")}
              </Button>
            ) : null}
            <label>
              <Text size="2">{t("speech.upload")}</Text>
              <input
                aria-label={t("speech.upload")}
                type="file"
                accept="audio/*,.wav,.mp3,.m4a,.ogg,.flac,.webm"
                disabled={!ready || busy}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = "";
                  if (file) void recognize(file);
                }}
              />
            </label>
          </Flex>
          {busy ? (
            <Text
              role="status"
              aria-live="polite"
            >
              {t(`speech.${state}`)}
            </Text>
          ) : null}
          {error ? (
            <Text
              role="alert"
              color="red"
            >
              {error}
            </Text>
          ) : null}
          {audio && error ? (
            <Button
              variant="soft"
              disabled={busy || !ready}
              onClick={() => void recognize(audio)}
            >
              {t("speech.retry")}
            </Button>
          ) : null}
          <TextArea
            aria-label={t("speech.transcript")}
            placeholder={t("speech.transcript")}
            value={text}
            disabled={busy}
            onChange={(event) => setText(event.target.value)}
            rows={6}
          />
          <Flex
            justify="end"
            gap="3"
          >
            <Dialog.Close>
              <Button
                variant="soft"
                color="gray"
              >
                {t("common.cancel")}
              </Button>
            </Dialog.Close>
            <Button
              disabled={!text.trim() || busy || disabled}
              onClick={() => {
                onInsert(text);
                cleanup();
                setOpen(false);
                setState("idle");
                setText("");
                setAudio(null);
              }}
            >
              {t("speech.insert")}
            </Button>
          </Flex>
        </Flex>
      </Dialog.Content>
    </Dialog.Root>
  );
}

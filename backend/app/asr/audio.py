"""Canonical audio validation before any native inference or network request."""

import io
import wave

from fastapi import HTTPException

MAX_SECONDS = 300
MAX_BYTES = 16000 * 2 * MAX_SECONDS + 4096


def validate_audio(audio: bytes) -> float:
    try:
        with wave.open(io.BytesIO(audio), "rb") as source:
            frames = source.getnframes()
            if (
                source.getnchannels() != 1
                or source.getsampwidth() != 2
                or source.getframerate() != 16000
                or source.getcomptype() != "NONE"
            ):
                raise ValueError("Expected mono 16 kHz 16-bit PCM WAV")
            if not 0 < frames <= 16000 * MAX_SECONDS:
                raise ValueError("Recording must be between 0 and 300 seconds")
            if len(source.readframes(frames)) != frames * 2:
                raise ValueError("Truncated WAV audio")
            return frames / 16000
    except (wave.Error, EOFError, ValueError) as exc:
        raise HTTPException(
            400, "Expected a valid mono 16 kHz 16-bit PCM WAV, up to 5 minutes"
        ) from exc

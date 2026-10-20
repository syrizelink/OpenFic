"""One isolated Python inference process per recording, reclaimed on completion.

The parent owns deadlines and cancellation. Native libraries never run in the
web server process. Input and output are memory-only; model files are reusable.
"""

import contextlib
import io
import json
import sys
import wave


def sensevoice(config: dict, audio: bytes) -> str:
    import numpy as np
    import sherpa_onnx

    with wave.open(io.BytesIO(audio), "rb") as source:
        samples = (
            np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").astype(
                np.float32
            )
            / 32768
        )
    recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=config["model_path"],
        tokens=config["tokens_path"],
        num_threads=2,
        use_itn=True,
        language=config["language"],
        provider="cpu",
    )
    vad_config = sherpa_onnx.VadModelConfig()
    vad_config.silero_vad.model = config["vad_path"]
    vad_config.silero_vad.min_silence_duration = 0.4
    vad_config.silero_vad.min_speech_duration = 0.1
    vad_config.silero_vad.max_speech_duration = 25
    vad_config.sample_rate = 16000
    vad_config.num_threads = 2
    detector = sherpa_onnx.VoiceActivityDetector(vad_config, buffer_size_in_seconds=30)
    texts = []
    first = True

    def drain():
        nonlocal first
        while not detector.empty():
            segment = detector.front
            speech = segment.samples
            # Restore the beginning that a cold VAD may detect late.
            if first:
                first = False
                start = max(0, segment.start - 3200)
                speech = np.concatenate((samples[start : segment.start], speech))
            stream = recognizer.create_stream()
            stream.accept_waveform(16000, speech)
            recognizer.decode_stream(stream)
            texts.append(stream.result.text.strip())
            detector.pop()

    for offset in range(0, len(samples), 512):
        detector.accept_waveform(samples[offset : offset + 512])
        drain()
    detector.flush()
    drain()
    return " ".join(text for text in texts if text)


def main():
    config = json.loads(sys.stdin.buffer.readline())
    audio = sys.stdin.buffer.read()
    # Third-party progress messages must not corrupt the output protocol.
    with contextlib.redirect_stdout(sys.stderr):
        text = sensevoice(config, audio)
    print(json.dumps({"text": text}, ensure_ascii=False))


if __name__ == "__main__":
    main()

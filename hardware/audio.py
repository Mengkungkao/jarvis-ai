import asyncio
import wave
from pathlib import Path

import sounddevice as sd
import numpy as np


class AudioController:
    def __init__(self, config: dict, logger) -> None:
        self.config = config
        self.logger = logger
        self.sample_rate = config.get("audio", {}).get("sample_rate", 16000)
        self.channels = config.get("audio", {}).get("channels", 1)
        self.record_seconds = config.get("audio", {}).get("record_seconds", 5)
        self.input_wav = Path(config.get("audio", {}).get("input_wav", "data/input.wav"))
        self.input_wav.parent.mkdir(parents=True, exist_ok=True)

    async def record_audio(self) -> str:
        self.logger.info("Recording audio")
        audio = sd.rec(
            int(self.record_seconds * self.sample_rate),
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            blocking=True,
        )
        self._write_wav(audio, self.input_wav)
        return str(self.input_wav)

    def _write_wav(self, audio, destination: Path) -> None:
        normalized = np.clip(audio, -1.0, 1.0)
        audio_int16 = (normalized * 32767).astype("int16")
        with wave.open(str(destination), "wb") as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

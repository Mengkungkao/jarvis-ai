from pathlib import Path

from vosk import Model, KaldiRecognizer
import wave
import json


class VoskASR:
    def __init__(self, config: dict, logger) -> None:
        self.config = config
        self.logger = logger
        self.model_path = Path(config.get("models", {}).get("vosk_model_path", "models/vosk"))
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        model_dir = self.model_path
        if not model_dir.exists():
            self.logger.warning("Vosk model path not found: %s", model_dir)
            return
        try:
            self.model = Model(str(model_dir))
            self.logger.info("Loaded Vosk model from %s", model_dir)
        except Exception as exc:  # pragma: no cover - runtime guard
            self.logger.exception("Unable to load Vosk model: %s", exc)

    def transcribe(self, audio_path: str) -> str:
        if self.model is None:
            self.logger.warning("Vosk model unavailable; returning placeholder")
            return ""

        wav = wave.open(audio_path, "rb")
        rec = KaldiRecognizer(self.model, 16000)
        result_text = []
        while True:
            data = wav.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                continue
        wav.close()
        result = json.loads(rec.FinalResult())
        text = result.get("text", "").strip()
        self.logger.info("Transcribed text: %s", text)
        return text

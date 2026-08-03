import subprocess
from pathlib import Path


class PiperTTS:
    def __init__(self, config: dict, logger) -> None:
        self.config = config
        self.logger = logger
        self.model_path = config.get("models", {}).get("piper_model_path", "models/piper/en_US-lessac-medium.onnx")
        self.model_config = config.get("models", {}).get("piper_model_config", "models/piper/en_US-lessac-medium.onnx.json")
        self.binary = config.get("models", {}).get("piper_binary", "piper")

    def speak(self, text: str) -> None:
        if not Path(self.model_path).exists():
            self.logger.warning("Piper voice model missing; skipping speech")
            return
        cmd = [self.binary, "--model", self.model_path, "--output_file", "data/output.wav"]
        if self.model_config:
            cmd.extend(["--config", self.model_config])
        self.logger.info("Speaking response via Piper")
        subprocess.run(cmd, input=text.encode("utf-8"), check=False)

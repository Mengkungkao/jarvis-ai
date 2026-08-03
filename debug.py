#!/usr/bin/env python3
import os
import sys
from pathlib import Path

from config import load_config
from utils.logger import get_logger
from hardware.whisplay_display import WhisplayDisplay
from hardware.led import LedController


def main() -> None:
    root = Path(__file__).resolve().parent
    config = load_config(root)
    logger = get_logger(root, name="jarvis-debug")

    print("[debug] Starting JARVIS debug checks")
    display = WhisplayDisplay(config, logger)
    led = LedController(config, logger)

    display.show("DEBUG")
    led.set_status("boot")

    print("[debug] Config loaded")
    print(f"[debug] Anthropic API key configured: {'yes' if os.getenv('ANTHROPIC_API_KEY') else 'no'}")

    model_paths = [
        config.get("models", {}).get("vosk_model_path", "models/vosk"),
        config.get("models", {}).get("piper_model_path", "models/piper/en_US-lessac-medium.onnx"),
    ]
    for path in model_paths:
        resolved = root / path if not Path(path).is_absolute() else Path(path)
        print(f"[debug] {resolved}: {'found' if resolved.exists() else 'missing'}")

    try:
        import sounddevice as sd
        devices = sd.query_devices()
        print("[debug] Audio devices:")
        if isinstance(devices, list):
            for idx, device in enumerate(devices):
                print(f"  {idx}: {device.get('name')}" if isinstance(device, dict) else f"  {idx}: {device}")
        else:
            print(devices)
    except Exception as exc:  # pragma: no cover - runtime fallback
        print(f"[debug] Audio query failed: {exc}")

    display.show("READY")
    led.set_status("idle")
    print("[debug] Debug checks complete")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted")
        sys.exit(0)

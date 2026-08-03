#!/usr/bin/env python3
import asyncio
import os
import sys
from pathlib import Path

from config import load_config
from utils.logger import get_logger
from utils.memory import ConversationMemory
from asr.vosk_engine import VoskASR
from llm.anthropic_client import AnthropicClient
from tts.piper_engine import PiperTTS
from hardware.whisplay_display import WhisplayDisplay
from hardware.audio import AudioController
from hardware.buttons import ButtonController
from hardware.led import LedController


class JarvisAssistant:
    def __init__(self) -> None:
        self.root = Path(__file__).resolve().parent
        self.config = load_config(self.root)
        self.logger = get_logger(self.root, name="jarvis")
        self.memory = ConversationMemory(self.config)
        self.display = WhisplayDisplay(self.config, self.logger)
        self.audio = AudioController(self.config, self.logger)
        self.buttons = ButtonController(self.config, self.logger)
        self.led = LedController(self.config, self.logger)
        self.asr = VoskASR(self.config, self.logger)
        self.llm = AnthropicClient(self.config, self.logger)
        self.tts = PiperTTS(self.config, self.logger)

    async def boot(self) -> None:
        self.logger.info("Starting JARVIS boot sequence")
        self.display.show("JARVIS READY")
        self.led.set_status("boot")
        await asyncio.sleep(0.5)
        self.display.show("Booting...")
        await self.display.boot_animation()
        self.display.show("JARVIS READY")
        self.led.set_status("idle")

    async def run(self) -> None:
        await self.boot()
        self.logger.info("Entering standby loop")
        while True:
            try:
                self.display.show("JARVIS READY")
                self.led.set_status("idle")
                await self.buttons.wait_for_press()
                self.display.show("Listening...")
                self.led.set_status("listening")
                audio_path = await self.audio.record_audio()
                self.display.show("Processing...")
                self.led.set_status("processing")
                transcript = self.asr.transcribe(audio_path)
                if not transcript:
                    self.display.show("Error")
                    self.led.set_status("error")
                    await asyncio.sleep(1)
                    continue

                self.logger.info("User said: %s", transcript)
                prompt = self.memory.build_prompt(transcript)
                response = self.llm.generate(prompt)
                self.memory.append(transcript, response)
                self.display.show("Speaking...")
                self.led.set_status("speaking")
                self.tts.speak(response)
                self.display.show("JARVIS READY")
                self.led.set_status("idle")
            except KeyboardInterrupt:
                self.logger.info("Interrupted by user")
                break
            except Exception as exc:  # pragma: no cover - runtime guard
                self.logger.exception("Runtime error: %s", exc)
                self.display.show("Connection Error")
                self.led.set_status("error")
                await asyncio.sleep(2)


async def main() -> None:
    assistant = JarvisAssistant()
    await assistant.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted")
        sys.exit(0)

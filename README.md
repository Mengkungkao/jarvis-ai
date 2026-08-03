# JARVIS Pocket AI Assistant

JARVIS Pocket AI Assistant is a portable, offline-first voice assistant for Raspberry Pi Zero 2W with the Whisplay HAT. It uses Vosk for local speech recognition, Anthropic Claude for cloud reasoning, and Piper for local speech synthesis. The experience is designed to be compact, low-power, and resilient when WiFi or cloud connectivity is limited.

## 1. Raspberry Pi Zero 2W analysis

The Raspberry Pi Zero 2W is a capable but memory-constrained device. The best choice for this project is Raspberry Pi OS Lite (64-bit) because it provides a small footprint and good compatibility with Pi hardware. The project is optimized for 512MB RAM by using small speech models, a compact LLM prompt, and lightweight audio processing.

### Recommended OS
- Raspberry Pi OS Lite (64-bit)
- Use a 32GB microSD card or larger
- Enable SSH, WiFi, and I2C if required by the Whisplay HAT

### Hardware compatibility notes
- The Whisplay HAT should be tested with the Pi’s I2C and GPIO interfaces before full integration.
- Audio input and output should be tested with ALSA first, then via the HAT.
- The Pi Zero 2W should be run with the CPU governor set to conservative or ondemand for better thermal stability.

### Required libraries
- Python 3.10+
- Vosk for local speech recognition
- Piper for local speech synthesis
- Anthropic Python SDK for cloud reasoning
- SoundDevice for microphone capture
- PyYAML for configuration

## 2. Implementation plan

1. Validate the Whisplay HAT display, microphone, speaker, buttons, and RGB LED.
2. Implement local speech recognition with Vosk and local speech synthesis with Piper.
3. Add cloud reasoning with Anthropic Claude via a configurable API key.
4. Integrate the hardware drivers into a single main loop.
5. Optimize RAM usage, startup time, and battery efficiency.

## 3. Project structure

- main.py - Main application entry point.
- config/config.yaml - Defaults for the assistant.
- config/secrets.env - API key placeholders.
- asr/vosk_engine.py - Local speech-to-text.
- llm/anthropic_client.py - Claude API wrapper.
- tts/piper_engine.py - Local text-to-speech.
- hardware/whisplay_display.py - Display state manager.
- hardware/audio.py - Recording and playback helpers.
- hardware/buttons.py - Button event handling.
- hardware/led.py - RGB LED status.
- utils/logger.py - Logging helper.
- utils/memory.py - Conversation history storage.
- models/vosk/ - Vosk model directory.
- models/piper/ - Piper model files.

## 4. Hardware assembly

1. Attach the Whisplay HAT to the Pi Zero 2W.
2. Connect the microphone and speaker through the HAT.
3. Optionally attach the PiSugar 2 battery.
4. Power the Pi and verify that the display boots.

### Wiring diagram

- 5V power -> Pi 5V and HAT power rail
- GND -> Shared ground
- I2C pins -> Whisplay HAT display interface
- GPIO 17 -> Button input (default)
- GPIO 27 -> RGB LED output (default)

## 5. Software installation

Run the installer:

```bash
chmod +x install.sh
./install.sh
```

The installer will:
- update the system packages
- create a Python virtual environment
- install Python dependencies
- download the Vosk English model
- download a Piper voice model
- create a systemd service

## 6. API configuration

Set your Anthropic API key in config/secrets.env:

```bash
cp config/secrets.env config/secrets.env.local
# edit config/secrets.env.local
```

The application loads the environment file automatically from the config directory when present.

## 7. Voice model replacement

To replace the Piper voice model:
- place the new ONNX model and JSON config under models/piper/
- update models.piper_model_path and models.piper_model_config in config/config.yaml

To replace the Vosk model:
- download a different model into models/vosk/
- update models.vosk_model_path in config/config.yaml

## 8. Troubleshooting

- If the display does not light up, verify the HAT is seated correctly and the Pi is powered with enough current.
- If audio is distorted, reduce the input gain or use an external USB microphone.
- If Claude requests fail, verify the API key and internet connectivity.
- If Vosk fails to initialize, ensure the model folder contains the expected files.

## 9. Performance optimization

- Run the service with the Python virtual environment to avoid dependency issues.
- Keep the conversation history short to reduce memory use.
- Disable wake-word detection unless it is required.
- Use a smaller Vosk model when running on a Pi Zero 2W.
# jarvis-ai

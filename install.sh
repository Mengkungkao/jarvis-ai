#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

SERVICE_DIR="$ROOT_DIR"

echo "[jarvis] Updating system packages"
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv python3-dev git curl wget alsa-utils sox libasound2-dev portaudio19-dev

if ! command -v python3 >/dev/null 2>&1; then
  echo "[jarvis] Python 3 is required" >&2
  exit 1
fi

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p models/vosk models/piper data logs

if [ ! -d "models/vosk/vosk-model-small-en-us-0.15" ]; then
  echo "[jarvis] Downloading Vosk model"
  wget -O /tmp/vosk-model-small-en-us-0.15.zip https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
  unzip -o /tmp/vosk-model-small-en-us-0.15.zip -d models/vosk/
fi

if [ ! -f "models/piper/en_US-lessac-medium.onnx" ]; then
  echo "[jarvis] Downloading Piper voice model"
  mkdir -p models/piper
  wget -O models/piper/en_US-lessac-medium.onnx https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
  wget -O models/piper/en_US-lessac-medium.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
fi

if ! command -v piper >/dev/null 2>&1; then
  echo "[jarvis] Piper binary not found. Install it manually if needed, or place a binary on PATH."
fi

cat > /tmp/jarvis-ai.service <<EOF
[Unit]
Description=JARVIS Pocket AI Assistant
After=network.target sound.target

[Service]
Type=simple
WorkingDirectory=$SERVICE_DIR
ExecStart=$SERVICE_DIR/.venv/bin/python $SERVICE_DIR/main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=JARVIS_HEADLESS=1
Environment=WHISPLAY_DAEMON_URL=http://127.0.0.1:8080

[Install]
WantedBy=multi-user.target
EOF

sudo install -m 0644 /tmp/jarvis-ai.service /etc/systemd/system/jarvis-ai.service
sudo systemctl daemon-reload
sudo systemctl enable jarvis-ai.service

if command -v amixer >/dev/null 2>&1; then
  echo "[jarvis] Configuring ALSA defaults"
  amixer sset Master unmute || true
  amixer sset PCM unmute || true
fi

echo "[jarvis] Installation complete."
echo "[jarvis] Next steps:"
echo "  1. Edit config/secrets.env"
echo "  2. Reboot or run: systemctl start jarvis-ai"
echo "  3. Connect the Whisplay HAT and test the hardware"

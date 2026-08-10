#!/usr/bin/env bash
# JARVIS setup for Raspberry Pi (Zero 2W and up).
# Installs audio/speech packages and, on request, a systemd service.
set -e

cd "$(dirname "$0")"

echo "== JARVIS Pi setup =="

echo "-- apt packages (alsa-utils for record/playback, espeak-ng for TTS)"
sudo apt-get update
sudo apt-get install -y alsa-utils espeak-ng python3-pip

if [ ! -f .env ]; then
  cp .env.example .env
  echo "-- created .env from .env.example (edit it to configure JARVIS)"
fi

echo
echo "-- offline speech recognition (vosk + small English model, ~40MB)"
read -r -p "   Install vosk ASR now? [Y/n] " answer
if [ "$answer" != "n" ] && [ "$answer" != "N" ]; then
  pip3 install vosk --break-system-packages
  MODEL_DIR="$HOME/vosk-model-small-en-us-0.15"
  if [ ! -d "$MODEL_DIR" ]; then
    echo "   downloading English model to $MODEL_DIR ..."
    curl -L -o /tmp/vosk-model.zip \
      https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
    python3 -c "import zipfile; zipfile.ZipFile('/tmp/vosk-model.zip').extractall('$HOME')"
    rm -f /tmp/vosk-model.zip
  fi
  if grep -q "^VOSK_MODEL_PATH=" .env 2>/dev/null; then
    sed -i "s|^VOSK_MODEL_PATH=.*|VOSK_MODEL_PATH=$MODEL_DIR|" .env
  else
    printf "\nVOSK_MODEL_PATH=%s\n" "$MODEL_DIR" >> .env
  fi
  echo "   VOSK_MODEL_PATH set in .env"
  echo "   verify the whole pipeline with: python3 run_jarvis.py mic-test"
fi

echo
if [ -S /tmp/whisplay-daemon.sock ]; then
  read -r -p "-- register JARVIS on the whisplay daemon desktop? [y/N] " answer
  if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
    python3 run_jarvis.py register-app
    echo "   (skip the systemd service below — the daemon launches JARVIS)"
  fi
else
  echo "-- whisplay-daemon not running: skipping desktop registration."
  echo "   After starting the daemon, run: python3 run_jarvis.py register-app"
fi

echo
read -r -p "-- install jarvis-voice systemd service (starts on boot)? [y/N] " answer
if [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
  SERVICE_FILE=/etc/systemd/system/jarvis-voice.service
  sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=JARVIS offline voice assistant
After=sound.target network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/python3 $(pwd)/run_jarvis.py voice
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl daemon-reload
  sudo systemctl enable jarvis-voice.service
  echo "   Installed. Start now with: sudo systemctl start jarvis-voice"
fi

echo
echo "== done. Train with: ./jarvis-cli train   then: ./jarvis-cli chat =="

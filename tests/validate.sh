#!/usr/bin/env bash
# JARVIS-AI validation suite. Run from anywhere: bash tests/validate.sh
#
# Works on the dev box and on the Pi. Checks that need a service that is
# not available (Ollama, vosk model, network) are reported as SKIP, not
# FAIL. Exit code is 1 if anything FAILed.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
CACHE="$HOME/.cache/jarvis-tests"
TMP="$(mktemp -d /tmp/jarvis-validate-XXXX)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$CACHE"
PASS=0; FAIL=0; SKIP=0
ok()   { PASS=$((PASS+1)); echo "PASS: $1"; }
bad()  { FAIL=$((FAIL+1)); echo "FAIL: $1"; }
skip() { SKIP=$((SKIP+1)); echo "SKIP: $1"; }
check(){ if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }

OLLAMA_UP=false
curl -s -m 3 "$(grep -s '^OLLAMA_ENDPOINT=' .env | cut -d= -f2 | sed 's|/$||' || true)/api/version" >/dev/null 2>&1 && OLLAMA_UP=true
curl -s -m 3 localhost:11434/api/version >/dev/null 2>&1 && OLLAMA_UP=true

echo "===== 1. code health ====="
check "all modules compile" "python3 -m py_compile jarvis/*.py"
check "CLI --help" "python3 run_jarvis.py --help"

echo "===== 2. training pipeline ====="
printf '# Temp test doc\nThe secret validation code is zebra-blue-42.\n' > knowledge/_validation_tmp.md
OUT=$(python3 run_jarvis.py train 2>&1)
echo "$OUT" | grep -q "_validation_tmp.md: chunk" && ok "new file indexed" || bad "new file indexed"
OUT=$(python3 run_jarvis.py train 2>&1)
echo "$OUT" | grep -q "unchanged: _validation_tmp.md" && ok "incremental skip unchanged" || bad "incremental skip unchanged"
echo "extra line" >> knowledge/_validation_tmp.md
OUT=$(python3 run_jarvis.py train 2>&1)
echo "$OUT" | grep -q "_validation_tmp.md: chunk" && ok "re-index changed file" || bad "re-index changed file"
ANS=$(python3 run_jarvis.py --backend extractive ask "what is the secret validation code" 2>&1)
echo "$ANS" | grep -q "zebra-blue-42" && ok "extractive retrieval finds new fact" || bad "extractive retrieval finds new fact"
rm knowledge/_validation_tmp.md
OUT=$(python3 run_jarvis.py train 2>&1)
echo "$OUT" | grep -q "removed knowledge for deleted file" && ok "deleted file cleanup" || bad "deleted file cleanup"

echo "===== 3. brains ====="
ANS=$(python3 run_jarvis.py --backend test ask "hello" 2>&1)
echo "$ANS" | grep -q "\[test\] You said: hello" && ok "test brain" || bad "test brain"
ANS=$(OLLAMA_ENDPOINT=http://127.0.0.1:9 timeout 60 python3 run_jarvis.py --backend auto ask "what battery does my device use" 2>&1)
echo "$ANS" | grep -q "brain: extractive" && ok "auto falls back to extractive when ollama down" || bad "auto fallback"
if $OLLAMA_UP; then
  ANS=$(python3 run_jarvis.py --backend ollama ask "what battery does my device use" 2>&1)
  echo "$ANS" | grep -qi "1200mAh" && ok "ollama RAG answer (battery fact)" || bad "ollama RAG answer (battery fact)"
else
  skip "ollama RAG answer (server not running)"
fi

echo "===== 4. tools / skills / memory ====="
python3 run_jarvis.py skills 2>&1 | grep -q "morning-briefing" && ok "skills discovery" || bad "skills discovery"
if $OLLAMA_UP; then
  MEM_BAK="$ROOT/data/memory.json"; [ -f "$MEM_BAK" ] && cp "$MEM_BAK" "$TMP/memory.bak"
  python3 run_jarvis.py memory --clear >/dev/null 2>&1
  python3 run_jarvis.py --backend ollama ask "please remember that my validation color is purple" >/dev/null 2>&1
  python3 run_jarvis.py memory 2>&1 | grep -qi "purple" && ok "remember tool persists fact" || bad "remember tool persists fact"
  ANS=$(python3 run_jarvis.py --backend ollama ask "read the morning-briefing skill and follow it" 2>&1)
  echo "$ANS" | grep -q "read_skill" && ok "read_skill tool invoked" || bad "read_skill tool invoked"
  python3 run_jarvis.py memory --clear >/dev/null 2>&1
  [ -f "$TMP/memory.bak" ] && cp "$TMP/memory.bak" "$MEM_BAK"
else
  skip "remember/read_skill tools (need ollama)"
fi

echo "===== 5. speech pipeline ====="
python3 - "$TMP" <<'EOF'
import math, struct, sys, wave
tmp = sys.argv[1]
with wave.open(tmp + "/silent.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(b"\x00\x00" * 16000)
with wave.open(tmp + "/tone.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(b"".join(struct.pack("<h", int(12000 * math.sin(i * 0.1))) for i in range(16000)))
EOF
OUT=$(ASR_BACKEND=none python3 run_jarvis.py mic-test --file "$TMP/silent.wav" 2>&1)
echo "$OUT" | grep -q "completely silent" && ok "silent-mic detection" || bad "silent-mic detection"
OUT=$(ASR_BACKEND=none python3 run_jarvis.py mic-test --file "$TMP/tone.wav" 2>&1)
echo "$OUT" | grep -q "level looks OK" && ok "level meter" || bad "level meter"
VOSK_MODEL="${VOSK_MODEL_PATH:-$CACHE/vosk-model-small-en-us-0.15}"
if python3 -c "import vosk" 2>/dev/null && [ -d "$VOSK_MODEL" ] && [ -f "$CACHE/test-speech.wav" ]; then
  OUT=$(VOSK_MODEL_PATH="$VOSK_MODEL" python3 run_jarvis.py mic-test --file "$CACHE/test-speech.wav" 2>&1)
  echo "$OUT" | grep -q "recognized: 'one zero zero zero one" && ok "vosk English recognition" || bad "vosk English recognition"
else
  skip "vosk English recognition (vosk/model/sample not present)"
fi

echo "===== 6. emotions ====="
if python3 -c "import PIL" 2>/dev/null; then
  python3 - <<EOF && ok "emotion frames + reactions + strip_emoji" || bad "emotions"
import sys; sys.path.insert(0, "$ROOT")
from jarvis import emotions
assert len(emotions.gif_bytes("listening")) > 1000
frames = emotions.compose_screen_frames("happy", "test")
assert len(frames) >= 4 and len(frames[0][0]) == 240*280*2
assert emotions.emotion_for_reply("yay \U0001F389") == "happy"
assert emotions.emotion_for_reply("so sorry") == "sad"
assert emotions.strip_emoji("hi \U0001F600") == "hi"
EOF
else
  skip "emotions (PIL not installed)"
fi

echo "===== 7. debug console ====="
JARVIS_DEBUG_PORT=17872 python3 run_jarvis.py --backend extractive debug >/dev/null 2>&1 &
DBG=$!; sleep 2
check "debug page serves" "curl -sf localhost:17872/ -o /dev/null"
check "state endpoint" "curl -sf localhost:17872/api/state | grep -q extractive"
check "rag inspector endpoint" "curl -sf 'localhost:17872/api/rag?q=battery' | grep -q score"
if python3 -c "import PIL" 2>/dev/null; then
  check "emotion gif endpoint" "curl -sf 'localhost:17872/emotion.gif?name=idle' -o /dev/null"
fi
curl -sf -X POST localhost:17872/api/ask -d '{"text":"what battery does my device use"}' >/dev/null; sleep 3
check "async ask via console" "curl -sf localhost:17872/api/state | grep -qi 1200mAh"
check "trace endpoint records pipeline" "curl -sf 'localhost:17872/api/trace?since=0' | grep -q '\"rag\"'"
kill $DBG 2>/dev/null

echo "===== 8. whisplay daemon app (mock) ====="
python3 tests/mock_daemon.py "$TMP/mock.sock" "$TMP/mock-fb.bin" > "$TMP/mock.log" 2>&1 &
MOCK=$!; sleep 0.5
WHISPLAY_DAEMON_SOCKET="$TMP/mock.sock" python3 run_jarvis.py register-app >/dev/null 2>&1
grep -q '"app_id": "jarvis-ai"' "$TMP/mock.log" && ok "register-app payload" || bad "register-app payload"
mkdir -p "$TMP/bin"; printf '#!/bin/sh\nexit 1\n' > "$TMP/bin/arecord"; chmod +x "$TMP/bin/arecord"
(WHISPLAY_DAEMON_SOCKET="$TMP/mock.sock" PATH="$TMP/bin:$PATH" ASR_BACKEND=none TTS_BACKEND=none \
  timeout 9 python3 run_jarvis.py --backend extractive voice </dev/null >"$TMP/voice.log" 2>&1)
grep -q "whisplay: daemon" "$TMP/voice.log" && ok "daemon mode detected" || bad "daemon mode detected"
grep -q "app.focus.acquire" "$TMP/mock.log" && ok "focus acquired" || bad "focus acquired"
grep -q "app.focus.release" "$TMP/mock.log" && ok "focus released on exit gesture" || bad "focus released"
python3 -c "
d = open('$TMP/mock-fb.bin', 'rb').read()
assert len(d) == 134400 and any(d), 'framebuffer empty'
" 2>/dev/null && ok "status/animation drew to framebuffer" || bad "status/animation drew to framebuffer"
kill $MOCK 2>/dev/null

echo
echo "===== RESULT: $PASS passed, $FAIL failed, $SKIP skipped ====="
[ "$FAIL" -eq 0 ]

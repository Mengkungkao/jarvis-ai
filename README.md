# JARVIS — your own offline, trainable AI assistant

A fully offline personal assistant you can **train on your own documents**
and **teach task procedures**, built by studying and distilling the
architecture of [PiSugar/Whisplay](Whisplay/) (hardware driver) and
[PiSugar/whisplay-ai-chatbot](whisplay-ai-chatbot/) (voice chatbot).

Pure Python standard library — no npm, no build step, no cloud, no API
keys. It runs on anything from a **Raspberry Pi Zero 2W** (retrieval-only
mode, no LLM needed) up to a desktop or Pi 5 running a local LLM through
[Ollama](https://ollama.com).

```
you ──> ask/chat/voice ──> ChatSession ────────────────┐
                             │                          │
                   RAG: embed question,          Ollama LLM (local/LAN)
                   search local vector store     + tools:
                   inject relevant chunks          search_knowledge
                             │                     read_skill
     knowledge/*.md ──train──> data/knowledge.json  remember
     skills/*/SKILL.md ──────> system prompt        get_current_time
     data/memory.json ───────> system prompt
```

## What "training" means here

Two complementary mechanisms (the same split whisplay-ai-chatbot uses):

1. **Knowledge (facts)** — drop `.txt`/`.md` files into `knowledge/`, run
   `./jarvis-cli train`. Files are chunked (sentence-aware, with overlap),
   embedded, and stored in a local vector store. At question time the best
   matching chunks are retrieved and injected — with a relevance threshold
   so unrelated questions aren't polluted. Training is **incremental**:
   only new/changed files are re-indexed, deleted files are cleaned up.
2. **Skills (procedures)** — create `skills/<name>/SKILL.md` describing
   *how to do a task*. The skill list is injected into the system prompt;
   the LLM loads the full instructions with the `read_skill` tool when the
   task comes up. See [skills/README.md](skills/README.md).

Plus **memory**: say "remember that ..." in chat and JARVIS stores the fact
in `data/memory.json` and knows it in every future conversation.

## Quick start (desktop / Pi 5)

```bash
# 1. Install Ollama (https://ollama.com) and pull two small models
ollama pull qwen2.5:1.5b        # chat model with tool support (~1GB)
ollama pull nomic-embed-text    # embedding model (~270MB)

# 2. Configure (optional — defaults just work)
cp .env.example .env

# 3. Train on the example knowledge, then talk
./jarvis-cli train
./jarvis-cli chat
./jarvis-cli ask "how do I see the whisplay daemon logs"
```

For noticeably better tool use and answers, use `JARVIS_CHAT_MODEL=qwen2.5:3b`
or `llama3.2:3b` (needs ~4GB RAM; a Pi 5 8GB handles them).

## Running on a Pi Zero 2W

512MB RAM cannot fit an LLM, so pick one of two fully-offline setups:

**A. Standalone (no LLM at all)** — extractive mode: JARVIS answers
questions by returning the most relevant trained knowledge directly.
Instant on the Zero 2W, zero downloads.

```bash
# in .env
JARVIS_BACKEND=extractive
JARVIS_EMBED_BACKEND=local     # dependency-free hashed embeddings
```

**B. LAN brain** — the Zero 2W handles mic/speaker/screen, a Pi 5 or any
PC on your network runs `ollama serve`. Still no internet involved.

```bash
# in .env on the Pi
JARVIS_BACKEND=ollama
OLLAMA_ENDPOINT=http://192.168.1.50:11434   # your LAN machine
# on the LAN machine: OLLAMA_HOST=0.0.0.0 ollama serve
```

Important: train with the same embedding backend the device will use at
question time. For standalone mode run `JARVIS_EMBED_BACKEND=local
./jarvis-cli train --rebuild` (the local embedder needs no server); with a
LAN brain, ollama embeddings give better semantic matching.

Deploy = copy this folder to the Pi (only `jarvis/`, `knowledge/`,
`skills/`, `run_jarvis.py`, `jarvis-cli`, `.env` matter), then run
`bash setup_pi.sh` for audio packages, optional vosk ASR, and an optional
systemd service that starts voice mode on boot.

## Running as a whisplay-daemon app (recommended on the device)

If the `whisplay-daemon` service manages your HAT, add JARVIS to its
desktop launcher instead of running it standalone:

```bash
./jarvis-cli register-app        # once; persists in ~/.whisplay-daemon/app/
./jarvis-cli register-app --remove   # to take it off the desktop again
```

JARVIS then appears as **JV / JARVIS** on the daemon desktop: single click
cycles apps, **long press launches JARVIS**, and while it is foregrounded
the button is push-to-talk. **Four rapid clicks exit** back to the desktop
(the daemon's standard exit gesture). Voice mode auto-detects the daemon:
it registers, acquires focus and the shared framebuffer, draws status
screens (LISTENING / THINKING / ANSWERING plus the recognized text and
answer) directly in RGB565, and drives the LED through the daemon —
falling back to direct hardware access only when no daemon is running.
Logs go to `~/.whisplay-daemon/daemon-app.log`.

## Voice mode (Whisplay HAT)

```bash
./jarvis-cli voice
```

Push-to-talk: hold the Whisplay button (green LED = listening, yellow =
thinking, blue = answering — same colors as whisplay-ai-chatbot), or press
Enter in a terminal without the HAT. The pieces auto-detect and degrade
gracefully:

- **ASR**: `vosk-transcriber` if installed (`pip3 install vosk`, small
  model ~40MB — works on the Zero 2W), or a `whisper-http` server
  (whisplay-ai-chatbot's `python/speech-service/whisper-host.py` protocol),
  or typed input as fallback.
- **TTS**: `piper` (natural voice, Pi 3/5-class) or `espeak-ng` (robotic
  but instant on the Zero 2W), or silent.
- **Whisplay HAT**: auto-detected — looks for the driver in
  `~/Whisplay/runtime` first (the standard install location on the
  device), then next to this project; override with `WHISPLAY_DRIVER_DIR`
  in `.env`. The driver must be installed first
  (`sudo bash ~/Whisplay/install_driver.sh` + reboot).

## Speech recognition not working?

Voice mode needs an ASR engine — without one it says `asr: typed input`
at startup and cannot understand speech at all. On the Pi:

```bash
bash setup_pi.sh          # installs vosk + downloads the English model
                          # and sets VOSK_MODEL_PATH in .env automatically
./jarvis-cli mic-test     # then verify the whole pipeline
```

`mic-test` checks each stage separately: records 4 seconds, reports the
**peak input level** (0 = wrong ALSA device, very low = raise capture
volume in `alsamixer`), plays the recording back, then runs recognition
with timing and prints exactly what was understood. You can also re-test
a saved recording with `./jarvis-cli mic-test --file some.wav`. JARVIS
keeps the vosk model loaded in memory, so recognition is slow only on
the first utterance after start. Alternative to vosk: run a whisper HTTP
server on a LAN machine and set `WHISPER_HTTP_URL` in `.env`. During
`jarvis voice`, every interaction now prints the recorded duration, peak
level, ASR latency, and recognized text — and `--debug` adds the full
pipeline trace.

## Developing JARVIS: the debug console

```bash
./jarvis-cli debug          # then open http://127.0.0.1:17870
```

A zero-dependency web dashboard for tuning your training data and skills:
a **chat tester** with live streamed answers, a **pipeline trace** showing
every RAG query with per-chunk scores against the threshold, LLM rounds,
tool calls with arguments/results and timings, a **RAG inspector** to try
any query against the knowledge base, a **retrain button**, and live
previews of all **emotion animations** exactly as the LCD shows them. Set
`JARVIS_DEBUG_HOST=0.0.0.0` in `.env` to open the console for a Pi from
your laptop. For terminal-only debugging, every command accepts `--debug`
to print the same trace events inline:

```bash
./jarvis-cli --debug ask "what battery does my device use"
```

## Emotion faces

During voice interaction the LCD shows an animated face per state:
blinking **idle**, wide-eyed **listening** with sound waves, **thinking**
dots, a talking **answering** mouth — and after each reply, a reaction
face (**happy / sad / surprised / love / angry**) picked from emoji or
sentiment words in the answer. Emoji are stripped before TTS so they are
never read aloud. All faces are drawn procedurally (no assets); replace
any of them with your own GIF at `emotions/<state>.gif` — see
[emotions/README.md](emotions/README.md).

## Commands

| Command | What it does |
|---|---|
| `./jarvis-cli chat` | interactive conversation (`/reset`, `/status`, `/exit`) |
| `./jarvis-cli ask "…"` | one-shot question |
| `./jarvis-cli train` | index `knowledge/` (add `--rebuild` to start fresh) |
| `./jarvis-cli status` | backend, models, knowledge/skills/memory overview |
| `./jarvis-cli skills` | list taught skills |
| `./jarvis-cli memory` | list facts (`--forget N`, `--clear`) |
| `./jarvis-cli voice` | push-to-talk voice loop |
| `./jarvis-cli register-app` | add JARVIS to the whisplay daemon desktop (`--remove` to undo) |
| `./jarvis-cli debug` | web debug console (chat tester, trace, RAG inspector) |
| `./jarvis-cli emotions` | list emotion animations (`--export` writes them as GIFs) |
| `./jarvis-cli mic-test` | diagnose recording + speech recognition step by step |
| `--debug` | print pipeline trace events with any command |
| `--backend X` | force `ollama` / `extractive` / `test` for one run |

## Configuration

Everything lives in `.env` (see [.env.example](.env.example) — every key is
documented there). The important ones:

- `JARVIS_BACKEND` — `auto` (default: Ollama if reachable, else extractive)
- `OLLAMA_ENDPOINT` / `JARVIS_CHAT_MODEL`
- `JARVIS_EMBED_BACKEND` — `auto` | `ollama` | `local`
- `RAG_SCORE_THRESHOLD` — unset = adaptive (0.55 semantic / 0.18 local)
- `CHAT_HISTORY_RESET_SEC` — fresh conversation after idle (default 300)
- `SYSTEM_PROMPT` — persona override

## Validating the project

```bash
bash tests/validate.sh
```

Runs the full self-check (28 checks): training pipeline (index /
incremental / re-index / cleanup), retrieval, all three brains with
auto-fallback, LLM tools, speech pipeline (level meter + real vosk
English recognition against a reference recording), emotions, every
debug-console endpoint, and the whisplay daemon-app lifecycle against a
mock daemon ([tests/mock_daemon.py](tests/mock_daemon.py)). Checks whose
prerequisites are missing on the machine (Ollama server, vosk model, PIL)
are reported as SKIP, so the same script works on the dev box and on the
Pi. Reference assets are cached in `~/.cache/jarvis-tests/`.

## Project layout

```
jarvis/            the Python package (≈1200 lines, stdlib only)
  config.py        .env loading + settings
  llm.py           Ollama streaming chat + test brain
  embeddings.py    ollama (nomic) or local hashed-BoW embeddings
  chunker.py       sentence-aware chunking with overlap
  vectorstore.py   tiny local vector DB (JSON + base64 float32, cosine)
  knowledge.py     incremental training + threshold retrieval
  skills.py        SKILL.md discovery
  memory.py        durable facts
  tools.py         LLM tool definitions
  chat.py          conversation engine + tool loop + extractive brain
  voice.py         push-to-talk front-end (Whisplay HAT / terminal)
  cli.py           command-line interface
knowledge/         your training documents (+ example)
skills/            your taught procedures (+ example)
data/              generated: vector store, memory (gitignored)
```

## What was learned/ported from the reference projects

- **whisplay-ai-chatbot** — pluggable ASR/LLM/TTS backend pattern; RAG
  pipeline (chunk → embed → Qdrant → score threshold → prompt injection,
  from `src/core/Knowledge.ts`); sentence-aware chunking
  (`src/utils/knowledge.ts`); Ollama tool-calling loop with max-rounds cap,
  duplicate-call blocking, and forced final answer (`ollama-llm.ts`);
  skills-as-SKILL.md-folders (hardness tools); local memory; idle-based
  history reset; speech-friendly system prompt.
- **Whisplay** — `WhisplayBoard` runtime API (button, RGB LED) used by
  voice mode, and the daemon/app conventions described in its README.

This project reimplements those ideas in dependency-free Python. Like the
reference projects, it is licensed under **GPL-3.0**.

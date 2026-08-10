"""Configuration: .env file + environment variables (env vars win).

Mirrors the whisplay-ai-chatbot approach of a single .env at the project
root, but with no external dependency (no python-dotenv).
"""

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_env_loaded = False


def _load_env_file(path):
    """Minimal .env parser: KEY=VALUE lines, # comments, optional quotes."""
    values = {}
    if not os.path.isfile(path):
        return values
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if key:
                values[key] = value
    return values


def load_env():
    """Load .env once; real environment variables take precedence."""
    global _env_loaded
    if _env_loaded:
        return
    for key, value in _load_env_file(os.path.join(PROJECT_ROOT, ".env")).items():
        os.environ.setdefault(key, value)
    _env_loaded = True


def get(key, default=""):
    load_env()
    return os.environ.get(key, default)


def get_bool(key, default=False):
    raw = get(key, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def get_int(key, default):
    try:
        return int(get(key, str(default)))
    except ValueError:
        return default


def get_float(key, default):
    try:
        return float(get(key, str(default)))
    except ValueError:
        return default


# ── Paths ────────────────────────────────────────────────────────────
def data_dir():
    path = get("JARVIS_DATA_DIR", os.path.join(PROJECT_ROOT, "data"))
    os.makedirs(path, exist_ok=True)
    return path


def knowledge_dir():
    path = get("JARVIS_KNOWLEDGE_DIR", os.path.join(PROJECT_ROOT, "knowledge"))
    os.makedirs(path, exist_ok=True)
    return path


def skills_dir():
    path = get("JARVIS_SKILLS_DIR", os.path.join(PROJECT_ROOT, "skills"))
    os.makedirs(path, exist_ok=True)
    return path


# ── Brain / LLM ──────────────────────────────────────────────────────
def backend():
    """auto | ollama | extractive | test"""
    return get("JARVIS_BACKEND", "auto").strip().lower()


def ollama_endpoint():
    return get("OLLAMA_ENDPOINT", "http://localhost:11434").rstrip("/")


def chat_model():
    return get("JARVIS_CHAT_MODEL", "qwen2.5:1.5b")


def enable_thinking():
    return get_bool("ENABLE_THINKING", False)


def enable_tools():
    return get_bool("ENABLE_TOOLS", True)


def max_tool_rounds():
    return get_int("MAX_TOOL_ROUNDS", 4)


def chat_history_reset_sec():
    return get_int("CHAT_HISTORY_RESET_SEC", 300)


def system_prompt():
    base = get(
        "SYSTEM_PROMPT",
        "You are JARVIS, a helpful offline personal assistant. "
        "Answer clearly and concisely.",
    )
    # Speech-friendly instruction, same idea as whisplay-ai-chatbot's default.
    speech = (
        " Reply in plain sentences without Markdown formatting, code fences, "
        "or bullet symbols, so the answer also works when spoken aloud."
    )
    return base + speech


# ── Embeddings / RAG ─────────────────────────────────────────────────
def embed_backend():
    """auto | ollama | local"""
    return get("JARVIS_EMBED_BACKEND", "auto").strip().lower()


def embed_model():
    return get("JARVIS_EMBED_MODEL", "nomic-embed-text")


def rag_enabled():
    return get_bool("RAG_ENABLED", True)


def rag_top_k():
    return get_int("RAG_TOP_K", 3)


def rag_score_threshold(embed_signature=""):
    """Explicit RAG_SCORE_THRESHOLD wins; otherwise the default depends on
    the embedding backend — semantic (ollama) scores run much higher than
    the local hashed bag-of-words scores."""
    raw = get("RAG_SCORE_THRESHOLD", "").strip()
    if raw:
        try:
            return float(raw)
        except ValueError:
            pass
    return 0.18 if embed_signature.startswith("local:") else 0.55


def chunk_size():
    return get_int("RAG_CHUNK_SIZE", 500)


def chunk_overlap():
    return get_int("RAG_CHUNK_OVERLAP", 80)


# ── Memory ───────────────────────────────────────────────────────────
def face_style():
    """emo (big glowing eyes, EMO-robot style) | classic (round smiley)"""
    return get("JARVIS_FACE_STYLE", "emo").strip().lower()


def memory_enabled():
    return get_bool("MEMORY_ENABLED", True)


def memory_max_inject():
    return get_int("MEMORY_MAX_INJECT", 10)


# ── Voice (optional, Raspberry Pi + Whisplay HAT) ────────────────────
def asr_backend():
    """auto | vosk | whisper-http | none"""
    return get("ASR_BACKEND", "auto").strip().lower()


def vosk_model_path():
    return get("VOSK_MODEL_PATH", "")


def whisper_http_url():
    host = get("WHISPER_HOST", "localhost")
    port = get("WHISPER_PORT", "8804")
    return get("WHISPER_HTTP_URL", "http://%s:%s" % (host, port))


def tts_backend():
    """auto | espeak-ng | piper | none"""
    return get("TTS_BACKEND", "auto").strip().lower()


def piper_binary():
    return get("PIPER_BINARY_PATH", "piper")


def piper_model():
    return get("PIPER_MODEL_PATH", "")


def alsa_input_device():
    return get("ALSA_INPUT_DEVICE", "")


def alsa_output_device():
    return get("ALSA_OUTPUT_DEVICE", "")


def record_max_sec():
    return get_int("RECORD_MAX_SEC", 30)

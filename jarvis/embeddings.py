"""Text embeddings with two offline backends.

- "ollama": real semantic embeddings via the Ollama /api/embed endpoint
  (default model: nomic-embed-text), same as whisplay-ai-chatbot's
  ollama-embedding.ts.
- "local":  dependency-free hashed bag-of-words vectors (hashing trick,
  signed buckets, L2-normalized). No model download, runs instantly on
  a Pi Zero 2W. Retrieval quality is keyword-level rather than semantic,
  which is usually fine for a task-specific knowledge base.

The vector store records which backend/model built it, and queries always
embed with the store's recorded backend, so a knowledge base stays
consistent regardless of the chat backend in use.
"""

import json
import math
import re
import urllib.request
import zlib

from . import config

LOCAL_DIM = 512

_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_CJK_RE = re.compile(r"[㐀-鿿豈-﫿]")


# Common function words carry no retrieval signal in a bag-of-words vector
# and badly dilute short queries ("how do i see the logs" -> "logs").
_STOPWORDS = frozenset(
    """a an and are as at be but by can could did do does for from had has
    have he her his how i if in is it its just me my no not of on or our
    she should so some than that the their them then there these they this
    to us was we were what when where which who why will with would you
    your""".split()
)


def _tokenize(text):
    text = text.lower()
    tokens = [t for t in _WORD_RE.findall(text) if t not in _STOPWORDS]
    cjk = _CJK_RE.findall(text)
    tokens.extend(cjk)
    # CJK bigrams capture word-level meaning in Chinese/Japanese text.
    tokens.extend(a + b for a, b in zip(cjk, cjk[1:]))
    return tokens


def embed_local(text):
    vec = [0.0] * LOCAL_DIM
    counts = {}
    for token in _tokenize(text):
        counts[token] = counts.get(token, 0) + 1
    for token, count in counts.items():
        raw = token.encode("utf-8")
        bucket = zlib.crc32(b"b:" + raw) % LOCAL_DIM
        sign = 1.0 if zlib.crc32(b"s:" + raw) & 1 else -1.0
        vec[bucket] += sign * math.sqrt(count)
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def _task_prefix(model, purpose):
    """nomic-embed models are trained with task prefixes; using them
    noticeably widens the gap between relevant and irrelevant scores."""
    if "nomic-embed" in model:
        return "search_query: " if purpose == "query" else "search_document: "
    return ""


def embed_ollama(text, model=None, endpoint=None, timeout=120, purpose="document"):
    endpoint = (endpoint or config.ollama_endpoint()).rstrip("/")
    model = model or config.embed_model()
    text = _task_prefix(model, purpose) + text
    payload = json.dumps({"model": model, "input": text}).encode("utf-8")
    req = urllib.request.Request(
        endpoint + "/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    embeddings = data.get("embeddings") or []
    if not embeddings:
        raise RuntimeError("Ollama returned no embedding for model %s" % model)
    return embeddings[0]


def ollama_embed_available():
    """True if the Ollama endpoint is reachable and can embed."""
    try:
        vec = embed_ollama("ping", timeout=10)
        return bool(vec)
    except Exception:
        return False


def resolve_backend():
    """Resolve the configured embed backend ('auto' probes Ollama)."""
    choice = config.embed_backend()
    if choice in ("ollama", "local"):
        return choice
    return "ollama" if ollama_embed_available() else "local"


def embed_text(text, backend=None, purpose="document"):
    backend = backend or resolve_backend()
    if backend == "ollama":
        return embed_ollama(text, purpose=purpose)
    return embed_local(text)


def backend_signature(backend):
    """Identifier stored in the vector store metadata."""
    if backend == "ollama":
        model = config.embed_model()
        suffix = "#tp" if _task_prefix(model, "document") else ""
        return "ollama:" + model + suffix
    return "local:hashed-bow-v2"


def embed_with_signature(text, signature):
    """Embed a query the same way the knowledge base was built."""
    if signature.startswith("ollama:"):
        model = signature.split(":", 1)[1].split("#", 1)[0]
        return embed_ollama(text, model=model, purpose="query")
    return embed_local(text)

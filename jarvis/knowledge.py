"""Knowledge base: "training" JARVIS on your own documents.

Port of whisplay-ai-chatbot's src/core/Knowledge.ts:
  - drop .txt / .md files into knowledge/
  - `jarvis train` chunks, embeds, and stores them locally
  - incremental: unchanged files (sha256) are skipped, changed files are
    re-indexed, removed files are cleaned up
  - retrieval applies a score threshold so unrelated questions don't get
    polluted with irrelevant context
"""

import hashlib
import os
import uuid

from . import config, embeddings
from .chunker import chunk_text
from .vectorstore import VectorStore

SKIP_NAMES = {"readme.md", "readme.txt"}


def store_path():
    return os.path.join(config.data_dir(), "knowledge.json")


def open_store():
    return VectorStore(store_path())


def _hash_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def knowledge_files():
    root = config.knowledge_dir()
    names = []
    for name in sorted(os.listdir(root)):
        lower = name.lower()
        if lower in SKIP_NAMES:
            continue
        if lower.endswith(".txt") or lower.endswith(".md"):
            names.append(name)
    return names


def train(rebuild=False, log=print):
    """Index the knowledge folder. Returns a summary dict."""
    backend = embeddings.resolve_backend()
    signature = embeddings.backend_signature(backend)
    dimension = len(embeddings.embed_text("test", backend=backend))
    log("[train] embeddings: %s (dim %d)" % (signature, dimension))

    store = open_store()
    if rebuild or not store.ensure_signature(signature, dimension):
        if not rebuild and not store.is_empty():
            log(
                "[train] embedding backend changed (%s -> %s), full rebuild"
                % (store.embed_signature(), signature)
            )
        store.reset(signature, dimension)

    files = knowledge_files()
    if not files:
        log("[train] no .txt/.md files found in %s" % config.knowledge_dir())

    existing = store.sources()
    indexed = skipped = 0

    for name in files:
        path = os.path.join(config.knowledge_dir(), name)
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        file_hash = _hash_text(content)

        if existing.get(name) == file_hash:
            log("[train] unchanged: %s" % name)
            skipped += 1
            continue
        if name in existing:
            store.delete_by_source(name)

        chunks = chunk_text(content, config.chunk_size(), config.chunk_overlap())
        for i, chunk in enumerate(chunks):
            vector = embeddings.embed_text(chunk, backend=backend)
            store.upsert(
                str(uuid.uuid4()),
                vector,
                {
                    "content": chunk,
                    "source": name,
                    "chunk_index": i,
                    "file_hash": file_hash,
                },
            )
            log("[train] %s: chunk %d/%d" % (name, i + 1, len(chunks)))
        indexed += 1

    removed = 0
    file_set = set(files)
    for source in list(store.sources()):
        if source not in file_set:
            store.delete_by_source(source)
            log("[train] removed knowledge for deleted file: %s" % source)
            removed += 1

    store.save()
    summary = {
        "indexed": indexed,
        "skipped": skipped,
        "removed": removed,
        "chunks": store.stats()["chunks"],
    }
    log(
        "[train] done: %(indexed)d indexed, %(skipped)d unchanged, "
        "%(removed)d removed, %(chunks)d chunks total" % summary
    )
    return summary


def search(query, top_k=None, store=None):
    """Search the knowledge base. Returns [] if it is empty."""
    store = store or open_store()
    if store.is_empty():
        return []
    vector = embeddings.embed_with_signature(query, store.embed_signature())
    return store.search(vector, top_k or config.rag_top_k())


def score_threshold(store=None):
    store = store or open_store()
    return config.rag_score_threshold(store.embed_signature())


def knowledge_context(query, store=None):
    """Relevant chunks above the score threshold, formatted for the
    system prompt — the getSystemPromptWithKnowledge() equivalent."""
    store = store or open_store()
    try:
        results = search(query, top_k=config.rag_top_k() * 2, store=store)
    except Exception as err:
        print("[RAG] knowledge search failed: %s" % err)
        return ""
    return context_from_results(
        results, score_threshold(store), config.rag_top_k()
    )


MAX_CHUNKS_PER_SOURCE = 2


def select_results(results, threshold, limit=None):
    """Filter search results for context building: drop scores below the
    threshold and keep at most MAX_CHUNKS_PER_SOURCE per file — in a
    grown knowledge base one topic-heavy file otherwise crowds every
    other source out of the context. Callers over-fetch (top_k * 2) and
    pass limit=top_k so capped slots are refilled from other sources."""
    kept = []
    per_source = {}
    for r in results:
        if r["score"] < threshold:
            continue
        source = r["payload"].get("source", "?")
        if per_source.get(source, 0) >= MAX_CHUNKS_PER_SOURCE:
            continue
        per_source[source] = per_source.get(source, 0) + 1
        kept.append(r)
        if limit is not None and len(kept) >= limit:
            break
    return kept


def context_from_results(results, threshold, limit=None):
    kept = select_results(results, threshold, limit)
    if not kept:
        return ""
    parts = []
    for r in kept:
        parts.append(
            "[%s | score %.2f]\n%s"
            % (r["payload"].get("source", "?"), r["score"], r["payload"].get("content", ""))
        )
    return (
        "Use the following knowledge from the local knowledge base to answer "
        "the question. If it does not cover the question, say what you do "
        "not know instead of guessing.\n\n" + "\n\n".join(parts)
    )

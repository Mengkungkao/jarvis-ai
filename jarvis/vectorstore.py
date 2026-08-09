"""Local vector store — a tiny, dependency-free stand-in for Qdrant.

Same responsibilities as whisplay-ai-chatbot's qdrant-vectordb.ts
(upsert, cosine search, delete-by-source, per-file hash tracking) but
persisted as a single JSON file with vectors packed as base64 float32,
so it loads fast and stays small enough for a Pi Zero 2W.
"""

import base64
import json
import os
import struct
import tempfile


def _pack(vec):
    return base64.b64encode(struct.pack("<%df" % len(vec), *vec)).decode("ascii")


def _unpack(blob):
    raw = base64.b64decode(blob)
    return list(struct.unpack("<%df" % (len(raw) // 4), raw))


def _cosine(a, b):
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


class VectorStore:
    def __init__(self, path):
        self.path = path
        self.meta = {"embed_signature": "", "dimension": 0}
        self.points = []  # {"id", "vector": packed, "payload": {...}}
        self._load()

    def _load(self):
        if not os.path.isfile(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self.meta = data.get("meta", self.meta)
            self.points = data.get("points", [])
        except (ValueError, OSError) as err:
            raise RuntimeError(
                "Vector store %s is unreadable (%s). "
                "Delete it and retrain." % (self.path, err)
            )

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=os.path.dirname(self.path) or ".", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"meta": self.meta, "points": self.points}, fh)
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    # ── collection-level ─────────────────────────────────────────
    def is_empty(self):
        return not self.points

    def embed_signature(self):
        return self.meta.get("embed_signature", "")

    def reset(self, embed_signature, dimension):
        self.meta = {"embed_signature": embed_signature, "dimension": dimension}
        self.points = []

    def ensure_signature(self, embed_signature, dimension):
        """True if store matches; False means a full rebuild is required."""
        if self.is_empty() and not self.meta.get("embed_signature"):
            self.reset(embed_signature, dimension)
            return True
        return (
            self.meta.get("embed_signature") == embed_signature
            and self.meta.get("dimension") == dimension
        )

    # ── points ───────────────────────────────────────────────────
    def upsert(self, point_id, vector, payload):
        self.points.append(
            {"id": point_id, "vector": _pack(vector), "payload": payload}
        )

    def delete_by_source(self, source):
        before = len(self.points)
        self.points = [
            p for p in self.points if p["payload"].get("source") != source
        ]
        return before - len(self.points)

    def sources(self):
        """Map of source file -> stored content hash."""
        result = {}
        for p in self.points:
            payload = p.get("payload", {})
            src = payload.get("source")
            if src:
                result[src] = payload.get("file_hash", "")
        return result

    def search(self, vector, top_k=3):
        scored = []
        for p in self.points:
            score = _cosine(vector, _unpack(p["vector"]))
            scored.append((score, p))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {"id": p["id"], "score": score, "payload": p["payload"]}
            for score, p in scored[:top_k]
        ]

    def stats(self):
        by_source = {}
        for p in self.points:
            src = p["payload"].get("source", "?")
            by_source[src] = by_source.get(src, 0) + 1
        return {
            "chunks": len(self.points),
            "files": len(by_source),
            "by_source": by_source,
            "embed_signature": self.embed_signature(),
            "dimension": self.meta.get("dimension", 0),
        }

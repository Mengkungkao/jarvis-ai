"""Pipeline tracing for development and debugging.

Every stage of the pipeline (RAG query, retrieval scores, LLM rounds,
tool calls, timings) emits events into a shared ring buffer. The debug
web console renders them live; `--debug` echoes them to the terminal.
"""

import threading
import time
from collections import deque


class Tracer:
    def __init__(self, maxlen=500, echo=False):
        self.events = deque(maxlen=maxlen)
        self.echo = echo
        self._lock = threading.Lock()
        self._seq = 0

    def emit(self, kind, **data):
        with self._lock:
            self._seq += 1
            event = {
                "seq": self._seq,
                "ts": time.time(),
                "kind": kind,
                "data": data,
            }
            self.events.append(event)
        if self.echo:
            summary = " ".join(
                "%s=%s" % (k, _short(v)) for k, v in data.items()
            )
            print("\033[2m[trace] %-14s %s\033[0m" % (kind, summary))
        return event

    def since(self, seq):
        with self._lock:
            return [e for e in self.events if e["seq"] > seq]

    def all(self):
        with self._lock:
            return list(self.events)


def _short(value, limit=120):
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"


# Shared default tracer: silent unless something turns echo on or the
# debug console reads from it.
default = Tracer()

"""Lightweight long-term memory: durable facts the user teaches JARVIS.

Simplified from whisplay-ai-chatbot's local-memory plugin: a JSON file of
short facts. The model saves facts with the remember tool ("remember that
the boiler service code is 4711"), and the most recent facts are injected
into the system prompt of every new conversation.
"""

import json
import os
import tempfile
import time

from . import config


def memory_path():
    return os.path.join(config.data_dir(), "memory.json")


def _load():
    path = memory_path()
    if not os.path.isfile(path):
        return {"facts": []}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data.get("facts"), list):
            return data
    except (ValueError, OSError):
        pass
    return {"facts": []}


def _save(data):
    path = memory_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def remember(fact):
    fact = " ".join(str(fact).split()).strip()
    if not fact:
        return False
    data = _load()
    if any(f["text"].lower() == fact.lower() for f in data["facts"]):
        return True
    data["facts"].append({"text": fact, "ts": int(time.time())})
    _save(data)
    return True


def facts(limit=None):
    items = _load()["facts"]
    if limit:
        items = items[-limit:]
    return [f["text"] for f in items]


def forget(index):
    """Remove fact by 1-based index (as shown by `jarvis memory`)."""
    data = _load()
    if 1 <= index <= len(data["facts"]):
        removed = data["facts"].pop(index - 1)
        _save(data)
        return removed["text"]
    return ""


def clear():
    _save({"facts": []})


def prompt_section():
    if not config.memory_enabled():
        return ""
    items = facts(limit=config.memory_max_inject())
    if not items:
        return ""
    lines = ["Things you remember about the user and their tasks:"]
    lines.extend("- " + item for item in items)
    return "\n".join(lines)

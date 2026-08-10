"""LLM backends.

- OllamaLLM: streaming chat with tool calling against a local (or LAN)
  Ollama server — the offline brain, mirroring ollama-llm.ts.
- TestLLM:   deterministic echo brain, like whisplay's LLM_SERVER=test,
  so the whole pipeline can run and be tested with no model at all.

Streaming interface: chat_stream(messages, tools) yields event dicts:
    {"type": "content",    "text": str}
    {"type": "thinking",   "text": str}
    {"type": "tool_calls", "calls": [{"function": {"name", "arguments"}}]}
"""

import json
import urllib.error
import urllib.request

from . import config


class OllamaLLM:
    def __init__(self, endpoint=None, model=None):
        self.endpoint = (endpoint or config.ollama_endpoint()).rstrip("/")
        self.model = model or config.chat_model()

    def available(self, timeout=3):
        try:
            with urllib.request.urlopen(
                self.endpoint + "/api/version", timeout=timeout
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    def has_model(self, name=None, timeout=5):
        name = name or self.model
        try:
            with urllib.request.urlopen(
                self.endpoint + "/api/tags", timeout=timeout
            ) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name", "") for m in data.get("models", [])]
            return any(m == name or m.split(":")[0] == name for m in models)
        except Exception:
            return False

    def _open_chat(self, messages, tools, think):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "think": think,
            "options": {"temperature": 0.7},
            "keep_alive": -1,
        }
        if tools:
            payload["tools"] = tools
        req = urllib.request.Request(
            self.endpoint + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        return urllib.request.urlopen(req, timeout=600)

    def chat_stream(self, messages, tools=None, think=False):
        try:
            resp = self._open_chat(messages, tools, think)
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8", "replace")[:400]
            if think and "does not support thinking" in body:
                # Model doesn't support Ollama's thinking mode (e.g.
                # ENABLE_THINKING=true with a non-reasoning model like
                # qwen2.5) — retry once without it instead of failing
                # the whole conversation turn.
                print(
                    "[ollama] model '%s' doesn't support thinking mode; "
                    "retrying without it. Set ENABLE_THINKING=false to "
                    "avoid this warning." % self.model
                )
                try:
                    resp = self._open_chat(messages, tools, False)
                except urllib.error.HTTPError as err2:
                    body2 = err2.read().decode("utf-8", "replace")[:400]
                    raise RuntimeError(
                        "Ollama chat failed (%d): %s" % (err2.code, body2)
                    )
            else:
                raise RuntimeError(
                    "Ollama chat failed (%d): %s" % (err.code, body)
                )
        with resp:
            for raw in resp:
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except ValueError:
                    continue
                message = data.get("message") or {}
                if message.get("thinking"):
                    yield {"type": "thinking", "text": message["thinking"]}
                if message.get("content"):
                    yield {"type": "content", "text": message["content"]}
                if message.get("tool_calls"):
                    yield {"type": "tool_calls", "calls": message["tool_calls"]}
                if data.get("done"):
                    break


class TestLLM:
    """No-model brain for pipeline tests and dry runs."""

    model = "test"

    def available(self, timeout=0):
        return True

    def has_model(self, name=None, timeout=0):
        return True

    def chat_stream(self, messages, tools=None, think=False):
        last_user = ""
        knowledge_injected = False
        for msg in messages:
            if msg.get("role") == "user":
                last_user = msg.get("content", "")
            if msg.get("role") == "system" and "knowledge base" in msg.get(
                "content", ""
            ):
                knowledge_injected = True
        reply = "[test] You said: %s" % last_user
        if knowledge_injected:
            reply += " (knowledge context was injected)"
        yield {"type": "content", "text": reply}

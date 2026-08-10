"""Conversation engine — the ChatFlow of this project.

Combines everything learned from whisplay-ai-chatbot:
  - idle-based chat history reset (CHAT_HISTORY_RESET_TIME)
  - RAG context injected per question above a score threshold
  - tool-calling loop with max-round cap, duplicate-call blocking, and a
    forced no-tools final answer (ported from ollama-llm.ts)
  - system prompt assembled from persona + skills list + memory facts

Backends:
  ollama      full agent (streaming, tools) via local/LAN Ollama
  extractive  no LLM at all — retrieval-only Q&A that runs on a
              Pi Zero 2W standalone
  test        echo brain for pipeline tests
"""

import json
import time

from . import config, knowledge, memory, skills, tools, trace
from .llm import OllamaLLM, TestLLM


def _stable_signature(call):
    fn = call.get("function", {})
    return "%s:%s" % (
        fn.get("name", ""),
        json.dumps(fn.get("arguments", {}), sort_keys=True, ensure_ascii=False),
    )


def resolve_backend():
    choice = config.backend()
    if choice in ("ollama", "extractive", "test"):
        return choice
    return "ollama" if OllamaLLM().available() else "extractive"


class ChatSession:
    def __init__(self, backend=None, quiet=False, tracer=None):
        if backend in (None, "", "auto"):
            backend = resolve_backend()
        self.backend = backend
        self.quiet = quiet
        self.trace = tracer or trace.default
        self.llm = None
        if self.backend == "ollama":
            self.llm = OllamaLLM()
        elif self.backend == "test":
            self.llm = TestLLM()
        self.tool_specs, self.tool_funcs = tools.build_tools()
        self.messages = []
        self.last_message_time = 0.0
        self.store = knowledge.open_store()
        self.reset()

    # ── history ──────────────────────────────────────────────────
    def build_system_prompt(self):
        parts = [config.system_prompt()]
        skills_part = skills.prompt_section()
        if skills_part:
            parts.append(skills_part)
        memory_part = memory.prompt_section()
        if memory_part:
            parts.append(memory_part)
        return "\n\n".join(parts)

    def reset(self):
        self.messages = [
            {"role": "system", "content": self.build_system_prompt()}
        ]

    def _maybe_reset_on_idle(self):
        reset_sec = config.chat_history_reset_sec()
        if (
            self.last_message_time
            and reset_sec > 0
            and time.time() - self.last_message_time > reset_sec
        ):
            self._log("[chat] idle for >%ds, starting a fresh conversation" % reset_sec)
            self.reset()

    def _log(self, text):
        if not self.quiet:
            print(text)

    # ── main entry ───────────────────────────────────────────────
    def ask(self, text, on_content=None, on_thinking=None, on_tool=None):
        """Answer one user message. Streams via callbacks, returns the
        final answer text."""
        text = text.strip()
        if not text:
            return ""
        self._maybe_reset_on_idle()
        self.last_message_time = time.time()
        started = time.time()
        self.trace.emit("ask", text=text, backend=self.backend)

        if self.backend == "extractive":
            answer = self._extractive_answer(text)
            self.trace.emit(
                "answer", text=answer,
                seconds=round(time.time() - started, 2),
            )
            if on_content:
                on_content(answer)
            return answer

        # RAG: inject relevant knowledge for this question.
        if config.rag_enabled():
            context = self._rag_context(text)
            if context:
                self.messages.append({"role": "system", "content": context})

        self.messages.append({"role": "user", "content": text})
        answer = self._run_llm(
            on_content, on_thinking, on_tool,
            round_index=0, seen_signatures=set(),
        )
        self.trace.emit(
            "answer", text=answer, seconds=round(time.time() - started, 2)
        )
        return answer

    def _rag_context(self, query):
        """Search once; feed both the trace and the injected context."""
        try:
            results = knowledge.search(
                query, top_k=config.rag_top_k() * 2, store=self.store
            )
        except Exception as err:
            self.trace.emit("rag", query=query, error=str(err))
            return ""
        threshold = knowledge.score_threshold(self.store)
        kept = knowledge.select_results(
            results, threshold, config.rag_top_k()
        )
        kept_ids = {id(r) for r in kept}
        self.trace.emit(
            "rag",
            query=query,
            threshold=threshold,
            results=[
                {
                    "score": round(r["score"], 3),
                    "source": r["payload"].get("source", "?"),
                    "used": id(r) in kept_ids,
                    "content": r["payload"].get("content", "")[:200],
                }
                for r in results
            ],
        )
        return knowledge.context_from_results(kept, threshold)

    # ── ollama/test agent loop ───────────────────────────────────
    def _run_llm(self, on_content, on_thinking, on_tool, round_index,
                 seen_signatures, tools_enabled=True):
        use_tools = (
            tools_enabled
            and self.backend == "ollama"
            and config.enable_tools()
        )
        answer_parts = []
        tool_calls = []
        llm_started = time.time()
        self.trace.emit(
            "llm_round",
            round=round_index,
            model=getattr(self.llm, "model", "?"),
            messages=len(self.messages),
            tools=use_tools,
        )
        try:
            for event in self.llm.chat_stream(
                self.messages,
                tools=self.tool_specs if use_tools else None,
                think=config.enable_thinking(),
            ):
                if event["type"] == "content":
                    answer_parts.append(event["text"])
                    if on_content:
                        on_content(event["text"])
                elif event["type"] == "thinking" and on_thinking:
                    on_thinking(event["text"])
                elif event["type"] == "tool_calls":
                    tool_calls.extend(event["calls"])
        except Exception as err:
            error_text = "LLM error: %s" % err
            self._log("[chat] %s" % error_text)
            self.trace.emit("llm_error", error=str(err))
            if on_content and not answer_parts:
                on_content(error_text)
            return "".join(answer_parts) or error_text

        answer = "".join(answer_parts)
        self.trace.emit(
            "llm_done",
            seconds=round(time.time() - llm_started, 2),
            chars=len(answer),
            tool_calls=[
                c.get("function", {}).get("name", "?") for c in tool_calls
            ],
        )
        self.messages.append(
            {"role": "assistant", "content": answer}
            if not tool_calls
            else {"role": "assistant", "content": answer, "tool_calls": tool_calls}
        )
        if not tool_calls:
            return answer

        # ── tool-loop protections, ported from ollama-llm.ts ─────
        if round_index >= config.max_tool_rounds():
            self._log("[chat] max tool rounds reached, forcing final answer")
            self.trace.emit("forced_answer", reason="max_tool_rounds")
            return self._forced_answer(
                "You have gathered enough tool results. Answer the user's "
                "request now using what you already have. Do not call any "
                "more tools and do not mention tools or internal markers.",
                on_content, on_thinking,
            )
        duplicate = next(
            (c for c in tool_calls if _stable_signature(c) in seen_signatures),
            None,
        )
        if duplicate:
            name = duplicate.get("function", {}).get("name", "tool")
            self._log("[chat] repeated %s call blocked" % name)
            self.trace.emit("forced_answer", reason="duplicate_tool", tool=name)
            return self._forced_answer(
                "The %s tool was already called with the same arguments. "
                "Answer the user now from the results you already have, "
                "without calling tools or mentioning them." % name,
                on_content, on_thinking,
            )
        for call in tool_calls:
            seen_signatures.add(_stable_signature(call))

        for call in tool_calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", {}) or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            func = self.tool_funcs.get(name)
            if on_tool:
                on_tool(name)
            self.trace.emit("tool_call", name=name, args=args)
            tool_started = time.time()
            if func:
                try:
                    result = func(args)
                except Exception as err:
                    result = "Error executing %s: %s" % (name, err)
            else:
                result = "Tool %s not found." % name
            self.trace.emit(
                "tool_result",
                name=name,
                seconds=round(time.time() - tool_started, 2),
                result=result[:300],
            )
            self._log("[tool] %s -> %s" % (name, result[:120].replace("\n", " ")))
            self.messages.append(
                {"role": "tool", "content": result, "tool_name": name}
            )

        return self._run_llm(
            on_content, on_thinking, on_tool,
            round_index + 1, seen_signatures,
        )

    def _forced_answer(self, instruction, on_content, on_thinking):
        self.messages.append({"role": "system", "content": instruction})
        return self._run_llm(
            on_content, on_thinking, None,
            round_index=config.max_tool_rounds(),
            seen_signatures=set(),
            tools_enabled=False,
        )

    # ── extractive brain (no LLM, Pi Zero 2W friendly) ───────────
    def _extractive_answer(self, text):
        try:
            results = knowledge.search(
                text, top_k=config.rag_top_k() * 2, store=self.store
            )
        except Exception as err:
            self.trace.emit("rag", query=text, error=str(err))
            return "Knowledge search failed: %s" % err
        threshold = knowledge.score_threshold(self.store)
        kept = knowledge.select_results(
            results, threshold, config.rag_top_k()
        )
        kept_ids = {id(r) for r in kept}
        self.trace.emit(
            "rag",
            query=text,
            threshold=threshold,
            results=[
                {
                    "score": round(r["score"], 3),
                    "source": r["payload"].get("source", "?"),
                    "used": id(r) in kept_ids,
                    "content": r["payload"].get("content", "")[:200],
                }
                for r in results
            ],
        )
        if not kept:
            hints = []
            skill_names = [s["name"] for s in skills.discover()]
            if skill_names:
                hints.append("Known skills: %s." % ", ".join(skill_names))
            if self.store.is_empty():
                hints.append(
                    "The knowledge base is empty — add files to knowledge/ "
                    "and run: jarvis train"
                )
            return (
                "I could not find anything about that in my knowledge base. "
                + " ".join(hints)
            ).strip()
        parts = []
        for r in kept:
            parts.append(
                "%s\n(source: %s, relevance %.0f%%)"
                % (
                    r["payload"].get("content", "").strip(),
                    r["payload"].get("source", "?"),
                    r["score"] * 100,
                )
            )
        return "\n\n".join(parts)

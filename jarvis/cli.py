"""Command-line interface.

  jarvis chat               interactive conversation (default)
  jarvis ask "question"     one-shot question
  jarvis train [--rebuild]  index knowledge/ into the local vector store
  jarvis status             backend, models, knowledge base, skills, memory
  jarvis skills             list taught skills
  jarvis memory             list remembered facts (--forget N, --clear)
  jarvis voice              Whisplay HAT / microphone voice loop (Pi)
"""

import argparse
import sys

from . import config, knowledge, memory, skills
from .chat import ChatSession, resolve_backend
from .llm import OllamaLLM


def cmd_train(args):
    knowledge.train(rebuild=args.rebuild)
    return 0


def _print_stream(chunk):
    sys.stdout.write(chunk)
    sys.stdout.flush()


def _print_thinking(chunk):
    sys.stdout.write("\033[2m%s\033[0m" % chunk)
    sys.stdout.flush()


def _make_session(args):
    session = ChatSession(backend=args.backend)
    print("[jarvis] brain: %s" % session.backend, end="")
    if session.backend == "ollama":
        print(" (%s @ %s)" % (session.llm.model, session.llm.endpoint))
        if not session.llm.has_model():
            print(
                "[jarvis] WARNING: model '%s' not found on the Ollama server. "
                "Pull it with: ollama pull %s"
                % (session.llm.model, session.llm.model)
            )
    else:
        print()
    return session


def cmd_ask(args):
    session = _make_session(args)
    session.ask(
        " ".join(args.question),
        on_content=_print_stream,
        on_thinking=_print_thinking if config.enable_thinking() else None,
        on_tool=lambda name: print("\n[tool] %s ..." % name),
    )
    print()
    return 0


def cmd_chat(args):
    session = _make_session(args)
    print(
        "[jarvis] type your message. Commands: /reset  /status  /exit"
    )
    while True:
        try:
            text = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text in ("/exit", "/quit"):
            break
        if text == "/reset":
            session.reset()
            print("[jarvis] conversation reset")
            continue
        if text == "/status":
            _print_status(session.backend)
            continue
        sys.stdout.write("jarvis> ")
        session.ask(
            text,
            on_content=_print_stream,
            on_thinking=_print_thinking if config.enable_thinking() else None,
            on_tool=lambda name: print("\n[tool] %s ..." % name),
        )
        print()
    return 0


def _print_status(active_backend=None):
    llm = OllamaLLM()
    reachable = llm.available()
    print("backend (configured): %s" % config.backend())
    print("backend (resolved):   %s" % (active_backend or resolve_backend()))
    print("ollama endpoint:      %s  [%s]" % (
        llm.endpoint, "reachable" if reachable else "NOT reachable"))
    if reachable:
        print("chat model:           %s  [%s]" % (
            llm.model,
            "installed" if llm.has_model() else "MISSING — ollama pull " + llm.model,
        ))
        print("embed model:          %s  [%s]" % (
            config.embed_model(),
            "installed" if llm.has_model(config.embed_model()) else "missing",
        ))
    store = knowledge.open_store()
    stats = store.stats()
    print("knowledge base:       %d chunks from %d files (%s)" % (
        stats["chunks"], stats["files"], stats["embed_signature"] or "untrained"))
    for src, count in sorted(stats["by_source"].items()):
        print("   - %s (%d chunks)" % (src, count))
    found = skills.discover()
    print("skills:               %d" % len(found))
    for s in found:
        print("   - %s: %s" % (s["name"], s["description"]))
    facts = memory.facts()
    print("memory facts:         %d" % len(facts))


def cmd_status(args):
    _print_status()
    return 0


def cmd_skills(args):
    found = skills.discover()
    if not found:
        print(
            "No skills yet. Create skills/<name>/SKILL.md — see skills/README.md"
        )
        return 0
    for s in found:
        print("%s — %s" % (s["name"], s["description"] or "(no description)"))
    return 0


def cmd_memory(args):
    if args.clear:
        memory.clear()
        print("Memory cleared.")
        return 0
    if args.forget:
        removed = memory.forget(args.forget)
        print("Forgot: %s" % removed if removed else "No fact #%d" % args.forget)
        return 0
    facts = memory.facts()
    if not facts:
        print("No facts remembered yet. In chat, say: remember that ...")
        return 0
    for i, fact in enumerate(facts, 1):
        print("%2d. %s" % (i, fact))
    return 0


def cmd_voice(args):
    from .voice import run_voice_loop

    return run_voice_loop(backend=args.backend)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description="JARVIS — offline, trainable AI assistant",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "ollama", "extractive", "test"],
        default=None,
        help="override JARVIS_BACKEND for this run",
    )
    sub = parser.add_subparsers(dest="command")

    p_train = sub.add_parser("train", help="index knowledge/ files")
    p_train.add_argument(
        "--rebuild", action="store_true", help="delete and re-index everything"
    )
    p_ask = sub.add_parser("ask", help="ask one question")
    p_ask.add_argument("question", nargs="+")
    sub.add_parser("chat", help="interactive chat (default)")
    sub.add_parser("status", help="show configuration and knowledge stats")
    sub.add_parser("skills", help="list taught skills")
    p_mem = sub.add_parser("memory", help="list remembered facts")
    p_mem.add_argument("--forget", type=int, metavar="N", help="forget fact N")
    p_mem.add_argument("--clear", action="store_true", help="forget everything")
    sub.add_parser("voice", help="voice loop (Whisplay HAT or terminal)")

    args = parser.parse_args(argv)
    if args.backend is None:
        args.backend = None if config.backend() else "auto"

    handlers = {
        "train": cmd_train,
        "ask": cmd_ask,
        "chat": cmd_chat,
        "status": cmd_status,
        "skills": cmd_skills,
        "memory": cmd_memory,
        "voice": cmd_voice,
        None: cmd_chat,
    }
    try:
        return handlers[args.command](args)
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    sys.exit(main())

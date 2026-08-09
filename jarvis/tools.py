"""Tools the LLM can call (Ollama function-calling format).

The whisplay-ai-chatbot equivalent is config/llm-tools.ts. Kept small on
purpose — small offline models get confused by big tool lists:

  search_knowledge  deep-dive into the trained knowledge base
  read_skill        pull the full instructions of a taught skill
  remember          save a durable fact to long-term memory
  get_current_time  clock access (offline devices still know the time)
"""

import time

from . import config, knowledge, memory, skills


def _tool_search_knowledge(args):
    query = str(args.get("query", "")).strip()
    if not query:
        return "Error: query is required."
    results = knowledge.search(query, top_k=config.rag_top_k())
    threshold = knowledge.score_threshold()
    kept = [r for r in results if r["score"] >= threshold]
    if not kept:
        return (
            "No relevant knowledge found. Answer from general knowledge and "
            "say the knowledge base does not cover this."
        )
    lines = []
    for r in kept:
        lines.append(
            "(%.2f, %s) %s"
            % (
                r["score"],
                r["payload"].get("source", "?"),
                r["payload"].get("content", ""),
            )
        )
    return "\n\n".join(lines)


def _tool_read_skill(args):
    name = str(args.get("name", "")).strip()
    body = skills.read(name)
    if not body:
        available = ", ".join(s["name"] for s in skills.discover()) or "none"
        return "Skill '%s' not found. Available skills: %s" % (name, available)
    return body


def _tool_remember(args):
    fact = str(args.get("fact", "")).strip()
    if not fact:
        return "Error: fact is required."
    memory.remember(fact)
    return "Saved to memory: %s" % fact


def _tool_get_current_time(args):
    return time.strftime("%A, %Y-%m-%d %H:%M:%S %Z")


def build_tools():
    """Return (tool_specs, func_map) like llmTools / llmFuncMap."""
    specs = [
        {
            "type": "function",
            "function": {
                "name": "search_knowledge",
                "description": (
                    "Search the local knowledge base the user trained. Use it "
                    "whenever the question may relate to the user's documents, "
                    "tasks, or domain."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query in plain words.",
                        }
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_skill",
                "description": (
                    "Read the full step-by-step instructions of a named skill "
                    "before performing that task."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Skill name from the skill list.",
                        }
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "remember",
                "description": (
                    "Save a short durable fact to long-term memory when the "
                    "user asks you to remember something."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fact": {
                            "type": "string",
                            "description": "The fact to remember, one sentence.",
                        }
                    },
                    "required": ["fact"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "Get the current local date and time.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]
    funcs = {
        "search_knowledge": _tool_search_knowledge,
        "read_skill": _tool_read_skill,
        "remember": _tool_remember,
        "get_current_time": _tool_get_current_time,
    }
    return specs, funcs

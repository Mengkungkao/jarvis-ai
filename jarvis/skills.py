"""Skills: teach JARVIS *procedures* for specific tasks.

Same convention as whisplay-ai-chatbot's hardness skill tools:
each skill is a directory under skills/ containing a SKILL.md with
optional frontmatter:

    skills/
      morning-report/
        SKILL.md      <- name / description frontmatter + instructions

The skill list (names + descriptions) is injected into the system prompt;
the model pulls the full instructions with the read_skill tool when the
task comes up. In extractive mode, `jarvis skills` and read_skill still
work for the human operator.
"""

import os

from . import config

MAX_SKILL_CHARS = 8000


def _parse_frontmatter(text):
    """Return (meta dict, body). Frontmatter is optional key: value lines."""
    meta = {}
    body = text
    if text.startswith("---"):
        lines = text.splitlines()
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
        if end is not None:
            for line in lines[1:end]:
                if ":" in line:
                    key, _, value = line.partition(":")
                    meta[key.strip().lower()] = value.strip()
            body = "\n".join(lines[end + 1:]).strip()
    return meta, body


def discover():
    """List available skills: [{name, description, path}]."""
    root = config.skills_dir()
    found = []
    for entry in sorted(os.listdir(root)):
        skill_md = os.path.join(root, entry, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue
        try:
            with open(skill_md, "r", encoding="utf-8", errors="replace") as fh:
                meta, _ = _parse_frontmatter(fh.read())
        except OSError:
            continue
        found.append(
            {
                "name": meta.get("name", entry),
                "dir": entry,
                "description": meta.get("description", ""),
                "path": skill_md,
            }
        )
    return found


def read(name):
    """Full SKILL.md body for a skill by name (or directory name)."""
    for skill in discover():
        if name in (skill["name"], skill["dir"]):
            with open(skill["path"], "r", encoding="utf-8", errors="replace") as fh:
                _, body = _parse_frontmatter(fh.read())
            if len(body) > MAX_SKILL_CHARS:
                body = body[:MAX_SKILL_CHARS] + "\n[... truncated]"
            return body
    return ""


def prompt_section():
    """Skill list for the system prompt; empty string if no skills."""
    found = discover()
    if not found:
        return ""
    lines = ["You have these task skills available:"]
    for skill in found:
        desc = skill["description"] or "(no description)"
        lines.append("- %s: %s" % (skill["name"], desc))
    lines.append(
        "When the user asks for one of these tasks, call the read_skill tool "
        "first and follow its instructions."
    )
    return "\n".join(lines)

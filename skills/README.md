# Skills — how you teach JARVIS tasks

A skill is a folder with a `SKILL.md` describing how to perform one task:

    skills/
      morning-briefing/
        SKILL.md

`SKILL.md` starts with optional frontmatter, then the instructions:

    ---
    name: morning-briefing
    description: What to say when the user asks for their morning briefing.
    ---
    Step-by-step instructions for the task...

The list of skills (name + description) is injected into the system prompt.
When the task comes up, the LLM calls the `read_skill` tool to load the full
instructions and follows them. Check what is taught with:

    ./jarvis-cli skills

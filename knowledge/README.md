# Knowledge folder — how you train JARVIS

Drop `.txt` or `.md` files with the facts you want JARVIS to know, then run:

    ./jarvis-cli train

- Files are chunked, embedded, and stored locally in `data/knowledge.json`.
- Training is incremental: unchanged files are skipped, edited files are
  re-indexed, deleted files are removed from the knowledge base.
- README files in this folder are not indexed.

Tips for good answers:
- One topic per file, short paragraphs, plain language.
- State facts explicitly ("The greenhouse fan turns on at 28 degrees"),
  because questions are matched against sentence content.
- After changing the embedding backend (local <-> ollama), run
  `./jarvis-cli train --rebuild`.

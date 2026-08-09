"""Sentence-aware text chunking with overlap.

Python port of whisplay-ai-chatbot's src/utils/knowledge.ts chunkText():
normalize whitespace, split into sentences (CJK and Latin punctuation),
pack sentences into chunks up to max_size chars, then prepend the tail
of the previous chunk as overlap context.
"""

import re

_SENTENCE_SPLIT = re.compile(r"(?<=[。！？.!?])")


def split_sentences(text):
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def chunk_text(text, max_size=500, overlap=80):
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []

    chunks = []
    current = ""
    for sentence in split_sentences(clean):
        if len(current) + len(sentence) + 1 <= max_size:
            current = (current + " " + sentence).strip()
        else:
            if current:
                chunks.append(current)
            # A single sentence longer than max_size gets hard-split.
            while len(sentence) > max_size:
                chunks.append(sentence[:max_size])
                sentence = sentence[max_size:]
            current = sentence
    if current:
        chunks.append(current)

    if overlap > 0 and len(chunks) > 1:
        result = [chunks[0]]
        for i in range(1, len(chunks)):
            result.append(chunks[i - 1][-overlap:] + " " + chunks[i])
        return result
    return chunks

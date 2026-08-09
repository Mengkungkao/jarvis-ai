"""JARVIS — a fully offline, trainable AI assistant.

Inspired by PiSugar's Whisplay / whisplay-ai-chatbot architecture:
  - pluggable brains (Ollama LLM, extractive RAG-only, test)
  - trainable knowledge base (chunk -> embed -> local vector store)
  - skills (SKILL.md task procedures the model can discover and follow)
  - lightweight long-term memory (facts)
  - optional Whisplay HAT voice front-end for Raspberry Pi

Pure Python standard library. No cloud. Runs on anything from a
Pi Zero 2W (extractive mode) to a desktop (Ollama mode).
"""

__version__ = "0.1.0"

import json
from pathlib import Path
from typing import List, Dict


class ConversationMemory:
    def __init__(self, config: dict) -> None:
        self.config = config
        self.data_dir = Path(config.get("paths", {}).get("data_dir", "data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.conversation_path = self.data_dir / "conversation.json"
        self.messages: List[Dict[str, str]] = []
        self._load()

    def _load(self) -> None:
        if self.conversation_path.exists():
            try:
                self.messages = json.loads(self.conversation_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.messages = []

    def append(self, prompt: str, response: str) -> None:
        self.messages.append({"user": prompt, "assistant": response})
        max_messages = self.config.get("assistant", {}).get("max_history_messages", 12)
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]
        self.conversation_path.write_text(json.dumps(self.messages, indent=2), encoding="utf-8")

    def build_prompt(self, prompt: str) -> str:
        system_prompt = self.config.get("assistant", {}).get("system_prompt", "You are JARVIS.")
        history = ""
        for item in self.messages[-6:]:
            history += f"User: {item['user']}\nAssistant: {item['assistant']}\n"
        return f"{system_prompt}\n\nConversation history:\n{history}\nUser: {prompt}\nAssistant:"

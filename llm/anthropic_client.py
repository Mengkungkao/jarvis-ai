import os

from anthropic import Anthropic


class AnthropicClient:
    def __init__(self, config: dict, logger) -> None:
        self.config = config
        self.logger = logger
        self.client = None
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
        self._init_client()

    def _init_client(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            self.logger.warning("Anthropic API key is not configured")
            return
        self.client = Anthropic(api_key=api_key)
        self.logger.info("Anthropic client initialized")

    def generate(self, prompt: str) -> str:
        if self.client is None:
            return "Claude API is not configured. Please set ANTHROPIC_API_KEY."
        response = self.client.messages.create(
            model=self.model,
            max_tokens=256,
            temperature=0.7,
            system=self.config.get("assistant", {}).get("system_prompt", "You are JARVIS."),
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text if response.content else ""
        self.logger.info("Claude response: %s", content)
        return content

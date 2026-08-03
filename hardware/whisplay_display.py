import json
import os
import urllib.error
import urllib.request
from typing import Optional


class WhisplayDisplay:
    def __init__(self, config: dict, logger) -> None:
        self.config = config
        self.logger = logger
        self.enabled = config.get("hardware", {}).get("display_enabled", True)
        self.daemon_enabled = config.get("hardware", {}).get("whisplay_daemon_enabled", True)
        self.daemon_url = config.get("hardware", {}).get("whisplay_daemon_url", "http://127.0.0.1:8080")
        self.timeout = float(config.get("hardware", {}).get("whisplay_daemon_timeout_seconds", 1.0))

    def show(self, message: str) -> None:
        if not self.enabled:
            return
        print(f"[DISPLAY] {message}")
        self.logger.info("Display message: %s", message)
        self._publish_to_daemon(message)

    def publish_status(self, status: str, message: Optional[str] = None) -> None:
        if not self.enabled:
            return
        payload = {"status": status, "message": message or status, "source": "jarvis-ai"}
        self._post_json("/status", payload)

    async def boot_animation(self) -> None:
        if not self.enabled:
            return
        for state in ["JARVIS", "READY", "BOOT"]:
            self.show(state)
            import asyncio
            await asyncio.sleep(0.4)

    def _publish_to_daemon(self, message: str) -> None:
        if not self.daemon_enabled:
            return
        base_url = os.getenv("WHISPLAY_DAEMON_URL", self.daemon_url).rstrip("/")
        if not base_url:
            return
        try:
            self._post_json("/display", {"message": message, "source": "jarvis-ai"})
        except Exception as exc:  # pragma: no cover - runtime fallback
            self.logger.warning("Whisplay daemon unavailable: %s", exc)

    def _post_json(self, path: str, payload: dict) -> None:
        base_url = os.getenv("WHISPLAY_DAEMON_URL", self.daemon_url).rstrip("/")
        if not base_url:
            return
        request = urllib.request.Request(
            f"{base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            response.read()

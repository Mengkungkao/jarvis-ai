from time import sleep


class WhisplayDisplay:
    def __init__(self, config: dict, logger) -> None:
        self.config = config
        self.logger = logger
        self.enabled = config.get("hardware", {}).get("display_enabled", True)

    def show(self, message: str) -> None:
        if not self.enabled:
            return
        print(f"[DISPLAY] {message}")
        self.logger.info("Display message: %s", message)

    async def boot_animation(self) -> None:
        if not self.enabled:
            return
        for state in ["JARVIS", "READY", "BOOT"]:
            self.show(state)
            import asyncio
            await asyncio.sleep(0.4)

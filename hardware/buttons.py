import asyncio

try:
    import RPi.GPIO as GPIO
except Exception:  # pragma: no cover - runtime fallback
    GPIO = None


class ButtonController:
    def __init__(self, config: dict, logger) -> None:
        self.config = config
        self.logger = logger
        self.gpio = config.get("hardware", {}).get("button_gpio", 17)
        self.gpio_available = GPIO is not None
        self._setup_gpio()

    def _setup_gpio(self) -> None:
        if not self.gpio_available:
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    async def wait_for_press(self) -> None:
        self.logger.info("Waiting for button press")
        if self.gpio_available:
            self.logger.info("Waiting on GPIO %s", self.gpio)
            await asyncio.to_thread(GPIO.wait_for_edge, self.gpio, GPIO.FALLING)
            return
        # Fall back to a short delay when GPIO support is unavailable in the current environment.
        await asyncio.sleep(0.1)

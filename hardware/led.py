try:
    import RPi.GPIO as GPIO
except Exception:  # pragma: no cover - runtime fallback
    GPIO = None


class LedController:
    def __init__(self, config: dict, logger) -> None:
        self.config = config
        self.logger = logger
        self.gpio = config.get("hardware", {}).get("led_gpio", 27)
        self.gpio_available = GPIO is not None
        self._setup_gpio()

    def _setup_gpio(self) -> None:
        if not self.gpio_available:
            return
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.gpio, GPIO.OUT)

    def set_status(self, state: str) -> None:
        states = {
            "idle": "blue",
            "listening": "cyan",
            "processing": "yellow",
            "speaking": "green",
            "error": "red",
            "boot": "white",
        }
        color = states.get(state, "off")
        self.logger.info("LED status: %s (%s)", state, color)
        if self.gpio_available:
            GPIO.output(self.gpio, color != "off")
        print(f"[LED] {state} -> {color}")

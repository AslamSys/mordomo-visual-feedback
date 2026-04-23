import asyncio
import logging

logger = logging.getLogger("visual-feedback.led")

try:
    from rpi_ws281x import PixelStrip, Color as _Color
    _HAS_HW = True
except ImportError:
    _HAS_HW = False
    logger.warning("rpi_ws281x not available — running in mock mode (no GPIO output)")


def _make_color(r: int, g: int, b: int) -> int:
    if _HAS_HW:
        return _Color(r, g, b)
    return (r << 16) | (g << 8) | b


class LEDController:
    def __init__(self, config):
        self._config = config
        self._strip = None

    async def start(self):
        cfg = self._config

        def _init():
            if not _HAS_HW:
                return None
            try:
                strip = PixelStrip(
                    cfg.led_count,
                    cfg.led_pin,
                    cfg.led_freq_hz,
                    cfg.led_dma,
                    cfg.led_invert,
                    cfg.led_brightness,
                    cfg.led_channel,
                )
                strip.begin()
                return strip
            except Exception as e:
                logger.error(f"Physical LED initialization failed ({e}). Falling back to mock mode.")
                return None

        self._strip = await asyncio.to_thread(_init)
        logger.info(
            f"LED strip {'initialized' if _HAS_HW else 'mocked'}: "
            f"{cfg.led_count} LEDs on GPIO{cfg.led_pin}"
        )

    def set_pixel(self, i: int, color: tuple):
        if self._strip:
            self._strip.setPixelColor(i, _make_color(*color))

    def show(self):
        if self._strip:
            self._strip.show()

    def set_brightness(self, brightness: int):
        if self._strip:
            self._strip.setBrightness(brightness)
            self._strip.show()

    def clear(self):
        for i in range(self._config.led_count):
            self.set_pixel(i, (0, 0, 0))
        self.show()

    @property
    def count(self) -> int:
        return self._config.led_count

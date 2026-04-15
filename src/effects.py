"""
LED Effects — async coroutines that run until cancelled.
Each effect controls the LED ring and loops until the task is cancelled.
"""
import asyncio
import math


def _scale(color: tuple, factor: float) -> tuple:
    return (
        int(color[0] * factor),
        int(color[1] * factor),
        int(color[2] * factor),
    )


def _blend(a: tuple, b: tuple, t: float) -> tuple:
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def _fill(led, color: tuple):
    for i in range(led.count):
        led.set_pixel(i, color)
    led.show()


# ---------------------------------------------------------------------------
# Effects
# ---------------------------------------------------------------------------

async def solid(led, color: tuple):
    """Static color — holds until cancelled."""
    _fill(led, color)
    await asyncio.sleep(float("inf"))


async def off(led):
    _fill(led, (0, 0, 0))
    await asyncio.sleep(float("inf"))


async def breathing(led, color: tuple, speed: float = 1.0):
    """Slow sine-wave fade in/out."""
    step = 0.0
    while True:
        factor = (math.sin(step * math.pi * 2) + 1) / 2  # 0.0 → 1.0
        _fill(led, _scale(color, max(0.05, factor)))
        step += 0.01 * speed
        await asyncio.sleep(0.03)


async def flash(led, color: tuple, times: int = 2, duration: float = 0.15):
    """Quick on/off flashes — does NOT loop."""
    for _ in range(times):
        _fill(led, color)
        await asyncio.sleep(duration)
        _fill(led, (0, 0, 0))
        await asyncio.sleep(duration)


async def blink(led, color: tuple, times: int = 3, on_ms: float = 0.2, off_ms: float = 0.2):
    """Blinking — does NOT loop."""
    for _ in range(times):
        _fill(led, color)
        await asyncio.sleep(on_ms)
        _fill(led, (0, 0, 0))
        await asyncio.sleep(off_ms)


async def fade_to(led, color_from: tuple, color_to: tuple, duration: float = 0.5):
    """One-shot linear fade between two colours."""
    steps = max(1, int(duration / 0.03))
    for s in range(steps + 1):
        _fill(led, _blend(color_from, color_to, s / steps))
        await asyncio.sleep(0.03)


async def spinner(led, color: tuple, tail: int = 3, speed: float = 0.08):
    """Rotating comet tail — loops until cancelled."""
    count = led.count
    pos = 0
    while True:
        for i in range(count):
            dist = (i - pos) % count
            factor = max(0.0, (tail - dist) / tail) if dist < tail else 0.0
            led.set_pixel(i, _scale(color, factor))
        led.show()
        pos = (pos + 1) % count
        await asyncio.sleep(speed)


async def strobe(led, color: tuple, interval: float = 0.1):
    """Rapid strobe — loops until cancelled."""
    while True:
        _fill(led, color)
        await asyncio.sleep(interval)
        _fill(led, (0, 0, 0))
        await asyncio.sleep(interval)


async def hold(led):
    """No-op holder — keeps the current state until cancelled."""
    await asyncio.sleep(float("inf"))

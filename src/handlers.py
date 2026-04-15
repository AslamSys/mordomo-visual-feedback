"""
Event handler — maps NATS subjects to LED effects via a priority queue.
A running effect is cancelled only when a higher- or equal-priority event arrives.
"""
import asyncio
import json
import logging
from typing import Coroutine

from src import effects
from src.led import LEDController
from src.audio_sync import AudioSync

logger = logging.getLogger("visual-feedback.handlers")

# Higher number = higher priority
PRIORITY: dict[str, int] = {
    "security.intrusion": 10,
    "error":              10,   # prefix match for error.*
    "system.shutdown":     9,
    "brain.processing":    8,
    "tts.speaking_started": 7,
    "conversation.started": 7,
    "tts.speaking_stopped": 6,
    "conversation.ended":   6,
    "speaker.verified":     6,
    "speaker.rejected":     3,
    "wake_word.detected":   5,
    "system.started":       1,
}

# Context colours for TTS (sent by Brain in tts.speaking_started payload)
CONTEXT_COLORS: dict[str, tuple] = {
    "normal":   (0, 255, 0),
    "info":     (0, 150, 255),
    "success":  (50, 255, 50),
    "warning":  (255, 200, 0),
    "alert":    (255, 120, 0),
    "critical": (255, 0, 0),
    "error":    (180, 0, 255),
    "security": (255, 0, 0),
}

COLOR_BLUE  = (0, 150, 255)
COLOR_GREEN = (0, 255, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_RED   = (255, 0, 0)
COLOR_PURPLE = (180, 0, 255)


class EventHandler:
    def __init__(self, led: LEDController, audio_sync: AudioSync):
        self._led = led
        self._audio_sync = audio_sync
        self._current_task: asyncio.Task | None = None
        self._current_priority: int = 0
        self._last_idle_color: tuple = COLOR_BLUE

    # ------------------------------------------------------------------
    def _priority_for(self, subject: str) -> int:
        if subject.startswith("error."):
            return PRIORITY["error"]
        return PRIORITY.get(subject, 0)

    # ------------------------------------------------------------------
    async def dispatch(self, subject: str, data: dict):
        priority = self._priority_for(subject)

        # Only allow equal-or-higher priority to interrupt
        if (
            priority < self._current_priority
            and self._current_task
            and not self._current_task.done()
        ):
            logger.debug(f"Ignored {subject} (prio {priority} < current {self._current_priority})")
            return

        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass

        self._current_priority = priority
        coro = self._build_effect(subject, data)
        if coro:
            self._current_task = asyncio.create_task(coro)

    # ------------------------------------------------------------------
    def _build_effect(self, subject: str, data: dict) -> Coroutine | None:
        led = self._led

        if subject == "system.started":
            return effects.breathing(led, COLOR_BLUE, speed=0.5)

        if subject == "wake_word.detected":
            async def _wake():
                await effects.flash(led, COLOR_WHITE, times=2, duration=0.15)
                await effects.fade_to(led, (0, 0, 255), COLOR_GREEN, duration=0.3)
                await effects.breathing(led, COLOR_GREEN, speed=1.0)
            return _wake()

        if subject == "speaker.verified":
            self._last_idle_color = COLOR_GREEN
            return effects.solid(led, COLOR_GREEN)

        if subject == "speaker.rejected":
            async def _rejected():
                await effects.blink(led, COLOR_RED, times=2)
                await effects.breathing(led, COLOR_BLUE, speed=0.5)
            return _rejected()

        if subject == "conversation.started":
            self._last_idle_color = COLOR_GREEN
            return effects.breathing(led, COLOR_GREEN, speed=1.0)

        if subject == "brain.processing":
            return effects.spinner(led, (255, 200, 0))

        if subject == "tts.speaking_started":
            context = data.get("context", "normal")
            color = CONTEXT_COLORS.get(context, COLOR_GREEN)
            self._audio_sync.set_base_color(color)
            self._audio_sync.activate()
            return effects.hold(led)  # audio_sync drives LEDs; we just hold priority

        if subject == "tts.speaking_stopped":
            self._audio_sync.deactivate()
            return effects.breathing(led, self._last_idle_color, speed=0.8)

        if subject == "conversation.ended":
            self._last_idle_color = COLOR_BLUE
            async def _ended():
                await effects.fade_to(led, COLOR_GREEN, COLOR_BLUE, duration=0.5)
                await effects.breathing(led, COLOR_BLUE, speed=0.5)
            return _ended()

        if subject.startswith("error."):
            return effects.blink(led, COLOR_PURPLE, times=3, on_ms=0.2, off_ms=0.2)

        if subject == "security.intrusion":
            return effects.strobe(led, COLOR_RED, interval=0.1)

        if subject == "system.shutdown":
            async def _shutdown():
                await effects.fade_to(led, self._last_idle_color, (0, 0, 0), duration=1.0)
            return _shutdown()

        return None

    # ------------------------------------------------------------------
    async def on_event(self, msg):
        subject = msg.subject
        try:
            data = json.loads(msg.data.decode()) if msg.data else {}
        except Exception:
            data = {}
        logger.info(f"← {subject}")
        await self.dispatch(subject, data)

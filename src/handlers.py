"""
Event handler — dispatches NATS events to LED effects.

Rule source priority:
  1. Hardcoded overrides: error.* / security.* (always win, prio 10)
  2. Dynamic rules from RuleRegistry (loaded from Redis db3)

TTS audio sync (ZeroMQ) is activated/deactivated via the special
"tts_audio_sync" effect name in a rule.
"""
import asyncio
import json
import logging
from typing import Coroutine

from src import effects as fx
from src.led import LEDController
from src.audio_sync import AudioSync
from src.registry import RuleRegistry

logger = logging.getLogger("visual-feedback.handlers")

# Subjects that are ALWAYS handled here regardless of registry
HARDCODED_OVERRIDES = {
    "error.*":            10,
    "security.intrusion": 10,
    "system.shutdown":     9,
}

COLOR_RED    = (255, 0, 0)
COLOR_PURPLE = (180, 0, 255)
COLOR_BLUE   = (0, 150, 255)


def _parse_color(value) -> tuple:
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return tuple(int(v) for v in value)
    return (0, 255, 0)


class EventHandler:
    def __init__(self, led: LEDController, audio_sync: AudioSync, registry: RuleRegistry):
        self._led = led
        self._audio_sync = audio_sync
        self._registry = registry
        self._current_task: asyncio.Task | None = None
        self._current_priority: int = 0
        self._last_idle_color: tuple = COLOR_BLUE

    # ------------------------------------------------------------------
    def _hardcoded_priority(self, subject: str) -> int | None:
        if subject.startswith("error."):
            return 10
        return HARDCODED_OVERRIDES.get(subject)

    # ------------------------------------------------------------------
    async def dispatch(self, subject: str, data: dict):
        hw_prio = self._hardcoded_priority(subject)

        if hw_prio is not None:
            priority = hw_prio
        else:
            rule = self._registry.get(subject)
            priority = rule.get("priority", 1) if rule else 0

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
        coro = self._build_effect(subject, data, hw_prio)
        if coro:
            self._current_task = asyncio.create_task(coro)

    # ------------------------------------------------------------------
    def _build_effect(self, subject: str, data: dict, hw_prio: int | None) -> Coroutine | None:
        led = self._led

        # ── Hardcoded overrides ─────────────────────────────────────────
        if subject.startswith("error."):
            return fx.blink(led, COLOR_PURPLE, times=3, on_ms=0.2, off_ms=0.2)

        if subject == "security.intrusion":
            return fx.strobe(led, COLOR_RED, interval=0.1)

        if subject == "system.shutdown":
            async def _shutdown():
                await fx.fade_to(led, self._last_idle_color, (0, 0, 0), duration=1.0)
            return _shutdown()

        # ── Dynamic rules from registry ─────────────────────────────────
        rule = self._registry.get(subject)
        if not rule:
            logger.debug(f"No rule for subject: {subject}")
            return None

        return self._effect_from_rule(rule, data)

    # ------------------------------------------------------------------
    def _effect_from_rule(self, rule: dict, data: dict) -> Coroutine | None:
        led = self._led
        effect_name = rule.get("effect", "solid")
        color = _parse_color(rule.get("color", [0, 255, 0]))
        params = dict(rule.get("params", {}))
        then_rule = rule.get("then")

        # Special effect: activate ZeroMQ audio sync
        if effect_name == "tts_audio_sync":
            context_colors: dict = rule.get("context_colors", {})

            async def _tts_sync():
                context = data.get("context", "normal")
                base_color = _parse_color(context_colors.get(context, list(color)))
                self._audio_sync.set_base_color(base_color)
                self._audio_sync.activate()
                await fx.hold(led)

            return _tts_sync()

        # Special effect: deactivate ZeroMQ audio sync
        if effect_name == "tts_audio_sync_stop":
            async def _tts_stop():
                self._audio_sync.deactivate()
                if then_rule:
                    coro = self._effect_from_rule(then_rule, data)
                    if coro:
                        await coro
                else:
                    await fx.breathing(led, self._last_idle_color, speed=0.8)
            return _tts_stop()

        async def _run():
            if effect_name == "solid":
                self._last_idle_color = color
                await fx.solid(led, color)

            elif effect_name == "breathing":
                self._last_idle_color = color
                await fx.breathing(led, color, **params)

            elif effect_name == "spinner":
                await fx.spinner(led, color, **params)

            elif effect_name == "strobe":
                await fx.strobe(led, color, **params)

            elif effect_name == "flash":
                await fx.flash(led, color, **params)
                if then_rule:
                    coro = self._effect_from_rule(then_rule, data)
                    if coro:
                        await coro

            elif effect_name == "blink":
                await fx.blink(led, color, **params)
                if then_rule:
                    coro = self._effect_from_rule(then_rule, data)
                    if coro:
                        await coro

            elif effect_name == "fade_to":
                color_to = _parse_color(params.pop("color_to", list(color)))
                await fx.fade_to(led, color, color_to, **params)
                if then_rule:
                    coro = self._effect_from_rule(then_rule, data)
                    if coro:
                        await coro

            else:
                logger.warning(f"Unknown effect: {effect_name}")

        return _run()

    # ------------------------------------------------------------------
    async def on_event(self, msg):
        subject = msg.subject
        try:
            data = json.loads(msg.data.decode()) if msg.data else {}
        except Exception:
            data = {}
        logger.info(f"← {subject}")
        await self.dispatch(subject, data)

    async def on_register(self, msg):
        """Handles visual.register — a service publishes its visual rules."""
        try:
            payload = json.loads(msg.data.decode())
            service = payload.get("service", "unknown")
            rules = payload.get("rules", [])
            await self._registry.register_service(service, rules)
            logger.info(f"Rules registered for service '{service}' ({len(rules)} rules)")
        except Exception as e:
            logger.error(f"Failed to process visual.register: {e}")

import asyncio
import logging

import nats

from src.config import config
from src.led import LEDController
from src.audio_sync import AudioSync
from src.registry import RuleRegistry
from src.handlers import EventHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("visual-feedback")

# Hardcoded subjects that bypass the registry (always subscribed)
HARDCODED_SUBJECTS = [
    "mordomo.error.>",
    "mordomo.security.intrusion",
    "mordomo.system.shutdown",
]


async def main():
    # ── Hardware ───────────────────────────────────────────────────────
    led = LEDController(config)
    await led.start()

    audio_sync = AudioSync(config, led)

    # ── Registry (Redis db3) ───────────────────────────────────────────
    registry = RuleRegistry(config.redis_url)
    await registry.connect()
    await registry.load_all()

    handler = EventHandler(led, audio_sync, registry)

    # ── NATS ───────────────────────────────────────────────────────────
    nc = await nats.connect(
        config.nats_url,
        error_cb=lambda e: logger.error(f"NATS error: {e}"),
        reconnected_cb=lambda: logger.warning("NATS reconnected"),
        disconnected_cb=lambda: logger.warning("NATS disconnected"),
    )
    logger.info(f"Connected to NATS: {config.nats_url}")

    # Subscribe to hardcoded overrides
    for subject in HARDCODED_SUBJECTS:
        await nc.subscribe(subject, cb=handler.on_event)

    # Subscribe to all subjects currently registered in Redis
    for subject in registry.all_subjects():
        await nc.subscribe(subject, cb=handler.on_event)
        logger.info(f"Subscribed (registry): {subject}")

    # Listen for new service registrations at runtime
    async def _on_register(msg):
        prev_subjects = set(registry.all_subjects())
        await handler.on_register(msg)
        new_subjects = set(registry.all_subjects()) - prev_subjects
        for subject in new_subjects:
            await nc.subscribe(subject, cb=handler.on_event)
            logger.info(f"Subscribed (new registration): {subject}")

    await nc.subscribe("visual.register", cb=_on_register)
    logger.info("Listening for visual.register from services")

    logger.info("Visual feedback service running.")

    try:
        await asyncio.Future()  # run forever
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        audio_sync.deactivate()
        await nc.drain()
        await registry.close()
        led.clear()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())

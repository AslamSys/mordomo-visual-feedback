import asyncio
import logging

import nats

from src.config import config
from src.led import LEDController
from src.audio_sync import AudioSync
from src.handlers import EventHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("visual-feedback")

SUBSCRIPTIONS = [
    "system.started",
    "system.shutdown",
    "wake_word.detected",
    "speaker.verified",
    "speaker.rejected",
    "conversation.started",
    "conversation.ended",
    "brain.processing",
    "tts.speaking_started",
    "tts.speaking_stopped",
    "error.>",
    "security.intrusion",
]


async def main():
    led = LEDController(config)
    await led.start()

    audio_sync = AudioSync(config, led)
    handler = EventHandler(led, audio_sync)

    nc = await nats.connect(
        config.nats_url,
        error_cb=lambda e: logger.error(f"NATS error: {e}"),
        reconnected_cb=lambda: logger.warning("NATS reconnected"),
        disconnected_cb=lambda: logger.warning("NATS disconnected"),
    )
    logger.info(f"Connected to NATS: {config.nats_url}")

    for subject in SUBSCRIPTIONS:
        await nc.subscribe(subject, cb=handler.on_event)

    # Boot animation
    await handler.dispatch("system.started", {})

    logger.info("Visual feedback service running.")

    try:
        await asyncio.Future()  # run forever
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        audio_sync.deactivate()
        await nc.drain()
        led.clear()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())

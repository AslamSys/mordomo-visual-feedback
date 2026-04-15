"""
Audio sync — subscribes to ZeroMQ TTS audio stream and pulses
LED brightness in sync with speech amplitude.
"""
import asyncio
import logging

import numpy as np
import zmq
import zmq.asyncio

logger = logging.getLogger("visual-feedback.audio_sync")


class AudioSync:
    def __init__(self, config, led):
        self._config = config
        self._led = led
        self._active = False
        self._base_color: tuple = (0, 255, 0)
        self._task: asyncio.Task | None = None

    def set_base_color(self, color: tuple):
        self._base_color = color

    def activate(self):
        if self._active:
            return
        self._active = True
        self._task = asyncio.create_task(self._run())
        logger.info("Audio sync activated")

    def deactivate(self):
        if not self._active:
            return
        self._active = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Audio sync deactivated")

    async def _run(self):
        ctx = zmq.asyncio.Context.instance()
        sock = ctx.socket(zmq.SUB)
        sock.connect(self._config.zmq_tts_url)
        sock.setsockopt_string(zmq.SUBSCRIBE, "audio.output")
        logger.info(f"ZeroMQ SUB connected to {self._config.zmq_tts_url}")

        try:
            while self._active:
                try:
                    # Multipart: [topic, payload]
                    parts = await asyncio.wait_for(sock.recv_multipart(), timeout=0.5)
                    if len(parts) < 2:
                        continue
                    audio_bytes = parts[1]

                    samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
                    if len(samples) == 0:
                        continue

                    rms = float(np.sqrt(np.mean(samples ** 2)))
                    amplitude = min(rms / self._config.rms_threshold, 1.0)
                    brightness = int(50 + amplitude * 205)  # 50 – 255

                    r, g, b = self._base_color
                    color = (
                        int(r * brightness / 255),
                        int(g * brightness / 255),
                        int(b * brightness / 255),
                    )
                    for i in range(self._led.count):
                        self._led.set_pixel(i, color)
                    self._led.show()

                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            pass
        finally:
            sock.close()

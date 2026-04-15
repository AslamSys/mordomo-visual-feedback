import os


class Config:
    nats_url: str = os.getenv("NATS_URL", "nats://nats:4222")
    zmq_tts_url: str = os.getenv("ZMQ_TTS_URL", "tcp://tts-engine:5556")
    led_count: int = int(os.getenv("LED_COUNT", "16"))
    led_pin: int = int(os.getenv("LED_PIN", "18"))          # GPIO18 = PWM0
    led_freq_hz: int = int(os.getenv("LED_FREQ_HZ", "800000"))
    led_dma: int = int(os.getenv("LED_DMA", "10"))
    led_brightness: int = int(os.getenv("LED_BRIGHTNESS", "200"))  # 0-255
    led_invert: bool = os.getenv("LED_INVERT", "false").lower() == "true"
    led_channel: int = int(os.getenv("LED_CHANNEL", "0"))
    rms_threshold: float = float(os.getenv("RMS_THRESHOLD", "3000.0"))


config = Config()

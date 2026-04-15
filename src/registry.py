"""
Rule Registry — persists and loads visual rules from Redis db3.

Schema per service:
  Key:   vfb:rules:{service_name}
  Type:  Hash  { subject -> JSON-encoded rule }

Rule JSON format:
{
    "subject":  "wake_word.detected",   # NATS subject (exact or prefix with *)
    "priority": 5,
    "effect":   "flash",                # effect name (see effects.py)
    "color":    [255, 255, 255],        # RGB
    "params":   {"times": 2},           # extra kwargs forwarded to the effect
    "then": {                           # optional: looping effect after one-shot
        "effect": "breathing",
        "color":  [0, 255, 0]
    }
}
"""
import json
import logging
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger("visual-feedback.registry")

REDIS_KEY_PREFIX = "vfb:rules:"


class RuleRegistry:
    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._client: Optional[aioredis.Redis] = None
        # subject -> rule dict (in-memory cache rebuilt on load/update)
        self._rules: dict[str, dict] = {}

    # ------------------------------------------------------------------
    async def connect(self):
        self._client = aioredis.from_url(
            self._redis_url,
            decode_responses=True,
        )
        await self._client.ping()
        logger.info(f"Registry connected to Redis: {self._redis_url}")

    async def close(self):
        if self._client:
            await self._client.aclose()

    # ------------------------------------------------------------------
    async def load_all(self):
        """Load all service rules from Redis into memory."""
        if not self._client:
            return

        self._rules.clear()
        cursor = 0
        pattern = f"{REDIS_KEY_PREFIX}*"

        while True:
            cursor, keys = await self._client.scan(cursor, match=pattern, count=100)
            for key in keys:
                raw = await self._client.hgetall(key)
                service = key[len(REDIS_KEY_PREFIX):]
                for subject, rule_json in raw.items():
                    try:
                        rule = json.loads(rule_json)
                        self._rules[subject] = rule
                        logger.debug(f"Loaded rule [{service}] {subject}")
                    except Exception as e:
                        logger.warning(f"Bad rule [{service}] {subject}: {e}")
            if cursor == 0:
                break

        logger.info(f"Registry loaded {len(self._rules)} rules from Redis")

    # ------------------------------------------------------------------
    async def register_service(self, service: str, rules: list[dict]):
        """Called when a service publishes to visual.register."""
        if not self._client:
            return

        key = f"{REDIS_KEY_PREFIX}{service}"
        mapping = {r["subject"]: json.dumps(r) for r in rules if "subject" in r}

        if mapping:
            # Replace all rules for this service atomically
            await self._client.delete(key)
            await self._client.hset(key, mapping=mapping)
            # Update in-memory cache
            self._rules.update({subj: json.loads(v) for subj, v in mapping.items()})
            logger.info(f"Registered {len(mapping)} rules for service '{service}'")

    # ------------------------------------------------------------------
    def get(self, subject: str) -> Optional[dict]:
        """Exact-match lookup, then prefix wildcard match."""
        rule = self._rules.get(subject)
        if rule:
            return rule
        # Support wildcard prefix: "error.*" matches "error.nats"
        for pattern, r in self._rules.items():
            if pattern.endswith("*") and subject.startswith(pattern[:-1]):
                return r
        return None

    def all_subjects(self) -> list[str]:
        return list(self._rules.keys())

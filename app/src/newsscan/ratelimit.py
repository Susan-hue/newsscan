"""Rate limit for uploads (ADR-013): at most N scans per minute and per day for each visitor.

Counts live in Redis, so they survive a restart and stay right with more than one API container.
Each count belongs to a fixed time window (the key includes the window number), so old counts simply expire.
Raw addresses are never stored: the key holds a short hash.
"""

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import redis

from newsscan.config import Settings

MINUTE = 60
DAY = 86_400


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    window: str = ""  # "minute" or "day", only set when blocked
    retry_after: int = 0  # seconds until the blocking window ends


class RateLimiter(Protocol):
    def check(self, visitor: str) -> RateDecision: ...


class CounterStore(Protocol):
    def incr(self, key: str, ttl: int) -> int: ...


class MemoryStore:
    """Counts in memory. For tests and for running without Redis; it forgets everything on restart."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def incr(self, key: str, ttl: int) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]


class RedisStore:
    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    def incr(self, key: str, ttl: int) -> int:
        pipe = self._client.pipeline()  # one round trip, and the count and its expiry go together
        pipe.incr(key)
        pipe.expire(key, ttl)
        return int(pipe.execute()[0])


class AllowAllLimiter:
    def check(self, visitor: str) -> RateDecision:
        return RateDecision(allowed=True)


class FixedWindowLimiter:
    def __init__(
        self,
        store: CounterStore,
        per_minute: int,
        per_day: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._store = store
        self._windows = (("minute", MINUTE, per_minute), ("day", DAY, per_day))
        self._clock = clock

    def check(self, visitor: str) -> RateDecision:
        now = int(self._clock())
        who = hashlib.sha256(visitor.encode()).hexdigest()[:16]
        for name, size, limit in self._windows:
            if limit <= 0:  # 0 switches this window off
                continue
            index = now // size
            count = self._store.incr(f"ratelimit:{name}:{who}:{index}", size + 1)
            if count > limit:
                # Stop here: a request blocked by the minute limit must not use up the day budget.
                return RateDecision(False, name, (index + 1) * size - now)
        return RateDecision(allowed=True)


def build_rate_limiter(settings: Settings) -> RateLimiter:
    if settings.rate_limit_per_minute <= 0 and settings.rate_limit_per_day <= 0:
        return AllowAllLimiter()
    client = redis.Redis.from_url(settings.redis_url, socket_timeout=1, socket_connect_timeout=1)
    return FixedWindowLimiter(RedisStore(client), settings.rate_limit_per_minute, settings.rate_limit_per_day)

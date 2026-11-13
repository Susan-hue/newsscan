import pytest
from prometheus_client import generate_latest

from newsscan.config import Settings
from newsscan.ratelimit import (
    AllowAllLimiter,
    FixedWindowLimiter,
    MemoryStore,
    build_rate_limiter,
)
from tests.conftest import make_image


class Clock:
    def __init__(self, now: float = 1_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def limiter(per_minute=3, per_day=5, clock=None, store=None):
    return FixedWindowLimiter(store or MemoryStore(), per_minute, per_day, clock=clock or Clock())


def test_allows_up_to_the_minute_limit_then_blocks_with_a_wait_time():
    clock = Clock(now=1_000_020.0)  # 20 seconds into a minute window
    rl = limiter(per_minute=3, per_day=100, clock=clock)
    assert all(rl.check("1.2.3.4").allowed for _ in range(3))
    blocked = rl.check("1.2.3.4")
    assert not blocked.allowed and blocked.window == "minute"
    assert 0 < blocked.retry_after <= 60


def test_the_next_minute_starts_fresh():
    clock = Clock()
    rl = limiter(per_minute=1, per_day=100, clock=clock)
    assert rl.check("v").allowed and not rl.check("v").allowed
    clock.now += 61
    assert rl.check("v").allowed


def test_the_day_limit_applies_across_minutes():
    clock = Clock()
    rl = limiter(per_minute=100, per_day=2, clock=clock)
    assert rl.check("v").allowed
    clock.now += 120
    assert rl.check("v").allowed
    clock.now += 120
    blocked = rl.check("v")
    assert not blocked.allowed and blocked.window == "day"
    assert blocked.retry_after > 60


def test_a_blocked_minute_does_not_use_up_the_day_budget():
    clock = Clock()
    rl = limiter(per_minute=1, per_day=3, clock=clock)
    rl.check("v")
    for _ in range(10):
        assert not rl.check("v").allowed  # hammering inside the minute
    clock.now += 61
    assert rl.check("v").allowed  # still has day budget left


def test_visitors_are_counted_separately():
    rl = limiter(per_minute=1, per_day=10)
    assert rl.check("a").allowed and rl.check("b").allowed
    assert not rl.check("a").allowed


def test_a_zero_limit_switches_that_window_off():
    rl = limiter(per_minute=0, per_day=0)
    assert all(rl.check("v").allowed for _ in range(50))


def test_raw_addresses_are_not_stored():
    store = MemoryStore()
    limiter(store=store).check("203.0.113.7")
    assert store.counts and all("203.0.113.7" not in key for key in store.counts)


def test_build_uses_allow_all_when_both_limits_are_off():
    assert isinstance(
        build_rate_limiter(Settings(_env_file=None, rate_limit_per_minute=0, rate_limit_per_day=0)),
        AllowAllLimiter,
    )
    assert isinstance(build_rate_limiter(Settings(_env_file=None)), FixedWindowLimiter)


def test_the_defaults_are_ten_per_minute_and_a_hundred_per_day():
    settings = Settings(_env_file=None)
    assert (settings.rate_limit_per_minute, settings.rate_limit_per_day) == (10, 100)


# --- through the real API ---


def upload(client):
    return client.post("/v1/scans", files={"file": ("page.png", make_image(), "image/png")})


def test_the_api_answers_429_with_retry_after_and_counts_it(client):
    client.app.state.rate_limiter = limiter(per_minute=2, per_day=100)
    assert upload(client).status_code == 202
    assert upload(client).status_code == 202
    response = upload(client)
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0
    assert "Too many scans" in response.json()["detail"]
    assert 'newsscan_rate_limited_total{window="minute"}' in generate_latest().decode()


def test_only_uploads_are_limited(client):
    client.app.state.rate_limiter = limiter(per_minute=1, per_day=1)
    assert upload(client).status_code == 202
    assert upload(client).status_code == 429
    assert client.get("/healthz").status_code == 200
    assert client.get("/").status_code == 200


class BrokenLimiter:
    def check(self, visitor):
        raise ConnectionError("redis is down")


def test_if_the_limiter_breaks_uploads_still_work(client):
    client.app.state.rate_limiter = BrokenLimiter()
    assert upload(client).status_code == 202


@pytest.mark.parametrize("window", ["minute", "day"])
def test_rate_limit_counters_start_at_zero(window):
    assert f'newsscan_rate_limited_total{{window="{window}"}}' in generate_latest().decode()

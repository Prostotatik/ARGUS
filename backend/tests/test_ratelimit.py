import asyncio
import time

import pytest

from sdoc import ratelimit as rl


def test_every_known_model_clamps_to_at_least_one():
    """A model whose real dashboard limit is 0 (not available on this account's tier - several
    are, see hackathon_info/google-ai-limits.md) must not make the limiter divide against an
    always-empty window; every axis clamps to >= 1 so acquire() can always eventually proceed and
    the real API call (not this client-side limiter) is what surfaces "not available"."""
    for model in list(rl._MODEL_LIMITS) + ["a-model-not-in-the-table"]:
        r, t, d = rl.limits_for(model)
        assert r >= 1 and t >= 1 and d >= 1, (model, r, t, d)


def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("SDOC_GEMINI_RPM", "7")
    monkeypatch.setenv("SDOC_GEMINI_TPM", "1234")
    monkeypatch.setenv("SDOC_GEMINI_RPD", "9")
    r, t, d = rl.limits_for("gemini-3.5-flash-lite")
    assert (r, t, d) == (7, 1234, 9)


def test_rpm_ceiling_makes_the_next_call_wait():
    """A limiter with RPM=2 lets 2 calls through immediately, then the 3rd call must actually
    sleep (proving acquire() throttles instead of just bookkeeping)."""

    async def run():
        limiter = rl.RateLimiter(model="test-only")
        limiter.rpm, limiter.tpm, limiter.rpd = 2, 10_000, 1000
        t0 = time.monotonic()
        await limiter.acquire(10)
        await limiter.acquire(10)
        assert time.monotonic() - t0 < 0.5  # first two are instant

        task = asyncio.create_task(limiter.acquire(10))
        await asyncio.sleep(0.2)
        assert not task.done(), "3rd call within the same RPM window should still be waiting"
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())


def test_estimate_tokens_is_positive_and_monotonic():
    assert rl.estimate_tokens("") >= 1
    assert rl.estimate_tokens("a" * 400) > rl.estimate_tokens("a" * 4)

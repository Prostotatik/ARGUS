"""Pre-emptive client-side rate limiting for the Gemini API.

Numbers default to the per-model RPM/TPM/RPD ceilings in `hackathon_info/google-ai-limits.md`
(gemini-2.5-flash: 1,000 RPM / 1,000,000 TPM / 10,000 RPD). A `RateLimiter` is shared by every call
one `GeminiClient` makes (classifier + all 7 field agents in a run), and it BLOCKS (sleeps) a caller
until a call is safely under all three ceilings - it never raises, so the account's limit is a
non-event from the pipeline's point of view instead of a 429 the reactive backoff in `llm.py` then
has to absorb. That reactive backoff stays in place as a second line of defense (limits can differ
per API key/tier, and this token estimate is a heuristic, not the server's own accounting).

Override per-model or per-account with `SDOC_GEMINI_RPM` / `SDOC_GEMINI_TPM` / `SDOC_GEMINI_RPD`.
"""
from __future__ import annotations

import asyncio
import os
import time
from collections import deque

from . import config

# model -> (requests/minute, tokens/minute, requests/day). Sourced from this project's own account
# dashboard (hackathon_info/google-ai-limits.md) - a FREE-TIER project, and confirmed the hard way:
# gemini-3.6-flash's real ceiling (RPM 5 / RPD 20) was blown through by two single-email smoke
# tests before this table was corrected from an earlier, much more generous (wrong) reading of the
# same dashboard. Free-tier allocations are account-specific and can change - re-check the
# dashboard before trusting these numbers on a different key, and prefer the env overrides below
# for anything that drifts.
_MODEL_LIMITS: dict[str, tuple[int, int, int | None]] = {
    "gemini-2.5-flash": (5, 250_000, 20),
    "gemini-2.5-flash-lite": (10, 250_000, 20),
    "gemini-2.5-pro": (0, 0, 0),          # not available on this tier
    "gemini-2.0-flash": (0, 0, 0),        # not available on this tier
    "gemini-2.0-flash-lite": (0, 0, 0),   # not available on this tier
    "gemini-3-flash": (5, 250_000, 20),
    "gemini-3.1-pro": (0, 0, 0),          # not available on this tier
    "gemini-3.1-flash-lite": (15, 250_000, 500),   # best RPM/RPD on this tier, alongside 3.5-flash-lite
    "gemini-3.5-flash": (5, 250_000, 20),
    "gemini-3.5-flash-lite": (15, 250_000, 500),   # default model - verified live, see backend/README.md
    "gemini-3.6-flash": (5, 250_000, 20),
    "gemini-3.7-flash": (5, 250_000, 20),
    "gemini-3.8-flash": (5, 250_000, 20),
}
# Conservative fallback for any model not in the table above - matches the smallest real ceiling
# seen on this tier (most non-lite text-out models), never the generous numbers Google's own
# marketing/docs pages advertise for a paid tier.
_DEFAULT_LIMITS: tuple[int, int, int | None] = (5, 200_000, 20)
_UNLIMITED_RPD = 10**9  # "no published daily ceiling" - don't actually block on this axis


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def limits_for(model: str) -> tuple[int, int, int]:
    """(rpm, tpm, rpd) for `model`, env overrides applied last. Clamped to >= 1 on every axis: a
    real 0 (model not available on this tier) would make the sliding-window math divide against an
    always-empty window and hang forever - let the real API call surface that as its own error
    instead (the pipeline already falls back to `rules` on any Gemini failure)."""
    rpm, tpm, rpd = _MODEL_LIMITS.get(model, _DEFAULT_LIMITS)
    rpd = rpd if rpd is not None else _UNLIMITED_RPD
    return (
        max(1, _env_int("SDOC_GEMINI_RPM", rpm)),
        max(1, _env_int("SDOC_GEMINI_TPM", tpm)),
        max(1, _env_int("SDOC_GEMINI_RPD", rpd)),
    )


def estimate_tokens(text: str) -> int:
    """Rough chars/4 heuristic. Good enough to stay well clear of a TPM ceiling; not a token count
    the API would bill on, and deliberately rounds up (worst case: we throttle slightly early)."""
    return max(1, len(text) // 4 + 1)


class RateLimiter:
    """Sliding-window limiter across all three axes. `acquire()` reserves capacity for one call of
    `tokens` size, sleeping in short slices until all three windows have room, then reserves
    immediately (no gap between "checked" and "spent") so concurrent callers can't both slip through."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or config.gemini_model()
        self.rpm, self.tpm, self.rpd = limits_for(self.model)
        self._req_times: deque[float] = deque()
        self._tok_events: deque[tuple[float, int]] = deque()
        self._day_times: deque[float] = deque()
        self._lock = asyncio.Lock()

    def _trim(self, now: float) -> None:
        while self._req_times and now - self._req_times[0] >= 60:
            self._req_times.popleft()
        while self._tok_events and now - self._tok_events[0][0] >= 60:
            self._tok_events.popleft()
        while self._day_times and now - self._day_times[0] >= 86400:
            self._day_times.popleft()

    def _wait_needed(self, now: float, tokens: int) -> float:
        waits = [0.0]
        if len(self._req_times) >= self.rpm:
            waits.append(60.0 - (now - self._req_times[0]) + 0.05)
        used = sum(t for _, t in self._tok_events)
        if self._tok_events and used + tokens > self.tpm:
            waits.append(60.0 - (now - self._tok_events[0][0]) + 0.05)
        if len(self._day_times) >= self.rpd:
            waits.append(86400.0 - (now - self._day_times[0]) + 0.5)
        return max(waits)

    async def acquire(self, tokens: int) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self._trim(now)
                wait = self._wait_needed(now, tokens)
                if wait <= 0:
                    self._req_times.append(now)
                    self._tok_events.append((now, tokens))
                    self._day_times.append(now)
                    return
            await asyncio.sleep(min(wait, 5.0))  # re-check periodically; lock released while sleeping

    def snapshot(self) -> dict:
        """For diagnostics/health, not a hot path."""
        now = time.monotonic()
        self._trim(now)
        return {
            "model": self.model,
            "requests_per_min": {"used": len(self._req_times), "limit": self.rpm},
            "tokens_per_min": {"used": sum(t for _, t in self._tok_events), "limit": self.tpm},
            "requests_per_day": {"used": len(self._day_times), "limit": self.rpd if self.rpd < _UNLIMITED_RPD else None},
        }

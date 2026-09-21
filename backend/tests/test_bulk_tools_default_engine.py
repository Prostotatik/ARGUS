"""Regression test for a real bug hit during development: `run_all` and `export_replay` are BULK
tools that walk all 520 emails, and their `--engine` flag used to default to `None`, which
`config.default_engine()` resolves to `"gemini"` the moment a `GEMINI_API_KEY` is configured
(e.g. in `backend/.env`) - silently sending a full 520-email x up to 8-calls-each run at a live
key's daily quota instead of the fast, deterministic, reproducible baseline these tools exist to
produce. Both now default their `--engine` flag to `"rules"` explicitly; a key only gets exercised
across the whole dataset if `--engine gemini` is passed on purpose.
"""
from __future__ import annotations

import inspect
import re


def _engine_default(module) -> str:
    """Parse the literal `default=...` for the `--engine` add_argument call out of main()'s
    source, so this test breaks loudly if a future edit removes the safe default - without
    actually invoking main() (which would process the whole 520-email dataset)."""
    src = inspect.getsource(module.main)
    m = re.search(r'add_argument\(\s*"--engine".*?default=("?\w+"?)', src, re.S)
    assert m, f"{module.__name__}: could not find --engine's default in main()'s source"
    return m.group(1).strip('"')


def test_run_all_defaults_to_rules_even_with_a_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-present")
    import sdoc.run_all as run_all
    assert _engine_default(run_all) == "rules", (
        "run_all.py's --engine must default to 'rules' - a bulk 520-email run must never silently "
        "default onto a live key just because one is configured"
    )


def test_export_replay_defaults_to_rules_even_with_a_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-present")
    import sdoc.export_replay as export_replay
    assert _engine_default(export_replay) == "rules", (
        "export_replay.py's --engine must default to 'rules' - REPLAY is meant to work with no "
        "backend/key at all, and building it must not burn a configured key's daily quota"
    )

"""Paths, env loading and engine selection."""
from __future__ import annotations

import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
BACKEND_DIR = PKG_DIR.parent
ROOT_DIR = BACKEND_DIR.parent
OUT_DIR = Path(os.environ.get("SDOC_OUT_DIR", BACKEND_DIR / "out"))
REPLAY_DIR = ROOT_DIR / "frontend" / "public" / "replay"

FIELDS = [
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
]
CATEGORIES = ["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"]
REVIEW_REASONS = ["wrong_doc_type", "missing_attachment", "unreadable", "missing_value"]


def _load_dotenv() -> None:
    """Minimal .env loader (no python-dotenv dependency). Never overrides real env vars."""
    for p in (BACKEND_DIR / ".env", ROOT_DIR / ".env"):
        try:
            if not p.is_file():
                continue
            for raw in p.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
        except OSError:
            pass


_load_dotenv()


def data_dir() -> Path:
    env = os.environ.get("SDOC_DATA_DIR")
    if env:
        return Path(env)
    return ROOT_DIR / "work" / "bundle"


def gemini_key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or None


def gemini_model() -> str:
    return os.environ.get("SDOC_GEMINI_MODEL", "gemini-2.5-flash")


def gemini_concurrency() -> int:
    """Max concurrent in-flight Gemini calls (classifier + 7 field agents = up to 8 per email).
    Free-tier flash-class models allow only a small number of requests/minute; keeping this low
    avoids firing all 8 calls of one email at once and tripping 429s (reviews/judge.md #6)."""
    try:
        return max(1, int(os.environ.get("SDOC_GEMINI_CONCURRENCY", "3")))
    except ValueError:
        return 3


def gemini_max_attempts() -> int:
    try:
        return max(1, int(os.environ.get("SDOC_GEMINI_MAX_ATTEMPTS", "4")))
    except ValueError:
        return 4


def default_engine() -> str:
    """'gemini' iff a key exists (and SDOC_ENGINE does not force rules), else 'rules'."""
    forced = os.environ.get("SDOC_ENGINE")
    if forced in ("rules", "gemini"):
        return forced if (forced == "rules" or gemini_key()) else "rules"
    return "gemini" if gemini_key() else "rules"

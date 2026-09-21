"""Inbox access: reads the participant bundle layout (inbox/*.json + attachments/*)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config


class Inbox:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else config.data_dir()
        self._emails: dict[str, dict] | None = None

    def _load(self) -> dict[str, dict]:
        if self._emails is None:
            d = self.root / "inbox"
            emails: dict[str, dict] = {}
            for p in sorted(d.glob("*.json")):
                rec = json.loads(p.read_text(encoding="utf-8"))
                emails[rec["email_id"]] = rec
            self._emails = emails
        return self._emails

    def emails(self) -> list[dict]:
        return list(self._load().values())

    def ids(self) -> list[str]:
        return list(self._load().keys())

    def get(self, email_id: str) -> dict | None:
        return self._load().get(email_id)

    def __len__(self) -> int:
        return len(self._load())

    def attachment_path(self, rel: str) -> Path:
        return self.root / rel

    @staticmethod
    def received_at(email_id: str) -> str:
        """The dataset carries no timestamps. For the UI we simulate a steady inbox arrival stream
        (deterministic, derived from the numeric id only). Marked as simulated in the API docs."""
        try:
            n = int("".join(ch for ch in email_id if ch.isdigit()))
        except ValueError:
            n = 0
        t = datetime(2026, 1, 5, 7, 30, tzinfo=timezone.utc) + timedelta(minutes=7 * n)
        return t.strftime("%Y-%m-%dT%H:%M:%SZ")

    def summary(self, email_id: str) -> dict:
        e = self._load()[email_id]
        return {
            "email_id": email_id,
            "from": e.get("from", ""),
            "subject": e.get("subject", ""),
            "received_at": self.received_at(email_id),
            "has_attachments": bool(e.get("attachments")),
        }

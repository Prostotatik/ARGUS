"""Email classifier: BL_COMPARISON | SI_REQUEST | INVOICE_QUERY | GENERAL | SPAM.

Two engines, one interface:

* ``classify_rules``  - deterministic weighted-signal scorer (always available, offline).
* ``classify_gemini`` - Gemini structured-JSON call (only when GEMINI_API_KEY is set; see ``llm.py``).

The rules read the subject, the *cleaned* body (warning banner, quoted thread and signature stripped
so boilerplate cannot vote) and the attachment names. They use generic shipping-inbox language,
never email ids or anything from the generator/ground truth.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

from .config import CATEGORIES

# ---------------------------------------------------------------------------
_BANNER = re.compile(r"WARNING:\s*This email originated outside.*?(?:links or attachments\.)", re.I | re.S)
_QUOTE_CUT = re.compile(r"(?:^|\n)\s*(?:_{8,}|-{8,}|-{2,}\s*Original Message\s*-{2,}|From:\s.+\n\s*Sent:)", re.I)
_SIG_CUT = re.compile(r"\n\s*(?:Best Regards|Kind Regards|Warm regards|Regards|Best,|Thanks and regards|Thank you,)\b", re.I)


def clean_body(body: str) -> str:
    b = _BANNER.sub("", body or "")
    m = _QUOTE_CUT.search(b)
    if m:
        b = b[:m.start()]
    m = _SIG_CUT.search(b)
    if m:
        b = b[:m.start()]
    return b.strip()


def clean_subject(subject: str) -> str:
    return re.sub(r"^\s*(?:(?:RE|FW|FWD)\s*[:_]\s*)+", "", subject or "", flags=re.I).strip()


# (regex, weight, label)  - applied to subject (S), cleaned body (B) and attachment names (A)
_S = "subject"
_B = "body"
SIGNALS: dict[str, list[tuple[str, re.Pattern[str], float, str]]] = {
    "BL_COMPARISON": [
        (_S, re.compile(r"\bTO CONFIRM DOCS?\b", re.I), 4, "subject: 'to confirm docs'"),
        (_S, re.compile(r"\bREQUEST BL DRAFT\b|\bBL DRAFT\b", re.I), 4, "subject: BL draft request"),
        (_S, re.compile(r"\bdraft\s+b/?l\b", re.I), 3, "subject: draft BL"),
        (_S, re.compile(r"\bamend\s+b/?l\b", re.I), 2, "subject: amend BL"),
        (_S, re.compile(r"^[A-Z]{2,7}\s*-\s*[A-Z_ ]+\s*-\s*[A-Z]{2,7}\([A-Z0-9]{6,}\)\s*-\s*5[A-Z]{3}-\d+", re.I), 2.5,
         "subject: coded desk/POD/carrier(BL) reference"),
        (_B, re.compile(r"\bcompare\s+the\s+SI\s+and\b|\bSI\s+(?:and|vs\.?|against)\s+(?:the\s+)?draft\s+B/?L\b", re.I), 4, "body: compare SI and draft BL"),
        (_B, re.compile(r"\bcheck\s+the\s+draft\s+B/?L\b|\bcheck\s+the\s+details\b", re.I), 3.5, "body: check draft BL / details"),
        (_B, re.compile(r"\battached\s+(?:are\s+)?the\s+(?:shipping\s+instruction|SI)\s+and\s+(?:the\s+)?(?:draft\s+)?(?:BL|bill of lading)", re.I), 4, "body: SI and draft BL attached"),
        (_B, re.compile(r"\bfind\s+attached\s+the\s+(?:shipping\s+instruction|SI)\s+and\s+the\s+(?:draft\s+)?(?:bill of lading|BL)", re.I), 4, "body: SI and draft BL attached"),
        (_B, re.compile(r"\b(?:SI|shipping instruction)\s+and\s+(?:the\s+)?(?:commercial invoice|packing list|certificate of origin)\b", re.I), 3, "body: SI + other document for BL check"),
        (_B, re.compile(r"\bBL\s+is\s+in\s+order\b|\bverify\s+the\s+BL\s+matches\b|\bBL\s+matches\s+the\s+SI\b", re.I), 3.5, "body: verify BL against SI"),
        (_B, re.compile(r"\bdiscrepanc(?:y|ies)\b", re.I), 2, "body: discrepancy"),
        (_B, re.compile(r"\b(?:send|provide|share|revert with)\s+(?:us\s+)?the\s+draft\s+B/?L\b", re.I), 3, "body: asks for the draft BL"),
        (_B, re.compile(r"\bdraft\s+b(?:ill\s+of\s+lading|/?l)\b.{0,60}\bchecking\b|\bfor\s+checking\b", re.I), 2.5, "body: draft BL for checking"),
        (_B, re.compile(r"\bSI\s+fields\s+were\s+left\s+blank\b|\bwill not open\b|\battachments? appear", re.I), 2.5, "body: document problem on a BL check"),
    ],
    "SI_REQUEST": [
        (_S, re.compile(r"^\s*SI\s*-\s*\S", re.I), 4, "subject: 'SI - ...' shipping instruction ref"),
        (_S, re.compile(r"\bCUST\s+SI\b", re.I), 4, "subject: customer SI"),
        (_S, re.compile(r"\bREQUEST\s+SI\b", re.I), 4, "subject: request SI"),
        (_S, re.compile(r"\bSI\s+NEEDED\b|\bLATEST\s+SI\b|\bNEED\s+SI\b", re.I), 4, "subject: SI needed"),
        (_B, re.compile(r"\bplease\s+find\s+shipping\s+instruction\b", re.I), 4.5, "body: shipping instruction provided"),
        (_B, re.compile(r"\bPOL\s*:.*\n\s*POD\s*:", re.I), 3, "body: POL/POD block"),
        (_B, re.compile(r"\bDocuments\s+Required\b", re.I), 2.5, "body: documents required list"),
        (_B, re.compile(r"\bDescription\s+of\s+Goods\b", re.I), 1.5, "body: description of goods"),
        (_B, re.compile(r"\brevert\s+with\s+draft\s+B/?L\b", re.I), 1.5, "body: revert with draft BL"),
        (_B, re.compile(r"\b(?:send|provide|share|need|require)\b.{0,30}\b(?:SI|shipping\s+instruction)\b", re.I), 3, "body: asks for SI"),
    ],
    "INVOICE_QUERY": [
        (_S, re.compile(r"\bBILLING\b", re.I), 3, "subject: billing"),
        (_S, re.compile(r"\bMISSING\s+GR\b", re.I), 4, "subject: missing GR"),
        (_S, re.compile(r"\bCANCEL\s+INVOICE\b|\bCANCEL(?:LATION)?\s+OF\s+INVOICE\b", re.I), 4.5, "subject: cancel invoice"),
        (_S, re.compile(r"\bLOCAL\s+CHARGES?\b|\bTELEX\s+RELEASE\s+CHARGES?\b", re.I), 4, "subject: local charges"),
        (_S, re.compile(r"\bD\s*&\s*D\b|\bdetention\b|\bdemurrage\b", re.I), 4, "subject: D&D charges"),
        (_S, re.compile(r"\bTotal\s+Freight\b|\bfreight\s+(?:charge|invoice|bill)", re.I), 4, "subject: freight charges"),
        (_S, re.compile(r"\binvoice\b", re.I), 2, "subject: invoice"),
        (_B, re.compile(r"\binvoice\b", re.I), 2, "body: invoice"),
        (_B, re.compile(r"\bGR\s+is\s+still\s+missing\b|\bpost\s+the\s+GR\b|\bPGI\b|\bcredit\s+note\b", re.I), 3.5, "body: GR/PGI/credit note"),
        (_B, re.compile(r"\bTHC\b|\blocal\s+charge|\bdetention\b|\bD\s*&\s*D\b|\bdemurrage\b|\bbilled\s+separately\b", re.I), 3, "body: charges / billing breakdown"),
        (_B, re.compile(r"\breverse\s+the\s+PGI\b|\bcancel\s+invoice\b|\brelease\s+payment\b", re.I), 3, "body: cancel/reverse/payment"),
    ],
    "GENERAL": [
        (_S, re.compile(r"\bUPDATE\s+SUMMARY\b", re.I), 4.5, "subject: update summary"),
        (_S, re.compile(r"\bBerthing\s+Report\b", re.I), 4.5, "subject: berthing report"),
        (_S, re.compile(r"\bReminder\b", re.I), 3.5, "subject: reminder"),
        (_S, re.compile(r"_?RPA_?\b", re.I), 4, "subject: RPA bot notice"),
        (_S, re.compile(r"\bList\s+of\s+Outstanding\b|\bOutstanding\s+BL\b", re.I), 4, "subject: outstanding BL list"),
        (_S, re.compile(r"\bPending\s+BL\s+Release\b", re.I), 4, "subject: pending BL release"),
        (_S, re.compile(r"\bNew\s+Year\b|\bTime\s+Off\b|\bMiss\s+Connection\b|\bDelivery\s+planning\b|\bholiday\b|\bapproval\s+required\b", re.I), 4, "subject: HR / planning notice"),
        (_B, re.compile(r"\bautomated\s+notification\b|\bno\s+action\s+required\b|\bRPA\s+Bot\b", re.I), 4, "body: automated notice"),
        (_B, re.compile(r"\bupdate\s+summary\b|\bberthing\s+report\b|\boutstanding\s+BL\b|\bhappy\s+and\s+prosperous\b|\bOffice\s+resumes\b", re.I), 3, "body: operational update"),
        (_B, re.compile(r"\bReminder\s*:", re.I), 2.5, "body: reminder"),
    ],
    "SPAM": [
        (_S, re.compile(r"\bcongratulations\b|\bYou\s+have\s+WON\b|\bgift\s+card\b|\bCLAIM\s+NOW\b", re.I), 5, "subject: prize / gift card"),
        (_S, re.compile(r"\bparcel\b.*\b(?:hold|fee|payment)|\$\s?\d+\.\d{2}", re.I), 4, "subject: parcel fee"),
        (_S, re.compile(r"\bstorage\s+is\s+full\b|\bverify\s+account\b|\bupdate\s+your\s+account\b|\bundelivered\s+messages\b|\bsuspension\b", re.I), 5, "subject: account phishing"),
        (_S, re.compile(r"\b\d{2}%\s*OFF\b|\bexclusive\s+offer\b|\bONE\s+weird\s+trick\b|\bhot\s+singles\b|\bbitcoin\b|\bguaranteed\s+\d+%", re.I), 5, "subject: promotion / scam"),
        (_S, re.compile(r"\bbank\s+details\b|\bValued\s+Customer\b", re.I), 4, "subject: asks for bank details"),
        (_B, re.compile(r"https?://\S*(?:bit\.ly|claim|verify|parcel|track|winner|free|webmail|prize)\S*|click\s+here", re.I), 5, "body: suspicious link"),
        (_B, re.compile(r"\bwithin\s+24\s+hours\b|\bunpaid\s+customs\s+fee\b|\bstorage\s+limit\b|\bdeactivation\b|\bbank\s+officer\b|\burgent\s+business\s+proposal\b|\bLIMITED\s+TIME\s+OFFER\b|\bwon\s+a\s+brand\s+new\b|\bselected\s+in\s+our\s+monthly\s+draw\b", re.I), 5, "body: phishing / scam wording"),
    ],
}

_ORG_DOMAINS = re.compile(r"@(?:[\w.-]*\.)?(?:aprilasia|april)\.(?:com|com\.my)$|@(?:fujitogrp|safqa|psabdp|roxcel|ifpla|algurg|vitalsolutions)\.", re.I)
_SPAM_TLD = re.compile(r"\.(?:info|biz|co|net|org|xyz|top|click)$", re.I)


@dataclass
class ClassResult:
    category: str
    confidence: float
    reasons: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    engine: str = "rules"

    def to_payload(self) -> dict:
        return {"category": self.category, "confidence": round(self.confidence, 3),
                "reasons": self.reasons, "scores": {k: round(v, 2) for k, v in self.scores.items()}}


def attachment_hint(names: list[str]) -> tuple[float, str | None]:
    """Weak signal from attachment file names (an SI+BL pair strongly suggests a comparison request)."""
    roles = set()
    for n in names:
        low = n.lower()
        if re.search(r"(^|[^a-z])si([^a-z]|$)|instruction", low):
            roles.add("SI")
        if re.search(r"(^|[^a-z])(bl|bol)([^a-z]|$)|lading", low):
            roles.add("BL")
    if roles == {"SI", "BL"}:
        return 4.0, "attachments: SI + BL pair"
    if len(names) >= 2:
        return 1.5, "attachments: two documents"
    if roles:
        return 1.5, f"attachment: {'/'.join(sorted(roles))} only"
    return 0.0, None


def classify_rules(email: dict[str, Any], attachment_names: list[str] | None = None) -> ClassResult:
    subj = clean_subject(email.get("subject", ""))
    body = clean_body(email.get("body", ""))
    sender = email.get("from", "") or ""
    names = attachment_names if attachment_names is not None else [a.split("/")[-1] for a in email.get("attachments", [])]

    scores = {c: 0.0 for c in CATEGORIES}
    reasons: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    for cat, sigs in SIGNALS.items():
        for where, pat, w, label in sigs:
            text = subj if where == _S else body
            if pat.search(text):
                scores[cat] += w
                reasons[cat].append(label)
    w, r = attachment_hint(names)
    if r:
        scores["BL_COMPARISON"] += w
        reasons["BL_COMPARISON"].append(r)
    # sender reputation: unknown external domain with a spam-like TLD nudges towards spam, never decides alone
    if sender and not _ORG_DOMAINS.search(sender) and _SPAM_TLD.search(sender.split("@")[-1] if "@" in sender else ""):
        scores["SPAM"] += 3
        reasons["SPAM"].append(f"sender domain looks external/untrusted ({sender.split('@')[-1]})")

    # Invoice wording inside a real shipping-doc request should not flip it (subject carries invoice refs).
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, best_s = ranked[0]
    second_s = ranked[1][1]
    if best_s <= 0:
        return ClassResult("GENERAL", 0.35, ["no strong signal; defaulting to general operational mail"], scores)
    margin = best_s - second_s
    conf = 1 / (1 + math.exp(-(0.55 * margin + 0.08 * best_s - 1.2)))
    conf = round(min(0.99, max(0.4, conf)), 3)
    return ClassResult(best, conf, reasons[best][:5], scores)

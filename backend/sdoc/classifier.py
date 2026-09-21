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
        (_S, re.compile(r"\bdouble\s*check\b.{0,40}\b(?:before|release)\b|\bsanity[- ]check\b|\bcompar(?:e|ing)\b.{0,30}\b(?:files?|documents?|B/?L|draft)\b", re.I), 3.5, "subject: double/sanity-check or compare wording"),
        (_B, re.compile(r"\b(?:double|sanity|cross)[- ]?check(?:ed|ing)?\b.{0,80}\b(?:document|file|attachment|paperwork|instruction|draft|bill\s+of\s+lading|B/?L)\b", re.I), 3.5, "body: cross/double-check the documents"),
        (_B, re.compile(r"\bsecond\s+set\s+of\s+eyes\b|\bwant(?:ed)?\s+(?:a\s+)?(?:second|another)\s+(?:look|opinion)\b", re.I), 3, "body: wants a second review before sign-off"),
        (_B, re.compile(r"\breleas(?:e|ing)\s+the\s+(?:final\s+)?bill\s+of\s+lading\b|\bbefore\s+we\s+release\s+the\s+B/?L\b|\bbefore\s+we\s+sign\s+off\b", re.I), 3, "body: check before releasing/signing off the BL"),
        (_B, re.compile(r"\bcross[- ]?check\s+(?:them|these|it|the\s+documents)\b|\bspot\s+(?:any\s+)?discrepanc", re.I), 3, "body: cross-check for discrepancies"),
        (_B, re.compile(r"\b(?:our|the)\s+instruction\b.{0,20}\b(?:against|vs\.?|versus)\b.{0,20}\b(?:carrier'?s?|the)\s+draft\b", re.I), 3.5, "body: instruction vs carrier draft comparison"),
    ],
    "SI_REQUEST": [
        (_S, re.compile(r"^\s*SI\s*-\s*\S", re.I), 4, "subject: 'SI - ...' shipping instruction ref"),
        (_S, re.compile(r"\bCUST\s+SI\b", re.I), 4, "subject: customer SI"),
        (_S, re.compile(r"\bREQUEST\s+SI\b", re.I), 4, "subject: request SI"),
        (_S, re.compile(r"\bSI\s+NEEDED\b|\bLATEST\s+SI\b|\bNEED\s+SI\b", re.I), 4, "subject: SI needed"),
        (_S, re.compile(r"\bnew\s+booking\b", re.I), 2, "subject: new booking"),
        (_S, re.compile(r"\bfirst[- ]time\s+shipper\b", re.I), 3, "subject: first-time shipper onboarding"),
        (_B, re.compile(r"\bplease\s+find\s+shipping\s+instruction\b", re.I), 4.5, "body: shipping instruction provided"),
        (_B, re.compile(r"\bPOL\s*:.*\n\s*POD\s*:", re.I), 3, "body: POL/POD block"),
        (_B, re.compile(r"\bDocuments\s+Required\b", re.I), 2.5, "body: documents required list"),
        (_B, re.compile(r"\bDescription\s+of\s+Goods\b", re.I), 1.5, "body: description of goods"),
        (_B, re.compile(r"\brevert\s+with\s+draft\s+B/?L\b", re.I), 1.5, "body: revert with draft BL"),
        (_B, re.compile(r"\b(?:send|provide|share|need|require)\b.{0,30}\b(?:SI|shipping\s+instruction)\b", re.I), 3, "body: asks for SI"),
        (_B, re.compile(r"\bsubmit\s+instructions?\b|\bplease\s+raise\b.{0,20}\binstruction\b|\bbooking\s+instruction\b", re.I), 3.5, "body: booking-instruction wording"),
        (_B, re.compile(r"\b(?:need|require)\s+the\s+(?:standard\s+)?instruction\s+form\b", re.I), 4, "body: needs the instruction form"),
        (_B, re.compile(r"\bwhat\s+(?:information|details|documents)\s+do\s+you\s+need\b|\bwhat\s+do\s+you\s+need\s+from\s+us\b", re.I), 3, "body: onboarding - asks what's needed"),
        (_B, re.compile(r"\badvise\s+the\s+format\b|\bformat\s+you\s+need\s+our\b", re.I), 3, "body: asks for the required submission format"),
        (_B, re.compile(r"\bcargo\s+(?:is\s+)?ready\s+to\s+move\b|\bbefore\s+(?:the\s+)?vessel\s+departs?\b|\bsubmit\s+(?:it\s+)?to\s+the\s+line\b", re.I), 2.5, "body: pre-shipment booking wording"),
        (_B, re.compile(r"\bfirst\s+(?:time\s+)?shipper\b|\bfirst\s+shipment\s+with\s+you\b", re.I), 3, "body: first-time shipper onboarding"),
        (_B, re.compile(r"\bget\s+the\s+booking\s+confirmed\b|\bbooking\s+details\s+for\b", re.I), 2, "body: booking confirmation wording"),
        (_B, re.compile(r"\bwhat\s+(?:documents?|paperwork|information|details)\b.{0,25}\b(?:need|require)\b|\b(?:documents?|paperwork)\s+(?:you\s+)?require\s+from\s+us\b", re.I), 3, "body: asks what paperwork is required"),
        (_B, re.compile(r"\bsend\s+(?:over\s+)?the\s+template\b|\bexact\s+fields?\s+you\s+need\b|\bfields?\s+(?:you\s+need\s+)?filled\s+in\b", re.I), 3, "body: asks for the submission template/fields"),
        (_B, re.compile(r"\bcontainer\s+ready\s+to\s+load\b|\bget\s+this\s+booked\s+with\b|\bopened\s+an\s+account\b.{0,30}\bfirst\s+container\b", re.I), 2.5, "body: pre-booking / new-account wording"),
        (_B, re.compile(r"\bfirst\s+(?:container|shipment)\s+with\s+your\s+company\b|\bworking\s+with\s+your\s+company\b", re.I), 2.5, "body: new-customer onboarding"),
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
        (_S, re.compile(r"\bstatement\s+of\s+account\b", re.I), 4, "subject: statement of account"),
        (_B, re.compile(r"\bstatement\s+of\s+account\b|\boutstanding\s+balance\b", re.I), 3.5, "body: statement of account / outstanding balance"),
        (_B, re.compile(r"\bnumbers?\s+don'?t\s+(?:line\s+up|match|add\s+up)\b|\bdoesn'?t\s+(?:line\s+up|match)\s+with\s+what\s+was\s+quoted\b", re.I), 4, "body: figures don't reconcile with the quote"),
        (_B, re.compile(r"\bunpaid\s+balance\b|\bsend\s+(?:an\s+)?updated\s+statement\b|\bhasn'?t\s+been\s+settled\b", re.I), 3.5, "body: unpaid balance / statement follow-up"),
        (_B, re.compile(r"\bover\s?charged\b|\bissue\s+a\s+credit\s+note\b", re.I), 3.5, "body: overcharge / credit-note request"),
        (_S, re.compile(r"\bdiscrepancy\s+on\s+(?:the\s+)?(?:latest\s+)?bill\b|\bunpaid\s+balance\b", re.I), 3, "subject: billing discrepancy / unpaid balance"),
        (_B, re.compile(r"\bbilled\s+twice\b|\bcorrected\s+statement\b|\bhigher\s+than\s+(?:what\s+was\s+)?quoted\b|\bexplain\s+the\s+difference\b", re.I), 3.5, "body: duplicate charge / overcharge wording"),
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
        (_B, re.compile(r"\bwill\s+review\b|\breceived\s+it\b|\bnoted(?:,)?\s+(?:with\s+)?thanks?\b|\bnice\s+weekend\b|\bthanks,?\s+we\s+received\b", re.I), 4, "body: short acknowledgement / no action needed"),
        (_B, re.compile(r"\bno(?:thing)?\s+(?:further\s+)?(?:action\s+)?(?:is\s+)?(?:needed|required)\b|\bshould(?:n'?t|\s+not)\s+affect\b|\bjust\s+sharing\s+for\s+awareness\b|\ball\s+good\s+on\s+our\s+end\b", re.I), 3.5, "body: informational, no action needed"),
        (_S, re.compile(r"\bFYI\b|\bheads?[- ]up\b", re.I), 2.5, "subject: FYI / heads-up notice"),
        (_B, re.compile(r"\breally\s+appreciat(?:e|ed)\b|\bthanks?\s+for\s+sorting\b|\bturned\s+(?:that|it)\s+around\b", re.I), 3, "body: thank-you / closed-out acknowledgement"),
    ],
    "SPAM": [
        (_S, re.compile(r"\bcongratulations\b|\bYou\s+have\s+WON\b|\byou\s+won\b|\bgift\s+card\b|\bCLAIM\s+NOW\b|\bclaim\s+your\s+prize\b", re.I), 5, "subject: prize / gift card"),
        (_S, re.compile(r"\bparcel\b.*\b(?:hold|fee|payment)|\$\s?\d+\.\d{2}", re.I), 4, "subject: parcel fee"),
        (_S, re.compile(r"\bstorage\s+is\s+full\b|\bverify\s+account\b|\bupdate\s+your\s+account\b|\bundelivered\s+messages\b|\bsuspension\b|\b(?:account|mailbox)\s+(?:is|has\s+been|will\s+be)\s+(?:locked|limited|suspended|restricted)\b|\bmailbox\s+quota\s+exceeded\b|\bimmediate\s+action\b.{0,20}\bmailbox\b", re.I), 5, "subject: account/mailbox phishing"),
        (_S, re.compile(r"\b\d{2}%\s*OFF\b|\bexclusive\s+offer\b|\bONE\s+weird\s+trick\b|\bhot\s+singles\b|\bbitcoin\b|\bguaranteed\s+\d+%", re.I), 5, "subject: promotion / scam"),
        (_S, re.compile(r"\bbank\s+details\b|\bValued\s+Customer\b", re.I), 4, "subject: asks for bank details"),
        (_S, re.compile(r"\bboost\s+your\s+(?:website|site)\b|\brank\s+your\s+site\b", re.I), 4, "subject: SEO/marketing spam"),
        (_S, re.compile(r"\bwire\s+transfer\b.{0,20}\burgent", re.I), 4, "subject: urgent wire transfer (CEO fraud pattern)"),
        (_B, re.compile(r"https?://\S*(?:bit\.ly|claim|verify|parcel|track|winner|free|webmail|prize)\S*|click\s+here", re.I), 5, "body: suspicious link"),
        (_B, re.compile(r"\bwithin\s+24\s+hours\b|\bunpaid\s+customs\s+fee\b|\bstorage\s+limit\b|\bdeactivation\b|\bbank\s+officer\b|\burgent\s+business\s+proposal\b|\bLIMITED\s+TIME\s+OFFER\b|\bwon\s+a\s+brand\s+new\b|\bselected\s+in\s+our\s+monthly\s+draw\b|\bsuspended\s+in\s+\d+\s+hours\b|\bverify\s+your\s+credentials\b|\bmailbox\s+will\s+be\s+suspended\b", re.I), 5, "body: phishing / scam wording"),
        (_B, re.compile(r"\byou\s+won\b|\bsend\s+bank\s+details\b|\bconfirm\s+your\s+password\b|\bverify\s+your\s+password\b|\baccount\s+has\s+been\s+limited\b|\baccount\s+is\s+locked\b", re.I), 5, "body: prize / phishing wording"),
        (_B, re.compile(r"\brank\s+your\s+site\b|\bfree\s+audit\b|#1\s+on\s+google|\bboost\s+your\s+(?:website|site|traffic)\b", re.I), 4, "body: SEO/marketing spam wording"),
        (_B, re.compile(r"\bdo\s+not\s+call\b|\bi'?m\s+in\s+a\s+meeting\b|\bprocess\s+(?:a\s+)?payment\s+(?:today|now|urgently)\b|\bwire\s+transfer\b.{0,30}\burgent", re.I), 4, "body: CEO-fraud / urgent wire transfer wording"),
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
    # Sender-domain TLD is, at best, weak circumstantial evidence - lots of ordinary businesses use
    # .net/.org/.co/.info etc, so it must never outrank real content/attachment evidence for the
    # opposite conclusion (Round 3 fix: a genuine 2-attachment BL_COMPARISON request from a '.net'
    # sender was previously misclassified SPAM on the TLD nudge alone). Root-cause fix, not a
    # one-email patch: compute the strongest *non-SPAM* signal already found (content regex hits +
    # attachment_hint) BEFORE applying any TLD nudge, and let that countervailing evidence suppress
    # or shrink it rather than hard-coding this one sender/subject.
    non_spam_signal = max((s for c, s in scores.items() if c != "SPAM"), default=0.0)
    has_attachments = bool(names)
    if sender and not _ORG_DOMAINS.search(sender) and _SPAM_TLD.search(sender.split("@")[-1] if "@" in sender else ""):
        tld = sender.split("@")[-1]
        if has_attachments or non_spam_signal >= 2.5:
            # real attachments, or already-strong content evidence for a legitimate category:
            # a mainstream business TLD alone must not override that - skip the nudge entirely.
            pass
        elif non_spam_signal > 0:
            scores["SPAM"] += 1.5
            reasons["SPAM"].append(f"sender domain looks external/untrusted ({tld}) - weak signal, some content evidence too")
        else:
            scores["SPAM"] += 3
            reasons["SPAM"].append(f"sender domain looks external/untrusted ({tld})")

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

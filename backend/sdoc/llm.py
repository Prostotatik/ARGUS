"""Gemini path (google-genai). Used only when GEMINI_API_KEY is set; otherwise the rules twins run.

STATUS: written against the installed ``google-genai`` API (``client.aio.models.generate_content`` with
``response_mime_type='application/json'`` + ``response_json_schema``) and unit-tested with a fake client.
It has NOT been exercised against the live Gemini API (no key on the build machine).

Guard rails against hallucination
    * temperature 0, structured JSON output, values must be quoted from the document;
    * every returned ``evidence`` string is verified to occur in the document text; unverifiable
      evidence lowers the confidence and adds the ``evidence_unverified`` flag (the gate sees it);
    * the compare step stays a pure function - the LLM never decides match/mismatch.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from . import config
from .classifier import ClassResult, clean_body, clean_subject
from .config import CATEGORIES
from .docparse import ParsedDoc
from .rules_extract import Extracted
from . import normalize as nz

CLASSIFIER_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "confidence": {"type": "number"},
        "reasons": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["category", "confidence", "reasons"],
}

FIELD_SCHEMA = {
    "type": "object",
    "properties": {
        "si_value": {"type": "string"},
        "si_evidence": {"type": "string"},
        "bl_value": {"type": "string"},
        "bl_evidence": {"type": "string"},
        "confidence": {"type": "number"},
        "notes": {"type": "string"},
    },
    "required": ["si_value", "si_evidence", "bl_value", "bl_evidence", "confidence"],
}

CLASSIFIER_SYSTEM = (
    "You classify emails arriving in a shipping-documentation inbox. Categories: "
    "BL_COMPARISON = a request to check/compare a Shipping Instruction (SI) with a draft Bill of Lading (BL), "
    "including requests to send the draft BL for checking; "
    "SI_REQUEST = a request for, or delivery of, a new shipping instruction; "
    "INVOICE_QUERY = billing, invoice, freight/local-charge, GR or cancellation questions; "
    "GENERAL = operational updates, reports, reminders, automated notices, HR/office mail; "
    "SPAM = phishing, prizes, unsolicited promotions. "
    "Ignore signatures, legal banners and quoted older messages. Answer with JSON only."
)

FIELD_HELP = {
    "shipper": "the party shipping the goods (exporter/seller/consignor). Return the NAME only, no address.",
    "consignee": "the party receiving the goods (also labelled 'To the Order of'). Return the NAME only, no address.",
    "notify_party": "the party to notify on arrival (labelled Notify / Notify Party). Return the NAME only, no address.",
    "port_of_loading": "the port where cargo is loaded (labels: Port of Loading, POL, Load Port, Loading Port).",
    "port_of_discharge": "the port where cargo is discharged (labels: Port of Discharge, POD, Discharge Port).",
    "container_count": "the TOTAL number of containers (labels: No. of Containers, Total Containers, Container Count). "
                       "Return it as printed, e.g. '3 x 40HC'.",
    "gross_weight_kg": "the TOTAL gross weight of the shipment, as printed including its unit (kg/KGS/MT/lbs). "
                       "Not net weight, not per-container weight.",
}

FIELD_SYSTEM = (
    "You extract ONE field from a Shipping Instruction (SI) and a draft Bill of Lading (BL). "
    "Labels differ between documents (e.g. 'Load Port' = 'Port of Loading'); match by meaning. "
    "Copy the value exactly as printed in each document, and copy the single source line that contains it "
    "as evidence. If a document has no value for the field, or it is blank / '???' / 'TBA' / '____', return an "
    "empty string for that document. Never guess or infer a value. Answer with JSON only."
)


class GeminiError(RuntimeError):
    pass


class GeminiClient:
    """Thin async wrapper. ``client`` may be injected (tests use a fake with the same surface)."""

    def __init__(self, api_key: str | None = None, model: str | None = None, client: Any = None,
                 timeout_s: float = 45.0, max_attempts: int = 2) -> None:
        self.model = model or config.gemini_model()
        self.timeout_s = timeout_s
        self.max_attempts = max_attempts
        if client is not None:
            self.client = client
        else:
            from google import genai  # imported lazily: rules mode must not need the SDK/key
            self.client = genai.Client(api_key=api_key or config.gemini_key())

    async def generate_json(self, prompt: str, schema: dict, system: str | None = None) -> dict:
        cfg = {
            "system_instruction": system,
            "response_mime_type": "application/json",
            "response_json_schema": schema,
            "temperature": 0.0,
        }
        last: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                resp = await asyncio.wait_for(
                    self.client.aio.models.generate_content(model=self.model, contents=prompt, config=cfg),
                    timeout=self.timeout_s,
                )
                return parse_json_text(getattr(resp, "text", None))
            except Exception as e:  # noqa: BLE001 - surfaced to the node as a visible error
                last = e
                if attempt + 1 < self.max_attempts:
                    await asyncio.sleep(0.8 * (attempt + 1))
        raise GeminiError(f"{type(last).__name__}: {last}") from last


def parse_json_text(text: str | None) -> dict:
    if not text:
        raise ValueError("empty model response")
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S)
    obj = json.loads(t)
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        obj = obj[0]
    if not isinstance(obj, dict):
        raise ValueError("model response is not a JSON object")
    return obj


# ---------------------------------------------------------------------------
async def classify_gemini(gc: GeminiClient, email: dict, attachment_names: list[str]) -> ClassResult:
    prompt = (
        f"Subject: {clean_subject(email.get('subject', ''))}\n"
        f"From: {email.get('from', '')}\n"
        f"Attachments: {', '.join(attachment_names) or 'none'}\n\n"
        f"Body (signature/quoted thread removed):\n{clean_body(email.get('body', ''))[:4000]}"
    )
    out = await gc.generate_json(prompt, CLASSIFIER_SCHEMA, CLASSIFIER_SYSTEM)
    cat = str(out.get("category", "")).strip().upper()
    if cat not in CATEGORIES:
        raise GeminiError(f"model returned unknown category {out.get('category')!r}")
    conf = out.get("confidence", 0.7)
    try:
        conf = max(0.0, min(1.0, float(conf)))
    except (TypeError, ValueError):
        conf = 0.7
    reasons = [str(r) for r in (out.get("reasons") or [])][:5]
    return ClassResult(cat, conf, reasons, {}, engine="gemini")


def _verify_evidence(doc: ParsedDoc, evidence: str, value: str) -> bool:
    if not evidence:
        return False
    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()  # noqa: E731
    text = norm(doc.text)
    ev = norm(evidence)
    if ev and ev in text:
        return True
    return bool(value) and norm(value) in text


def _to_extracted(field_name: str, doc: ParsedDoc, value: str, evidence: str, conf: float) -> Extracted:
    ex = Extracted(field=field_name, engine="gemini")
    value = (value or "").strip()
    if not doc.readable:
        ex.flags.append("not_found")
        ex.evidence = f"{doc.name}: {doc.status_detail or doc.status}"
        return ex
    if nz.is_blank(value):
        ex.value = None
        ex.flags.append("blank" if evidence else "not_found")
        ex.evidence = evidence or None
        return ex
    ex.value, ex.evidence = value, evidence or None
    c = conf
    if not _verify_evidence(doc, evidence, value):
        ex.flags.append("evidence_unverified")
        c = min(c, 0.5)
    if nz.has_placeholder(value):
        ex.flags.append("placeholder")
        c = min(c, 0.4)
    if doc.ocr_used:
        ex.flags.append("ocr")
        c = min(c, 0.6)
    ex.confidence = max(0.05, min(0.99, c))
    return ex


async def extract_field_gemini(gc: GeminiClient, field_name: str, si: ParsedDoc, bl: ParsedDoc) -> tuple[Extracted, Extracted]:
    prompt = (
        f"Field to extract: {field_name} - {FIELD_HELP[field_name]}\n\n"
        f"=== SHIPPING INSTRUCTION (SI) ===\n{si.text[:9000]}\n\n"
        f"=== DRAFT BILL OF LADING (BL) ===\n{bl.text[:9000]}\n"
    )
    out = await gc.generate_json(prompt, FIELD_SCHEMA, FIELD_SYSTEM)
    try:
        conf = max(0.0, min(1.0, float(out.get("confidence", 0.7))))
    except (TypeError, ValueError):
        conf = 0.7
    s = _to_extracted(field_name, si, str(out.get("si_value", "") or ""), str(out.get("si_evidence", "") or ""), conf)
    b = _to_extracted(field_name, bl, str(out.get("bl_value", "") or ""), str(out.get("bl_evidence", "") or ""), conf)
    return s, b

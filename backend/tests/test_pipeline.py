import asyncio
import json
import re

import pytest

from sdoc.docparse import ParsedDoc
from sdoc.flybrain import FlyBrain
from sdoc.inbox import Inbox
from sdoc.pipeline import Pipeline
from sdoc.rules_extract import extract_field

SI = """SHIPPING INSTRUCTION
========================================

Shipper: ACME EXPORTS PTE. LTD.
  1 Harbour Road; Singapore
Consignee (Non-Negotiable): GLOBEX TRADING GMBH
Notify: GLOBEX TRADING GMBH
Port of Loading (POL): SINGAPORE, SINGAPORE (SGSIN)
POD: HAMBURG, GERMANY
Total Containers: {cnt}
Gross Wt (kgs): 22,000 KG
Vessel: MV TEST
"""
BL = """BILL OF LADING (DRAFT)
========================================

SHIPPER: Acme Exports Pte Ltd
To the Order of: Globex Trading GmbH
Notify Party: GLOBEX TRADING GMBH
Load Port: Singapore
Discharge Port: Hamburg
Container Count: {cnt}
GROSS WEIGHT: {wt}
Vessel: MV TEST
"""
BODY_ATTACHED = "Dear Ann,\n\nAttached are the SI and draft BL for OC 5RAE-00001. Please check the details and confirm."


def make_inbox(tmp_path, emails):
    (tmp_path / "inbox").mkdir()
    (tmp_path / "attachments").mkdir()
    for e, files in emails:
        rec = {"email_id": e["email_id"], "from": e.get("from", "staff@aprilasia.com"),
               "subject": e.get("subject", "TO CONFIRM DOCS _ 5RAE-00001 _ HAMBURG"), "body": e.get("body", BODY_ATTACHED),
               "attachments": []}
        for name, content in files.items():
            p = tmp_path / "attachments" / name
            if isinstance(content, bytes):
                p.write_bytes(content)
            else:
                p.write_text(content, encoding="utf-8")
            rec["attachments"].append(f"attachments/{name}")
        (tmp_path / "inbox" / f"{rec['email_id']}.json").write_text(json.dumps(rec), encoding="utf-8")
    return Inbox(tmp_path)


def pipe_for(inbox, **kw):
    gate = FlyBrain()
    gate.calibrate(n_train=1500, n_val=200, n_anom=20)
    return Pipeline(inbox=inbox, gate=gate, default_engine=kw.pop("default_engine", "rules"), **kw)


def run(pipe, eid, **kw):
    return asyncio.run(pipe.run(eid, **kw))


def pair(cnt_si="2 x 40'HC", cnt_bl="2X40HC", wt="48,501.7 LBS"):
    return {"e1_SI.txt": SI.format(cnt=cnt_si), "e1_BL.txt": BL.format(cnt=cnt_bl, wt=wt)}


def test_label_unit_and_format_noise_is_no_mismatch(tmp_path):
    inbox = make_inbox(tmp_path, [({"email_id": "e1"}, pair())])
    r, _ = run(pipe_for(inbox), "e1")
    assert r["category"] == "BL_COMPARISON" and r["status"] == "OK", r["headline"]
    assert r["headline"] == "No mismatch detected" and r["defect_fields"] == []
    assert [f["field"] for f in r["fields"]][:2] == ["shipper", "consignee"]


def test_real_difference_flagged_with_side_by_side(tmp_path):
    inbox = make_inbox(tmp_path, [({"email_id": "e1"}, pair("3 x 40'HC", "4 x 40'HC"))])
    r, _ = run(pipe_for(inbox), "e1")
    assert r["status"] == "MISMATCH" and r["defect_fields"] == ["container_count"] and r["has_defect"]
    assert r["headline"] == "container_count: SI 3 / BL 4"
    f = next(x for x in r["fields"] if x["field"] == "container_count")
    assert f["si_norm"] == 3 and f["bl_norm"] == 4 and f["si_evidence"] and f["bl_evidence"]


def test_trace_event_order_and_shape(tmp_path):
    inbox = make_inbox(tmp_path, [({"email_id": "e1"}, pair())])
    seen = []
    r, _ = run(pipe_for(inbox), "e1", on_event=seen.append)
    assert seen == r["events"][:len(seen)] and [e["seq"] for e in r["events"]] == list(range(len(r["events"])))
    nodes = [(e["node"], e["state"]) for e in r["events"]]
    for a, b in [(("inbox", "done"), ("classifier", "start")), (("classifier", "done"), ("aggregator", "start")),
                 (("aggregator", "done"), ("compare", "start")), (("compare", "done"), ("gate", "start")),
                 (("gate", "done"), ("report", "done"))]:
        assert nodes.index(a) < nodes.index(b)
    for f in ["shipper", "consignee", "notify_party", "port_of_loading", "port_of_discharge", "container_count",
              "gross_weight_kg"]:
        assert nodes.index((f"field:{f}", "start")) < nodes.index((f"field:{f}", "done")) < nodes.index(("aggregator", "start"))
    # the 7 field agents run concurrently: every start precedes the first done
    first_done = min(i for i, n in enumerate(nodes) if n[0].startswith("field:") and n[1] == "done")
    starts = [i for i, n in enumerate(nodes) if n[0].startswith("field:") and n[1] == "start"]
    assert len(starts) == 7 and max(starts) < first_done
    engines = {e["node"]: e["engine"] for e in r["events"] if e["state"] == "done"}
    assert engines["compare"] == "pure" and engines["gate"] == "flynet" and engines["classifier"] == "rules"
    for k in ("seq", "t_ms", "node", "state", "engine", "duration_ms", "summary", "payload"):
        assert k in r["events"][0]
    gate_ev = next(e for e in r["events"] if e["node"] == "gate" and e["state"] == "done")
    for k in ("suspicion", "threshold", "escalate", "input_vector", "kc_active", "winner_kc", "reason"):
        assert k in gate_ev["payload"]
    report = r["events"][-1]
    assert report["node"] == "report" and report["payload"]["email_id"] == "e1"


def test_non_comparison_stops_after_classifier(tmp_path):
    inbox = make_inbox(tmp_path, [({"email_id": "e1", "subject": "Congratulations! You have WON a $1,000 Gift Card",
                                    "body": "Click here http://bit.ly/claim-prize-now", "from": "w@prize-claims.info"}, {})])
    r, _ = run(pipe_for(inbox), "e1")
    assert r["category"] == "SPAM" and r["status"] is None
    # a confidently-classified non-comparison email still passes through the gate (classifier
    # confidence is itself one of the gate's grey-zone inputs now - reviews/developer.md #1/#10)
    # but a clean, high-confidence SPAM call does not escalate it.
    assert [e["node"] for e in r["events"] if e["state"] != "start"] == ["inbox", "classifier", "gate", "report"]


def test_low_confidence_non_comparison_can_escalate(tmp_path):
    # No rule fires at all (confidence floors at the classifier's own 0.35 "no signal" default) -
    # genuinely uncertain, unlike a normal low-but-matched confidence - the gate may ask for review.
    inbox = make_inbox(tmp_path, [({"email_id": "e1", "subject": "hey", "body": "ok thanks", "from": "a@b.com"}, {})])
    r, _ = run(pipe_for(inbox), "e1")
    assert r["category"] == "GENERAL"
    assert r["gate"]["decided_by"] == "flynet"
    if r["status"] == "NEEDS_REVIEW":
        assert r["review_reason"] == "low_confidence"


def test_missing_attachment_variants(tmp_path):
    inbox = make_inbox(tmp_path, [
        ({"email_id": "e1", "body": "Please compare the SI and draft BL for X and confirm (attachments appear to have been dropped)."}, {}),
        ({"email_id": "e2"}, {"e2_SI.txt": SI.format(cnt="1")}),
        ({"email_id": "e3", "subject": "REQUEST BL DRAFT _ PO 1", "body": "Dear Ann,\n\nPlease assist to send the draft BL for X for checking asap.\n\nThank you."}, {}),
    ])
    p = pipe_for(inbox)
    r1, _ = run(p, "e1")
    r2, _ = run(p, "e2")
    r3, _ = run(p, "e3")
    assert (r1["status"], r1["review_reason"]) == ("NEEDS_REVIEW", "missing_attachment")
    assert (r2["status"], r2["review_reason"]) == ("NEEDS_REVIEW", "missing_attachment")
    assert r1["escalation"]["open"] and r1["gate"]["decided_by"] == "deterministic_trigger"
    assert r3["category"] == "BL_COMPARISON" and r3["status"] == "OK" and r3["comparison_performed"] is False


def test_wrong_doc_type_unreadable_and_missing_value(tmp_path):
    invoice = "COMMERCIAL INVOICE\n=====\nSeller: ACME\nBuyer: GLOBEX\n*** THIS IS A COMMERCIAL INVOICE - NOT A SHIPPING INSTRUCTION ***\n"
    blank_si = SI.format(cnt="2 x 40'HC").replace("POD: HAMBURG, GERMANY", "POD: ???")
    inbox = make_inbox(tmp_path, [
        ({"email_id": "w"}, {"w_SI.txt": SI.format(cnt="1"), "w_BL.txt": invoice}),
        ({"email_id": "u1"}, {"u1_SI.txt": SI.format(cnt="1"), "u1_BL.pdf": b""}),
        ({"email_id": "u2"}, {"u2_SI.txt": SI.format(cnt="1"), "u2_BL.pdf": b"%PDF-1.5\n" + bytes(range(200))}),
        ({"email_id": "m"}, {"m_SI.txt": blank_si, "m_BL.txt": BL.format(cnt="2 x 40'HC", wt="22000 KG")}),
    ])
    p = pipe_for(inbox)
    want = {"w": "wrong_doc_type", "u1": "unreadable", "u2": "unreadable", "m": "missing_value"}
    for eid, reason in want.items():
        r, _ = run(p, eid)
        assert r["status"] == "NEEDS_REVIEW" and r["review_reason"] == reason, (eid, r["headline"])
        assert not r["has_defect"] and r["defect_fields"] == []
        assert r["escalation"]["open"] and r["escalation"]["evidence"]


def test_injected_failure_is_visible_and_retry_repairs(tmp_path):
    inbox = make_inbox(tmp_path, [({"email_id": "e1"}, pair())])
    p = pipe_for(inbox)
    r, st = run(p, "e1", inject_fail={"field:consignee"})
    assert any(e["node"] == "field:consignee" and e["state"] == "error" for e in r["events"])
    assert [e["node"] for e in r["errors"]] == ["field:consignee"]
    assert r["status"] == "NEEDS_REVIEW"
    r2, _ = run(p, "e1", prior=st)
    retried = {e["node"] for e in r2["events"][len(r["events"]):]}
    assert "field:consignee" in retried and "field:shipper" not in retried      # only the failed node re-ran
    assert r2["errors"] == [] and r2["status"] == "OK"


# ---------------------------------------------------------------- Gemini path with a fake client
class _Resp:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    async def generate_content(self, *, model, contents, config):
        self.calls.append(config)
        if self.fail:
            raise RuntimeError("503 UNAVAILABLE")
        props = config["response_json_schema"]["properties"]
        assert config["response_mime_type"] == "application/json" and config["temperature"] == 0.0
        if "category" in props:
            return _Resp(json.dumps({"category": "BL_COMPARISON", "confidence": 0.93, "reasons": ["fake model"]}))
        fld = re.search(r"Field to extract: (\w+)", contents).group(1)
        si_txt = contents.split("=== SHIPPING INSTRUCTION (SI) ===\n")[1].split("\n\n=== DRAFT")[0]
        bl_txt = contents.split("=== DRAFT BILL OF LADING (BL) ===\n")[1]
        out = {"confidence": 0.9}
        for side, txt in (("si", si_txt), ("bl", bl_txt)):
            doc = ParsedDoc(path="x", name=side, fmt="txt", lines=txt.split("\n"))
            e = extract_field(doc, fld)
            out[f"{side}_value"], out[f"{side}_evidence"] = e.value or "", e.evidence or ""
        return _Resp("```json\n" + json.dumps(out) + "\n```")


class FakeClient:
    def __init__(self, fail=False):
        self.aio = type("A", (), {})()
        self.aio.models = FakeModels(fail)


def test_gemini_path_with_fake_client(tmp_path):
    from sdoc.llm import GeminiClient
    inbox = make_inbox(tmp_path, [({"email_id": "e1"}, pair("3 x 40'HC", "4 x 40'HC"))])
    fake = FakeClient()
    p = pipe_for(inbox, gemini=GeminiClient(client=fake, model="fake", max_attempts=1))
    r, _ = run(p, "e1", force_engine="gemini")
    assert r["engine"] == {"classifier": "gemini", "fields": "gemini"}
    assert r["status"] == "MISMATCH" and r["defect_fields"] == ["container_count"]
    assert len(fake.aio.models.calls) == 8        # 1 classifier + 7 field agents
    assert {e["engine"] for e in r["events"] if e["node"].startswith("field:") and e["state"] == "done"} == {"gemini"}


def test_gemini_failure_falls_back_visibly(tmp_path):
    from sdoc.llm import GeminiClient
    inbox = make_inbox(tmp_path, [({"email_id": "e1"}, pair(wt="22,000 KG"))])
    p = pipe_for(inbox, gemini=GeminiClient(client=FakeClient(fail=True), model="fake", max_attempts=1))
    r, st = run(p, "e1", force_engine="gemini")
    assert any(e["state"] == "error" and e["engine"] == "gemini" for e in r["events"])
    assert r["engine"]["classifier"] == "rules" and r["engine"]["fields"] == "rules"       # honest about the twin
    assert len(r["errors"]) == 8 and all(e["fallback"] == "rules" for e in r["errors"])
    assert r["status"] == "OK"                                                             # result still produced


def test_no_key_never_claims_gemini(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    inbox = make_inbox(tmp_path, [({"email_id": "e1"}, pair())])
    p = pipe_for(inbox)
    r, _ = run(p, "e1", force_engine="gemini")
    assert r["engine"]["classifier"] == "rules"


# ---------------------------------------------------------------- dataset-backed checks
DATA = Inbox()
needs_data = pytest.mark.skipif(len(DATA.ids()) == 0 if (DATA.root / "inbox").exists() else True, reason="bundle not present")


@needs_data
def test_dataset_edge_cases_and_known_mismatch():
    p = Pipeline(inbox=DATA, gate=FlyBrain.load_or_calibrate(None), default_engine="rules")
    r, _ = run(p, "email_004")
    assert r["status"] == "MISMATCH" and r["defect_fields"] == ["consignee", "notify_party"]
    reasons = {}
    for i in range(501, 521):
        r, _ = run(p, f"email_{i}")
        assert r["status"] == "NEEDS_REVIEW"
        reasons[r["review_reason"]] = reasons.get(r["review_reason"], 0) + 1
    # email_512/513/514 are genuinely scanned (image-only) PDFs: OCR (rapidocr, reviews/developer.md
    # #5) now actually reads 2 of them (513/514) well enough that the FLY GATE - not a deterministic
    # trigger - decides to escalate them on its own (real, non-circular grey-zone job on the
    # official dataset, not just synthetic calibration data); the third still lands on a genuine
    # missing_value (a field the OCR text did not carry). email_511/515 are corrupt (non-image)
    # PDFs, unreadable by design and unrelated to OCR.
    assert reasons == {"wrong_doc_type": 5, "missing_attachment": 5, "unreadable": 4, "missing_value": 6}
    assert (run(p, "email_513")[0]["gate"] or {}).get("decided_by") == "flynet"


@needs_data
def test_api_sse_review_and_flybrain(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import sdoc.api as api
    monkeypatch.setattr(api, "GATE_PATH", tmp_path / "gate.json")
    monkeypatch.setattr(api.STORE, "out", tmp_path)
    c = TestClient(api.app)
    assert c.get("/api/health").json()["engine"] in ("rules", "gemini")
    r = c.post("/api/process/email_004")
    evs = [json.loads(x[6:]) for x in r.text.split("\n\n") if x.startswith("data:")]
    assert evs[-1]["node"] == "report" and evs[-1]["payload"]["status"] == "MISMATCH"
    assert c.get("/api/result/email_004").json()["email_id"] == "email_004"
    assert c.get("/api/result/email_nope").status_code == 404
    fb = c.get("/api/flybrain").json()
    assert fb["n_kc"] == len(fb["projection"]) == len(fb["weights"])
    body = {"decision": "correct_field", "field": "consignee", "corrected_bl": "EAST BRIGHT FZ-LLC"}
    u = c.post("/api/review/email_004", json=body).json()
    assert u["defect_fields"] == ["notify_party"] or "consignee" not in u["defect_fields"]
    assert u["review"]["decision"] == "correct_field"
    assert c.post("/api/review/email_004", json={"decision": "bogus"}).status_code == 422
    assert any(e["email_id"] == "email_004" for e in c.get("/api/emails").json())
    st = c.get("/api/stats").json()
    assert st["emails_total"] == len(DATA.ids())

"""Judge robustness harness. Copies txt SI/BL pairs of BL_COMPARISON emails, applies mutations, reruns pipeline,
compares vs baseline (backend/out/submission.json)."""
import asyncio, json, os, re, shutil, sys, random
from pathlib import Path
ROOT = Path(r"E:/Projects/Averis x Monash")
sys.path.insert(0, str(ROOT / "backend"))
os.environ["SDOC_ENGINE"] = "rules"
from sdoc.inbox import Inbox
from sdoc.pipeline import Pipeline
from sdoc.flybrain import FlyBrain
from sdoc.submission import build_submission

BUNDLE = ROOT / "work" / "bundle"
base = json.load(open(ROOT / "backend/out/submission.json"))
SCR = ROOT / "reviews" / "judge_scratch" / "data"

def load(eid):
    e = json.load(open(BUNDLE / "inbox" / f"{eid}.json"))
    return e
def pairs():
    out = []
    for p in sorted((BUNDLE / "inbox").glob("*.json")):
        e = json.load(open(p))
        a = e.get("attachments", [])
        if len(a) == 2 and all(x.endswith(".txt") for x in a) and base[e["email_id"]]["category"] == "BL_COMPARISON" and base[e["email_id"]]["status"] in ("OK", "MISMATCH"):
            out.append(e)
    return out
PAIRS = pairs()

def build(name, mut, only=None, email_mut=None):
    d = SCR / name
    if d.exists(): shutil.rmtree(d)
    (d / "inbox").mkdir(parents=True); (d / "attachments").mkdir()
    ids = []
    for e in PAIRS:
        si = (BUNDLE / e["attachments"][0]).read_text(encoding="utf-8")
        bl = (BUNDLE / e["attachments"][1]).read_text(encoding="utf-8")
        si2, bl2 = mut(si, bl, e)
        e2 = dict(e)
        if email_mut: e2 = email_mut(e2)
        for a, t in zip(e["attachments"], (si2, bl2)):
            (d / a).parent.mkdir(exist_ok=True, parents=True)
            (d / a).write_text(t, encoding="utf-8")
        (d / "inbox" / f"{e['email_id']}.json").write_text(json.dumps(e2), encoding="utf-8")
        ids.append(e["email_id"])
    return d, ids

async def run(d):
    inbox = Inbox(d)
    pipe = Pipeline(inbox=inbox, gate=FlyBrain.load_or_calibrate(None), default_engine="rules")
    res = {}
    sem = asyncio.Semaphore(8)
    async def one(eid):
        async with sem:
            r, _ = await pipe.run(eid); res[eid] = r
    await asyncio.gather(*[one(i) for i in inbox.ids()])
    return res

def evaluate(name, mut, expect_change=False, email_mut=None, show=6):
    d, ids = build(name, mut, email_mut=email_mut)
    res = asyncio.run(run(d))
    sub = build_submission(res)
    diffs = []
    for i in ids:
        b, s = base[i], sub[i]
        if (b["category"], b["status"], b["review_reason"], sorted(b["defect_fields"])) != (s["category"], s["status"], s["review_reason"], sorted(s["defect_fields"])):
            diffs.append((i, b, s, res[i]))
    print(f"[{name}] n={len(ids)} changed={len(diffs)}")
    for i, b, s, r in diffs[:show]:
        print("   ", i, "base", b["status"], b["defect_fields"], "-> now", s["category"], s["status"], s["review_reason"], s["defect_fields"], "|", (r["headline"] or "")[:110])
    return diffs, res

def sub_label(text, mapping):
    def f(m):
        lab = m.group(1)
        for pat, new in mapping:
            if re.fullmatch(pat, lab.strip(), re.I): return new + m.group(2)
        return m.group(0)
    return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60})(:.*)$", f, text)

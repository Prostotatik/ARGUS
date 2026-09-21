"""DEV-ONLY scoring helper. Calls the organisers' scoring.py against the local ground truth.

NOT part of the shipped runtime: nothing under backend/sdoc imports this or reads ground_truth.json.

    python backend/tools/score_local.py [submission.json] [--write-score] [--errors]

--write-score  writes backend/out/score.json = {"final_score": ...} (the single number the dashboard may show
               as 'accuracy vs labels'). --errors lists every disagreement with the reference.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "work" / "docker" / "server"
GT = ROOT / "work" / "docker" / "data_v2" / "ground_truth.json"
sys.path.insert(0, str(SERVER))
import scoring  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("submission", nargs="?", default=str(ROOT / "backend" / "out" / "submission.json"))
    ap.add_argument("--write-score", action="store_true")
    ap.add_argument("--errors", action="store_true")
    a = ap.parse_args()
    truth = json.loads(GT.read_text(encoding="utf-8"))
    sub = json.loads(Path(a.submission).read_text(encoding="utf-8"))
    r = scoring.score_all(truth, sub)
    print(f"final={r['final_score']:.4f} stage1_macroF1={r['stage1']['macro_f1']:.4f} "
          f"stage3_defectF1={r['stage3']['defect_f1']:.4f} e2e={r['end_to_end']['rate']:.4f} "
          f"esc_recall={r['reliability']['escalation_recall']:.3f} esc_precision={r['reliability']['escalation_precision']:.3f}")
    if a.errors:
        n = 0
        for eid, t in truth.items():
            s = sub.get(eid, {})
            if (s.get("category") != t["category"] or s.get("status") != t["status"]
                    or set(s.get("defect_fields", [])) != set(t["defect_fields"])
                    or s.get("review_reason") != t["review_reason"]):
                n += 1
                print("DIFF", eid, "pred", {k: s.get(k) for k in ("category", "status", "review_reason", "defect_fields")},
                      "gold", {k: t[k] for k in ("category", "status", "review_reason", "defect_fields")})
        print(f"{n} emails differ from the reference")
    if a.write_score:
        out = ROOT / "backend" / "out" / "score.json"
        out.write_text(json.dumps({"final_score": r["final_score"]}), encoding="utf-8")
        print("wrote", out)


if __name__ == "__main__":
    main()

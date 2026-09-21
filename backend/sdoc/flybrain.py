"""Fly-brain confidence gate (numpy). Architecture inspired by the fruit fly's olfactory system.

WHAT THIS IS (and is not)
    A small network of our own, *in the style of* the Drosophila mushroom body:

        input vector (32 "glomeruli")            per-field discrepancy / confidence / anomaly signals
              |  fixed sparse random projection  (each Kenyon cell reads ~3 of 32 inputs, ~9% connectivity)
              v
        Kenyon cells (1600, i.e. 50x expansion)  + APL-style global inhibition + top-k winner-take-all
              |  plastic KC->output weights      (the only learned synapses)
              v
        decision neuron (MBON-like)              suspicion score in [0, 1]  vs. threshold

    It is NOT real fly data, not FlyWire, not a connectome. It uses the same computational idea:
    a sparse, high-dimensional code makes "familiar" and "novel" input patterns land on
    *different* small sets of cells, so a handful of examples suffices to teach "this is normal",
    and a single wrong association can be corrected by touching only the few synapses involved.

WHAT IT DECIDES
    Only escalate-vs-report for the grey zone. It never edits extracted values or the
    match/mismatch outcome. Deterministic triggers (missing attachment, unreadable, wrong doc type,
    blank required value) bypass it and go straight to NEEDS_REVIEW.

LEARNING (dopamine-gated, STDP-like eligibility rule)
    KC->output weights w_j in [0, 1] start at 1 ("everything is novel").
      * calibration / "escalation unneeded" verdict: KCs that were active are depressed
        (w <- w * (1 - eta_dep))   -> this pattern is now familiar.
      * "escalation correct" verdict: active KCs are potentiated (w <- w + eta_pot * (1 - w)).
    "Pre" = KC spike (eligibility), "post" = decision-neuron output, "teacher" = human verdict.
    Because only ~5% of KCs are active per input, an update stays local (measured in tests).

INTERPRETABILITY
    ``explain`` returns the active KCs, the input indices each one reads, the weight of each,
    and per-input drive (which signals pushed the suspicion up).
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .config import FIELDS

# ---------------------------------------------------------------------------
# input layer
# ---------------------------------------------------------------------------
INPUT_NAMES: list[str] = (
    [f"mismatch:{f}" for f in FIELDS]                # 0-6   confident-looking discrepancy on a field
    + [f"low_conf:{f}" for f in FIELDS]              # 7-13  extraction confidence is low
    + [f"near_miss:{f}" for f in FIELDS]             # 14-20 typo-like near-miss
    + [
        "many_mismatches",                           # 21  >=3 fields differ (likely wrong pair of documents)
        "ocr_used",                                  # 22  text recovered by OCR
        "doc_type_low_conf",                         # 23  SI/BL title detection weak
        "classifier_low_conf",                       # 24  classifier unsure it is a BL check
        "unit_converted",                            # 25  kg/MT/lbs conversion applied
        "ambiguous_or_conflicting",                  # 26  ambiguous number/count or two conflicting candidate values
        "internal_inconsistency",                    # 27  document contradicts itself (table vs total)
        "format_normalised",                         # 28  benign normalisation applied (format difference ignored, fuzzy label)
        "engine_fallback",                           # 29  LLM node failed, rules twin used
        "deterministic_trigger",                     # 30  missing attachment / wrong doc type / unreadable / blank value
        "missing_value",                             # 31  required value blank
    ]
)
N_IN = len(INPUT_NAMES)
assert N_IN == 32

DEFAULT_N_KC = 1600          # 50x expansion
DEFAULT_DEGREE = 3           # inputs per KC (3/32 = ~9% connectivity)
DEFAULT_K_FRAC = 0.05        # ~5% of KCs may fire (APL / WTA)
INPUT_FLOOR = 0.25           # receptor-neuron style response floor: weaker input is treated as silence
KC_THRESHOLD = 0.95          # KCs are coincidence detectors: one lone input cannot make a KC spike
APL_GAIN = 0.6               # global inhibition proportional to mean KC current
# Initial KC->decision weight. Deliberately just under 1.0 (not exactly 1.0): a weight already at
# the ceiling cannot be potentiated further, so an "escalation was correct" verdict on a
# never-touched pattern would be a silent, visually-confusing no-op (0.63 -> 0.63). Starting at
# 0.9 keeps "everything is novel" (still saturating almost immediately) while leaving real,
# visible headroom for LTP on the very first confirmation of any pattern.
DEFAULT_INIT_W = 0.9


def build_input_vector(fields: Sequence[Mapping[str, Any]], *, classifier_conf: float = 1.0,
                       doc_type_conf: float = 1.0, ocr_used: bool = False, engine_fallback: bool = False,
                       doc_trigger: bool = False) -> np.ndarray:
    """Turn the pipeline's per-field results + doc-level metadata into the 32-d input vector."""
    x = np.zeros(N_IN, dtype=np.float64)
    by = {f["field"]: f for f in fields}
    n_mis = 0
    fmt_note = False
    any_flags: set[str] = set()
    for i, name in enumerate(FIELDS):
        f = by.get(name)
        if not f:
            continue
        flags = set(f.get("flags") or [])
        any_flags |= flags
        state = f.get("state")
        conf = float(f.get("confidence") or 0.0)
        if state == "mismatch":
            x[i] = 1.0
            n_mis += 1
        if state != "missing":
            x[7 + i] = float(np.clip((0.95 - conf) / 0.55, 0.0, 1.0))
        if f.get("near_miss"):
            x[14 + i] = 1.0
        elif state == "match" and f.get("note"):
            fmt_note = True
    # >=3 confident mismatches is only a "genuinely uncertain pair of documents" signal when at
    # least one of those mismatches is itself shaky (near-miss/typo-like or low extraction
    # confidence); three clean, high-confidence mismatches are a confirmed multi-field defect,
    # not an anomaly to gate-escalate away from the report (previously this fired on count alone,
    # which could trade a caught real defect for an unnecessary review - see reviews/developer.md).
    shaky_mismatch = any(x[i] == 1.0 and (x[14 + i] == 1.0 or x[7 + i] > 0.3) for i in range(7))
    x[21] = 1.0 if (n_mis >= 3 and shaky_mismatch) else 0.0
    x[22] = 1.0 if ocr_used or "ocr" in any_flags else 0.0
    x[23] = float(np.clip((0.8 - doc_type_conf) / 0.3, 0.0, 1.0))
    x[24] = float(np.clip((0.8 - classifier_conf) / 0.4, 0.0, 1.0))
    x[25] = 1.0 if "unit_converted" in any_flags else 0.0
    x[26] = 1.0 if ({"ambiguous", "conflict"} & any_flags) else 0.0
    x[27] = 1.0 if "inconsistent" in any_flags else 0.0
    x[28] = 0.5 if (fmt_note or "fuzzy_label" in any_flags) else 0.0
    x[29] = 1.0 if engine_fallback else 0.0
    x[30] = 1.0 if doc_trigger else 0.0
    x[31] = 1.0 if any(f.get("state") == "missing" for f in fields) else 0.0
    return x


# ---------------------------------------------------------------------------
@dataclass
class GateDecision:
    suspicion: float
    threshold: float
    escalate: bool
    kc_active: list[int]
    winner_kc: int | None
    drivers: list[dict]
    reason: str
    input_vector: list[float]

    def to_payload(self) -> dict:
        return {
            "suspicion": round(self.suspicion, 4),
            "threshold": round(self.threshold, 4),
            "escalate": bool(self.escalate),
            "reason": self.reason,
            "input_vector": [round(float(v), 3) for v in self.input_vector],
            "kc_active": [int(k) for k in self.kc_active],
            "winner_kc": None if self.winner_kc is None else int(self.winner_kc),
            "drivers": self.drivers,
        }


class FlyBrain:
    """Sparse expansion + winner-take-all + one plastic decision neuron."""

    def __init__(self, n_in: int = N_IN, n_kc: int = DEFAULT_N_KC, degree: int = DEFAULT_DEGREE,
                 k_frac: float = DEFAULT_K_FRAC, seed: int = 7, threshold: float = 0.25,
                 eta_dep: float = 0.6, eta_pot: float = 0.5) -> None:
        self.n_in, self.n_kc, self.degree, self.k_frac, self.seed = n_in, n_kc, degree, k_frac, seed
        self.k = max(1, int(round(k_frac * n_kc)))
        self.tau = 0.15 * self.k                       # decision-neuron saturation scale
        self.threshold = float(threshold)
        self.eta_dep, self.eta_pot = float(eta_dep), float(eta_pot)
        rng = np.random.default_rng(seed)
        # fixed sparse random projection: each KC reads `degree` distinct inputs
        self.proj = np.stack([rng.choice(n_in, size=degree, replace=False) for _ in range(n_kc)]).astype(np.int32)
        # fixed per-KC excitability offset (also breaks ties deterministically)
        self.kc_bias = rng.uniform(0.0, 0.08, size=n_kc)
        self.w = np.full(n_kc, DEFAULT_INIT_W, dtype=np.float64)  # plastic KC -> decision-neuron weights
        self.history: list[dict] = []
        self.calibration: dict = {}

    # -- forward pass ----------------------------------------------------
    @staticmethod
    def _floor(x: np.ndarray) -> np.ndarray:
        x = np.asarray(x, dtype=np.float64)
        return np.where(x < INPUT_FLOOR, 0.0, x)

    def _active(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        x = self._floor(x)
        cur = x[self.proj].sum(axis=1)                              # KC input current
        inhibition = APL_GAIN * float(cur.mean())                   # APL: global feedback inhibition
        drive = cur - self.kc_bias - KC_THRESHOLD - inhibition
        cand = np.flatnonzero(drive > 0)
        if cand.size == 0:
            return cand, cur
        if cand.size > self.k:                                      # winner-take-all: top-k by drive
            top = np.argpartition(-drive[cand], self.k - 1)[: self.k]
            cand = cand[top]
        return np.sort(cand), cur

    def _sus(self, act: np.ndarray) -> float:
        """Decision-neuron output: saturating function of the summed KC->output drive.
        Counting *novel* (undepressed) cells in absolute terms keeps a few novel cells from being
        diluted by the many familiar ones that share the active set."""
        if act.size == 0:
            return 0.0
        return float(1.0 - math.exp(-float(self.w[act].sum()) / self.tau))

    def suspicion(self, x: np.ndarray) -> float:
        act, _ = self._active(np.asarray(x, dtype=np.float64))
        return self._sus(act)

    def explain(self, x: np.ndarray, top: int = 5) -> tuple[list[int], int | None, list[dict], float]:
        x = self._floor(x)
        act, cur = self._active(x)
        if act.size == 0:
            return [], None, [], 0.0
        contrib = self.w[act]
        s = self._sus(act)
        winner = int(act[int(np.argmax(contrib * cur[act]))])
        drive = np.zeros(self.n_in)
        for j, c in zip(act, contrib):
            for i in self.proj[j]:
                drive[i] += c * x[i]
        tot = drive.sum()
        drivers = []
        if tot > 0:
            for i in np.argsort(-drive)[:top]:
                if drive[i] <= 0:
                    break
                drivers.append({"input": INPUT_NAMES[int(i)], "index": int(i), "share": round(float(drive[i] / tot), 3)})
        return [int(a) for a in act], winner, drivers, s

    def decide(self, x: Sequence[float] | np.ndarray, *, deterministic_reason: str | None = None) -> GateDecision:
        x = np.asarray(x, dtype=np.float64)
        act, winner, drivers, s = self.explain(x)
        esc = s >= self.threshold
        if deterministic_reason:
            reason = f"deterministic trigger ({deterministic_reason}) - sent to review without needing the gate; " \
                     f"fly-net suspicion {s:.2f} logged for learning"
            esc = True
        elif esc:
            top = ", ".join(f"{d['input']} ({int(d['share'] * 100)}%)" for d in drivers[:3]) or "novel input pattern"
            reason = f"novel/uncertain input pattern (suspicion {s:.2f} >= {self.threshold:.2f}); main drivers: {top}"
        elif act:
            reason = f"familiar pattern - {len(act)} Kenyon cells fired, mostly depressed (suspicion {s:.2f} < {self.threshold:.2f})"
        else:
            reason = "clean pattern - no Kenyon cell crossed threshold (suspicion 0.00)"
        return GateDecision(s, self.threshold, esc, act, winner, drivers, reason, [float(v) for v in x])

    # -- learning --------------------------------------------------------
    def learn(self, x: Sequence[float] | np.ndarray, verdict: str, *, note: str | None = None,
              record: bool = True) -> dict:
        """Human-verdict update. verdict: 'escalation_unneeded' | 'escalation_correct'.
        Returns per-KC before/after weights for the cells that actually changed (not just the
        aggregate suspicion), so a caller (e.g. POST /api/review) can show the real update
        directly without a second GET /api/flybrain round trip (innovator.md request #2)."""
        x = np.asarray(x, dtype=np.float64)
        act, _ = self._active(x)
        w_before = self.w[act].copy() if act.size else np.zeros(0)
        before = self._sus(act)
        if act.size:
            if verdict == "escalation_unneeded":
                self.w[act] *= (1.0 - self.eta_dep)               # LTD on the eligible synapses
            elif verdict == "escalation_correct":
                self.w[act] += self.eta_pot * (1.0 - self.w[act])  # LTP
            else:
                raise ValueError(f"unknown verdict {verdict!r}")
        w_after = self.w[act].copy() if act.size else np.zeros(0)
        after = self._sus(act)
        ev = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "before": round(before, 4), "after": round(after, 4),
              "verdict": verdict, "n_kc_updated": int(act.size), "note": note,
              "kc_active": [int(a) for a in act],
              "kc_weights_before": [round(float(v), 4) for v in w_before],
              "kc_weights_after": [round(float(v), 4) for v in w_after]}
        if record:
            self.history.append(ev)
        return ev

    def familiarise(self, x: np.ndarray, eta: float = 0.35) -> None:
        act, _ = self._active(x)
        if act.size:
            self.w[act] *= (1.0 - eta)

    # -- calibration -----------------------------------------------------
    def calibrate(self, seed: int = 123, n_train: int = 2500, n_val: int = 1000, n_anom: int = 200) -> dict:
        """Teach 'normal' from synthetic normal vectors (unsupervised familiarity), set the threshold
        from a held-out normal set, then report recall on held-out synthetic anomalies (never trained on)."""
        rng = np.random.default_rng(seed)
        self.w[:] = DEFAULT_INIT_W
        for _ in range(n_train):
            self.familiarise(synthetic_normal(rng), 0.6)
        val = np.array([self.suspicion(synthetic_normal(rng)) for _ in range(n_val)])
        # threshold: above the 99.5th percentile of held-out normal suspicion, kept in a sane band
        thr = float(np.clip(np.quantile(val, 0.995) + 0.03, 0.08, 0.5))
        self.threshold = round(thr, 3)
        per: dict[str, dict] = {}
        tot_hit = tot = 0
        for kind in ANOMALY_KINDS:
            hits = 0
            for _ in range(n_anom):
                hits += int(self.suspicion(synthetic_anomaly(rng, kind)) >= self.threshold)
            per[kind] = {"n": n_anom, "escalated": hits, "recall": round(hits / n_anom, 3)}
            tot_hit += hits
            tot += n_anom
        fpr = float(np.mean([self.suspicion(synthetic_normal(rng)) >= self.threshold for _ in range(n_val)]))
        self.calibration = {
            "method": "unsupervised familiarity learning on synthetic normal vectors + held-out threshold; "
                      "anomalies used only for evaluation",
            "seed": seed, "n_train_normal": n_train, "n_heldout_normal": n_val, "n_anomalies_per_kind": n_anom,
            "threshold": self.threshold,
            "heldout_normal_false_escalation_rate": round(fpr, 4),
            "anomaly_recall_overall": round(tot_hit / tot, 3),
            "anomaly_recall_by_kind": per,
            "normal_suspicion_p50_p99": [round(float(np.quantile(val, 0.5)), 4), round(float(np.quantile(val, 0.99)), 4)],
        }
        self.history = []
        return self.calibration

    # -- persistence / public view --------------------------------------
    def to_state(self) -> dict:
        return {"version": 1, "n_in": self.n_in, "n_kc": self.n_kc, "degree": self.degree, "k_frac": self.k_frac,
                "seed": self.seed, "threshold": self.threshold, "eta_dep": self.eta_dep, "eta_pot": self.eta_pot,
                "weights": [round(float(v), 6) for v in self.w], "history": self.history[-500:],
                "calibration": self.calibration}

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_state()), encoding="utf-8")
        tmp.replace(p)

    @classmethod
    def from_state(cls, st: Mapping[str, Any]) -> "FlyBrain":
        fb = cls(n_in=st["n_in"], n_kc=st["n_kc"], degree=st["degree"], k_frac=st["k_frac"], seed=st["seed"],
                 threshold=st["threshold"], eta_dep=st.get("eta_dep", 0.6), eta_pot=st.get("eta_pot", 0.5))
        fb.w = np.asarray(st["weights"], dtype=np.float64)
        fb.history = list(st.get("history", []))
        fb.calibration = dict(st.get("calibration", {}))
        return fb

    @classmethod
    def load_or_calibrate(cls, path: str | Path | None = None, *, persist: bool = True) -> "FlyBrain":
        if path:
            p = Path(path)
            if p.is_file():
                try:
                    return cls.from_state(json.loads(p.read_text(encoding="utf-8")))
                except Exception:  # noqa: BLE001 - corrupt state -> recalibrate
                    pass
        fb = cls()
        fb.calibrate()
        if path and persist:
            fb.save(path)
        return fb

    def public(self) -> dict:
        """Payload for GET /api/flybrain (CONTRACT.md) plus extras."""
        return {
            "n_inputs": self.n_in, "n_kc": self.n_kc, "kc_sparsity": self.k_frac,
            "connectivity": round(self.degree / self.n_in, 3), "threshold": self.threshold,
            "eta_dep": self.eta_dep, "eta_pot": self.eta_pot, "tau": round(self.tau, 4),
            "init_w": DEFAULT_INIT_W,
            "projection": self.proj.tolist(), "weights": [round(float(v), 4) for v in self.w],
            "history": self.history[-100:], "input_names": INPUT_NAMES,
            "calibration": self.calibration,
            "description": "Architecture inspired by the fruit fly's olfactory system: sparse random projection "
                           "-> Kenyon cells with global (APL-style) inhibition / winner-take-all -> one decision "
                           "neuron with human-verdict-gated plasticity. Our own small network; not real fly data.",
        }


# ---------------------------------------------------------------------------
# synthetic data for calibration (documented in README)
# ---------------------------------------------------------------------------
ANOMALY_KINDS = [
    "low_conf_mismatch", "low_conf_only", "near_miss_typo", "ocr_text", "many_mismatches",
    "inconsistent_document", "ambiguous_parse", "engine_fallback_low_conf", "weak_doc_type", "doc_trigger",
]


def synthetic_normal(rng: np.random.Generator) -> np.ndarray:
    """A 'normal' pipeline outcome: 0-2 confident mismatches, high confidence, minor benign noise."""
    x = np.zeros(N_IN)
    n_mis = int(rng.choice([0, 1, 2], p=[0.50, 0.38, 0.12]))
    for i in rng.choice(7, size=n_mis, replace=False):
        x[i] = 1.0
    for i in range(7):                                    # mild confidence wobble, still 'confident'
        if rng.random() < 0.10:
            x[7 + i] = rng.uniform(0.0, 0.12)
    if rng.random() < 0.12:                               # benign formatting difference ignored
        x[28] = 0.5
    if rng.random() < 0.05:
        x[25] = 1.0                                       # kg <-> MT conversion
    if rng.random() < 0.06:
        x[28] = 0.5                                       # fuzzy label alignment (benign)
    if rng.random() < 0.04:
        x[24] = rng.uniform(0.0, 0.15)
    if rng.random() < 0.10:
        x[29] = 1.0                                       # Gemini node failed, rules twin gave a confident answer
    return x


def synthetic_anomaly(rng: np.random.Generator, kind: str) -> np.ndarray:
    x = np.zeros(N_IN)
    f = int(rng.integers(0, 7))
    if kind == "low_conf_mismatch":
        x[f] = 1.0
        x[7 + f] = rng.uniform(0.55, 1.0)
    elif kind == "low_conf_only":
        x[7 + f] = rng.uniform(0.6, 1.0)
        x[7 + (f + 2) % 7] = rng.uniform(0.3, 0.8)
    elif kind == "near_miss_typo":
        x[f] = 1.0
        x[14 + f] = 1.0
    elif kind == "ocr_text":
        x[22] = 1.0
        x[7 + f] = rng.uniform(0.3, 0.9)
        if rng.random() < 0.5:
            x[int(rng.integers(0, 7))] = 1.0
    elif kind == "many_mismatches":
        for i in rng.choice(7, size=int(rng.integers(3, 6)), replace=False):
            x[i] = 1.0
        x[21] = 1.0
    elif kind == "inconsistent_document":
        x[27] = 1.0
        x[f] = 1.0
        x[7 + f] = rng.uniform(0.25, 0.6)
    elif kind == "ambiguous_parse":
        x[26] = 1.0
        x[5 + int(rng.integers(0, 2))] = 1.0
        x[7 + 5 + int(rng.integers(0, 2))] = rng.uniform(0.3, 0.8)
    elif kind == "engine_fallback_low_conf":
        x[29] = 1.0
        x[f] = 1.0
        x[7 + f] = rng.uniform(0.4, 0.9)
    elif kind == "weak_doc_type":
        x[23] = rng.uniform(0.6, 1.0)
        x[24] = rng.uniform(0.3, 0.9)
        x[f] = 1.0
    elif kind == "doc_trigger":
        x[30 + int(rng.integers(0, 2))] = 1.0
        x[7 + f] = rng.uniform(0.3, 1.0)
    else:
        raise ValueError(kind)
    return x

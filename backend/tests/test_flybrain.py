import numpy as np

from sdoc.flybrain import (ANOMALY_KINDS, INPUT_NAMES, N_IN, FlyBrain, build_input_vector, synthetic_anomaly,
                           synthetic_normal)


def calibrated():
    fb = FlyBrain()
    fb.calibrate(n_train=1500, n_val=300, n_anom=60)
    return fb


def test_architecture_numbers():
    fb = FlyBrain()
    assert fb.n_kc / fb.n_in == 50
    assert fb.proj.shape == (1600, 3) and 0.05 <= fb.degree / fb.n_in <= 0.10
    assert len(INPUT_NAMES) == N_IN
    x = np.zeros(N_IN)
    x[[0, 8, 22]] = 1
    act, _ = fb._active(x)
    assert 0 < len(act) <= fb.k            # winner-take-all cap


def test_clean_input_is_silent_and_deterministic():
    fb = calibrated()
    d = fb.decide(np.zeros(N_IN))
    assert d.suspicion == 0.0 and not d.escalate and d.kc_active == []
    x = synthetic_anomaly(np.random.default_rng(1), "ocr_text")
    assert fb.decide(x).suspicion == fb.decide(x).suspicion


def test_calibration_separates_normal_from_anomalies():
    fb = calibrated()
    rng = np.random.default_rng(999)
    fpr = np.mean([fb.decide(synthetic_normal(rng)).escalate for _ in range(300)])
    rec = np.mean([fb.decide(synthetic_anomaly(rng, k)).escalate for k in ANOMALY_KINDS for _ in range(30)])
    assert fpr <= 0.02 and rec >= 0.9
    assert fb.calibration["anomaly_recall_overall"] >= 0.9


def test_learning_direction_and_locality():
    fb = calibrated()
    rng = np.random.default_rng(5)
    x = synthetic_anomaly(rng, "near_miss_typo")
    other = synthetic_anomaly(rng, "ocr_text")
    s0, o0 = fb.suspicion(x), fb.suspicion(other)
    assert s0 >= fb.threshold
    ev = fb.learn(x, "escalation_unneeded")                 # human: escalation was unnecessary
    s1, o1 = fb.suspicion(x), fb.suspicion(other)
    assert s1 < s0 and ev["after"] < ev["before"]           # familiar now
    assert o1 >= 0.5 * o0                                   # unrelated pattern largely untouched (sparse update)
    fb.learn(x, "escalation_correct")                       # human: it WAS suspicious
    assert fb.suspicion(x) > s1


def test_repeated_unneeded_verdicts_stop_escalation():
    fb = calibrated()
    x = synthetic_anomaly(np.random.default_rng(7), "low_conf_mismatch")
    for _ in range(6):
        if not fb.decide(x).escalate:
            break
        fb.learn(x, "escalation_unneeded")
    assert not fb.decide(x).escalate


def test_persistence_roundtrip(tmp_path):
    fb = calibrated()
    x = synthetic_anomaly(np.random.default_rng(3), "many_mismatches")
    fb.learn(x, "escalation_unneeded")
    p = tmp_path / "fb.json"
    fb.save(p)
    fb2 = FlyBrain.load_or_calibrate(p)
    assert np.allclose(fb.w, fb2.w, atol=1e-5) and fb2.threshold == fb.threshold and len(fb2.history) == 1


def test_explain_reports_drivers():
    fb = calibrated()
    x = synthetic_anomaly(np.random.default_rng(2), "near_miss_typo")
    d = fb.decide(x)
    assert d.kc_active and d.winner_kc in d.kc_active and d.drivers
    assert all(0 < dr["share"] <= 1 for dr in d.drivers)


def test_input_vector_from_pipeline_fields():
    def f(name, state, conf=0.98):
        return {"field": name, "state": state, "confidence": conf, "flags": [], "note": None, "near_miss": False}

    fields = [f("shipper", "match"), f("consignee", "mismatch"), f("notify_party", "missing", 0.0)]
    x = build_input_vector(fields, ocr_used=True)
    assert x[1] == 1 and x[22] == 1 and x[31] == 1 and x[0] == 0

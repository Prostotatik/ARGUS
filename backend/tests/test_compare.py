import pytest

from sdoc import compare as cmp
from sdoc import normalize as nz
from sdoc.rules_extract import Extracted


def ex(v, conf=0.98, flags=None):
    return Extracted(field="x", value=v, evidence=str(v), confidence=conf, flags=flags or [])


def match(field, a, b):
    return cmp.compare_field(field, ex(a), ex(b))


# -- names: format noise ignored, real differences caught ------------------
@pytest.mark.parametrize("a,b", [
    ("VITAL SOLUTIONS PTE. LTD.", "Vital Solutions Pte Ltd"),
    ("KTP CO., LTD", "KTP CO LTD"),
    ("BALL & DOGGETT AUSTRALIA PTY LTD", "Ball and Doggett Australia Pty. Ltd."),
    ("SAFQA LIMITED", "SAFQA LTD"),
    ("ROXCEL TRADING GMBH", "roxcel trading gmbh"),
])
def test_name_format_noise_is_not_a_mismatch(a, b):
    assert match("consignee", a, b)["match"] is True


@pytest.mark.parametrize("a,b", [
    ("SAFQA LIMITED", "HABRAS INTERNATIONAL LIMITED"),
    ("APRIL FINE PAPER TRADING", "APRIL FINE PAPER TRADING (MIDDLE EAST) FZE"),
    ("APRIL FAR EAST (M) SDN BHD", "APRIL FINE PAPER TRADING"),
    ("KTP CO., LTD", "KPP CO., LTD"),
])
def test_real_name_differences_are_caught(a, b):
    assert match("shipper", a, b)["match"] is False


# -- ports -----------------------------------------------------------------
def test_port_country_and_unlocode_ignored():
    assert match("port_of_loading", "NANTONG, CHINA (CNNTG)", "Nantong")["match"]
    assert match("port_of_loading", "Port Klang (Westport), Malaysia", "PORT KLANG (WESTPORT)")["match"]
    assert match("port_of_discharge", "JEBEL ALI, UAE", "AEJEA")["match"]
    assert match("port_of_discharge", "Ho Chi Minh City", "HOCHIMINH CITY, VIETNAM")["match"]


def test_port_real_difference():
    r = match("port_of_discharge", "MOMBASA, KENYA (KEMBA)", "TUTICORIN, INDIA (KEMBA)")
    assert r["match"] is False       # same trailing code text must not hide a different port


# -- container count ---------------------------------------------------------
@pytest.mark.parametrize("a,b,ok", [
    ("2 x 40HC", "2X40'HC", True),
    ("3 x 40'HC", "3", True),
    ("TWO (2)", "2 containers", True),
    ("1 x 20' + 2 x 40HC", "3 x 40HC", True),
    ("3 x 40'HC", "4 x 40'HC", False),
])
def test_container_counts(a, b, ok):
    assert match("container_count", a, b)["match"] is ok


# -- weight: units and separators --------------------------------------------
@pytest.mark.parametrize("a,b,ok", [
    ("22,000 KG", "22000", True),
    ("22,000 KG", "22.0 MT", True),
    ("22,000.00 KGS", "22 MT", True),
    ("48,502 KG", "106,924 LBS", True),
    ("131,058 KG", "130,558 KG", False),
    ("22,000 KG", "23,000 KG", False),
    ("22,000 KG", "22 LBS", False),
])
def test_weights(a, b, ok):
    assert match("gross_weight_kg", a, b)["match"] is ok


# -- decision semantics --------------------------------------------------------
def _fields(**over):
    base = {f: (ex("A"), ex("A")) for f in ["shipper", "consignee", "notify_party", "port_of_loading", "port_of_discharge"]}
    base["container_count"] = (ex("3 x 40HC"), ex("3 x 40HC"))
    base["gross_weight_kg"] = (ex("22,000 KG"), ex("22,000 KG"))
    base.update(over)
    return [cmp.compare_field(f, s, b) for f, (s, b) in base.items()]


def test_all_match_is_ok():
    d = cmp.decide(_fields())
    assert d["status"] == "OK" and d["headline"] == "No mismatch detected" and not d["has_defect"]


def test_example_from_use_case_container_count_only():
    d = cmp.decide(_fields(container_count=(ex("3 x 40HC"), ex("4 x 40HC"))))
    assert d["status"] == "MISMATCH" and d["defect_fields"] == ["container_count"]
    assert "SI 3 / BL 4" in d["headline"]


def test_blank_is_missing_value_not_mismatch():
    d = cmp.decide(_fields(consignee=(ex("???"), ex("ACME LTD"))))
    assert d["status"] == "NEEDS_REVIEW" and d["review_reason"] == "missing_value" and d["defect_fields"] == []
    d = cmp.decide(_fields(port_of_loading=(ex("TBA"), ex("SINGAPORE"))))
    assert d["review_reason"] == "missing_value"


def test_preflight_reason_wins():
    d = cmp.decide(_fields(), preflight_reason="unreadable", preflight_detail="x.pdf")
    assert d["status"] == "NEEDS_REVIEW" and d["review_reason"] == "unreadable"


def test_normalize_helpers():
    assert nz.is_blank("_______") and nz.is_blank("N/A") and nz.is_blank("??? KG") and not nz.is_blank("SINGAPORE")
    assert nz.parse_container_count("six").count == 6

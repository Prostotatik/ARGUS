import sys, os
sys.path.insert(0, r"E:/Projects/Averis x Monash/backend")
from sdoc.docparse import parse_document
from sdoc.rules_extract import extract_field
from sdoc import compare as cmp

FIELDS = ["shipper","consignee","notify_party","port_of_loading","port_of_discharge","container_count","gross_weight_kg"]

si_path = "data/fresh_scan/SI_fresh.pdf"
bl_path = "data/fresh_scan/BL_fresh.pdf"

si = parse_document(si_path)
bl = parse_document(bl_path)
print("SI ocr_used=", si.ocr_used, "type_confidence=", si.type_confidence, "role guess=", getattr(si, 'role', None))
print("SI text sample:", si.text[:200].replace("\n","|"))
print("BL ocr_used=", bl.ocr_used)
print("BL text sample:", bl.text[:200].replace("\n","|"))

fields = []
for f in FIELDS:
    s = extract_field(si, f)
    b = extract_field(bl, f)
    fr = cmp.compare_field(f, s, b)
    fields.append(fr)
    print(f, "| SI:", repr(s.value), "conf", round(s.confidence,2), "| BL:", repr(b.value), "conf", round(b.confidence,2), "| match=", fr["match"])

decision = cmp.decide(fields)
print("DECISION:", decision["status"], decision.get("review_reason"), decision.get("has_defect"), decision.get("defect_fields"))

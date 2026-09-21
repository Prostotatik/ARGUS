import sys
sys.path.insert(0, r"E:/Projects/Averis x Monash/backend")
from sdoc.docparse import parse_document
from sdoc.rules_extract import extract_field
from sdoc import compare as cmp

FIELDS = ["shipper","consignee","notify_party","port_of_loading","port_of_discharge","container_count","gross_weight_kg"]
si = parse_document("data/fresh_scan2/SI2.pdf")
bl = parse_document("data/fresh_scan2/BL2.pdf")
print("ocr_used si/bl:", si.ocr_used, bl.ocr_used)
fields = []
for f in FIELDS:
    s = extract_field(si, f); b = extract_field(bl, f)
    fr = cmp.compare_field(f, s, b)
    fields.append(fr)
    print(f, "| SI:", repr(s.value), "| BL:", repr(b.value), "| match=", fr["match"])
decision = cmp.decide(fields)
print("DECISION:", decision["status"], decision.get("review_reason"), decision.get("has_defect"), decision.get("defect_fields"))

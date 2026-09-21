from perturb import *
FIELD_LABEL_RE = {
 "shipper": r"(Shipper|SHIPPER|Shipper/Exporter|Shipper \(Principal or Seller\))",
 "consignee": r"(Consignee|CONSIGNEE|Consignee \(Non-Negotiable\)|To the Order of)",
 "notify": r"(Notify|Notify Party|NOTIFY PARTY|Notify Party/Intermediate Consignee)",
 "pol": r"(Port of Loading|PORT OF LOADING|POL|Port of Loading \(POL\)|Load Port)",
 "pod": r"(Port of Discharge|PORT OF DISCHARGE|POD|Port of Discharge \(POD\)|Discharge Port)",
 "cnt": r"(No\. of Containers|No\. of Containers or Packages|Total Containers|Container Count)",
 "wt": r"(Gross Weight毛重\(KGS\)|Gross Wt \(kgs\)|GROSS WEIGHT|Gross Weight \(KG\))",
}
ALTS = {
 "shipper": ["Shipper Name & Address","Shipper / Consignor","Sender","Exporter Name","SHIPPER (EXPORTER)","Shipper Details","Party: Shipper","Shipper Company"],
 "consignee": ["Consignee Name & Address","Consigned To","Consignee / Buyer","Receiver","CONSIGNEE (NON-NEGOTIABLE)","Consignee Details","Buyer","Ship To"],
 "notify": ["Notify Party Name","Notify Party / Address","Also Notify","NOTIFY","Notify (Intermediate Consignee)","Notify Party Details","Notifying party","Notify Contact"],
 "pol": ["Loading Port / Place of Receipt","Port Loading","Origin Port","Port of Origin","Place of Loading","Port of Shipment","LOAD PORT (POL)","POL (Port of Loading)","Loading Port","From Port","Departure Port","Port of Load"],
 "pod": ["Port Discharge","Final Destination","Destination Port","Port of Delivery","Port of Destination","DISCHARGE PORT (POD)","POD (Port of Discharge)","Discharging Port","Unloading Port","Arrival Port","Port of Unloading","Place of Delivery"],
 "cnt": ["Number of Containers","Container Qty.","Containers/Packages","No. of Cntrs","Total No. of Containers","Qty of Containers","Containers Total","Total Cntrs","Number of Cntr","Equipment Count","No of Containers","CONTAINER QUANTITY"],
 "wt": ["Gross Weight (kgs)","G.W. (KGS)","Total G.W.","Gross Weight of Cargo","Cargo Gross Weight","Total Gross Weight","GW","Gross Mass","Gross Wt.","Gr. Wt (KG)","Weight (Gross)","Gross Weight, KGS","Total Gross Wt","Gross Weight in KGS","Weight"],
}
# subset of pairs for speed
import perturb
perturb.PAIRS = perturb.PAIRS[:30]
def mk(field, alt, only_side=None):
    pat = FIELD_LABEL_RE[field]
    def m(si, bl, e):
        def rep(t):
            return re.sub(r"(?m)^" + pat + r"(?=[:\s])", alt, t, count=1) if False else re.sub(r"(?m)^" + pat + r"(?=:)", alt, t)
        return rep(si), rep(bl)
    return m
tot = {}
for fld, alts in ALTS.items():
    bad = []
    for a in alts:
        d, ids = build("alt_"+fld, mk(fld, a))
        res = asyncio.run(run(d)); sub = build_submission(res)
        ch = [i for i in ids if (base[i]["status"], sorted(base[i]["defect_fields"])) != (sub[i]["status"], sorted(sub[i]["defect_fields"]))]
        kinds = {}
        for i in ch:
            k = (base[i]["status"], "->", sub[i]["status"], sub[i]["review_reason"], tuple(sub[i]["defect_fields"]) != tuple(base[i]["defect_fields"]))
            kinds[k] = kinds.get(k, 0) + 1
        print(f"{fld:10s} {a!r:42s} changed {len(ch)}/{len(ids)} {kinds}")

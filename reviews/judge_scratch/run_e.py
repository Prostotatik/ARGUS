from perturb import *
import perturb
perturb.PAIRS = perturb.PAIRS[:60]
exec(open("run_d.py").read().split("def new_defect")[1].split("new_defect(")[0].join(["def new_defect",""]) if False else "")
def typo(si, bl, e):
    def rep(m):
        v=m.group(2); j=len(v)//2; return m.group(1)+v[:j]+("X" if v[j]!="X" else "Y")+v[j+1:]
    return si, re.sub(r"(?m)^((?:Consignee[^:\n]*|CONSIGNEE|To the Order of):\s*)(.+)$", rep, bl, count=1)
d, ids = build("typo", typo); res = asyncio.run(run(d))
from collections import Counter
c=Counter()
for i in ids:
    r=res[i]; nm=sum(1 for f in (base[i]["defect_fields"])) 
    c[(base[i]["status"], len(base[i]["defect_fields"]), r["status"], (r["gate"] or {}).get("escalate"), len(r["defect_fields"]))]+=1
for k,v in sorted(c.items(), key=str): print(k,v)
# show gate on a clean OK email with a typo
for i in ids:
    if base[i]["status"]=="OK":
        r=res[i]; g=r["gate"]; print(i, r["status"], g["suspicion"], g["threshold"], g["escalate"], [ (f["field"],f["near_miss"],f["note"]) for f in r["fields"] if f["state"]=="mismatch"]); break

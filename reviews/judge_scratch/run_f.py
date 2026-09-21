from perturb import *
import perturb, numpy as np
perturb.PAIRS = perturb.PAIRS[:80]
def typo(si, bl, e):
    def rep(m):
        v=m.group(2); j=len(v)//2; return m.group(1)+v[:j]+("X" if v[j]!="X" else "Y")+v[j+1:]
    return si, re.sub(r"(?m)^((?:Consignee[^:\n]*|CONSIGNEE|To the Order of):\s*)(.+)$", rep, bl, count=1)
d, ids = build("typo2", typo)
inbox = Inbox(d); gate = FlyBrain.load_or_calibrate(None)
pipe = Pipeline(inbox=inbox, gate=gate, default_engine="rules")
async def go():
    out={}
    for i in ids:
        r,_=await pipe.run(i); out[i]=r
    return out
res = asyncio.run(go())
esc=[i for i in ids if res[i]["gate"] and res[i]["gate"]["escalate"] and res[i]["gate"].get("decided_by")=="flynet"]
print("escalated", len(esc), "of", len(ids))
vecs={i:np.array(res[i]["gate"]["input_vector"]) for i in esc}
s0={i:res[i]["gate"]["suspicion"] for i in esc}
print("suspicion before: mean", np.mean(list(s0.values())), "min", min(s0.values()), "thr", gate.threshold)
# teach unneeded on first 3
for i in esc[:3]:
    print("teach", i, gate.learn(list(vecs[i]), "escalation_unneeded", note="judge"))
after={i:gate.decide(vecs[i]).suspicion for i in esc}
print("first3 after:", [round(after[i],3) for i in esc[:3]])
rest=[after[i] for i in esc[3:]]
print("rest still escalate:", sum(a>=gate.threshold for a in rest), "of", len(rest), "mean suspicion", np.mean(rest))
# unrelated: an OK clean email & a real mismatch remain not escalated?
print("threshold", gate.threshold)
# forget test: teach 'correct' on a totally different clean pattern
print("---- few-shot curve on a single pattern")
gate2 = FlyBrain.load_or_calibrate(None)
i=esc[0]; v=list(vecs[i])
for n in range(1,8):
    gate2.learn(v,"escalation_unneeded",note="j"); s=gate2.decide(np.array(v)).suspicion
    others=[gate2.decide(vecs[j]).suspicion>=gate2.threshold for j in esc[1:]]
    print(n, round(s,3), "same pattern escalates:", s>=gate2.threshold, "| other typo vectors still escalating:", sum(others), "/", len(others))
    if s<gate2.threshold: break

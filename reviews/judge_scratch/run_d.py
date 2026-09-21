from perturb import *
import perturb, random
perturb.PAIRS = perturb.PAIRS[:40]
rnd = random.Random(3)
def trunc(frac):
    def m(si, bl, e): return si, bl[:int(len(bl)*frac)]
    return m
for f in (0.9,0.7,0.5,0.3): evaluate(f"trunc_bl_{f}", trunc(f), show=3)
# truncated mid-value: cut BL right after "Gross Weight...: 22,"  (mid number)
def midnum(si, bl, e):
    m = re.search(r"(?m)^(Gross[^\n:]*:\s*\d)", bl) or re.search(r"(?m)^(GROSS[^\n:]*:\s*\d)", bl) or re.search(r"(?m)^(Gross[^\n]*?\s{2,}\d)", bl)
    return si, (bl[:m.end()] if m else bl)
evaluate("cut_mid_weight", midnum, show=3)
def garbage(si, bl, e):
    return si, "".join(chr(rnd.randint(1,255)) for _ in range(600))
evaluate("garbage_bl", garbage, show=2)
def binary(si, bl, e): return si, "%PDF-1.4\x00\x00\x00binary"
evaluate("binary_bl", binary, show=2)
def blank_lines(si, bl, e): return si, "\n\n\n"
evaluate("empty_bl", blank_lines, show=2)
# noise: extra look-alike fields
def noise(si, bl, e):
    extra = "Net Weight: 1,000 KG\nTare Weight: 500 KG\nTotal Packages: 12\nContainer No: TCLU1234567\nPort of Transshipment: COLOMBO\nPlace of Delivery: KARACHI\n"
    lines = bl.split("\n"); lines.insert(3, extra.rstrip()); return si, "\n".join(lines)
evaluate("noise_lookalike_fields", noise, show=5)
def noise2(si, bl, e):
    extra = "Gross Weight of container: 2,000 KG\nNotify address: SOMEWHERE\nConsignee contact: John\nNumber of packages: 12\n"
    return si, extra + bl
evaluate("noise_2", noise2, show=5)
# reorder fields, insert preamble and disclaimers
def reorder(si, bl, e):
    ls = bl.split("\n"); head, body = ls[:2], ls[2:]
    rnd.shuffle(body)
    return si, "\n".join(head+body)
evaluate("shuffled_lines(breaks address cont.)", reorder, show=3)
def preamble(si, bl, e): return si, "Dear team,\nPlease see below the Draft BL as agreed: (Ref: 5ALT)\n\n" + bl + "\n\nRegards, Ops\nNote: Weight approximate: 22,000 KG"
evaluate("preamble_and_footer", preamble, show=5)
# values: whitespace/case only in BL values
def upper_bl(si, bl, e):
    return si, re.sub(r"(?m)^([^:\n]+:)(.*)$", lambda m: m.group(1)+m.group(2).upper(), bl)
evaluate("upper_values", upper_bl, show=3)
def title_case(si, bl, e):
    return si, re.sub(r"(?m)^([^:\n]+:)(.*)$", lambda m: m.group(1)+m.group(2).title() if not re.search(r"\d{3},?\d{3}", m.group(2)) else m.group(0), bl)
evaluate("title_values", title_case, show=3)
def dbl_space(si, bl, e):
    return si, re.sub(r"(?m)^([^:\n]+:)(.*)$", lambda m: m.group(1)+m.group(2).replace(" ", "  "), bl)
evaluate("double_space_values", dbl_space, show=3)
def trail_ws(si,bl,e): return si+"   \n\t\n", "\ufeff"+bl.replace("\n"," \n")
evaluate("bom_trailing_ws", trail_ws, show=3)
# real defects: weight off by 1, names swapped etc. Expect MISMATCH on that field
def wt_defect(delta):
    def m(si, bl, e):
        def rep(mm):
            n = int(mm.group(2).replace(",","")); return mm.group(1)+f"{n+delta:,}"+mm.group(3)
        return si, re.sub(r"(?m)^(Gross[^\n:]*:\s*)([\d,]+)(.*)$", rep, bl, count=1, flags=0) if re.search(r"(?m)^Gross[^\n:]*:\s*[\d,]+", bl) else (si, bl)[1]
    return m
def new_defect(name, mut):
    d, ids = build(name, mut); res = asyncio.run(run(d))
    hit=0; tot=0; miss=[]
    for i in ids:
        r=res[i]; tot+=1
        if r["status"]=="MISMATCH": hit+=1
        else: miss.append((i,r["status"],r["headline"][:80]))
    print(f"[defect:{name}] detected {hit}/{tot}", miss[:3])
def swap_one_letter_consignee(si, bl, e):
    def rep(m):
        v=m.group(2); j=len(v)//2; return m.group(1)+v[:j]+("X" if v[j]!="X" else "Y")+v[j+1:]
    return si, re.sub(r"(?m)^((?:Consignee[^:\n]*|CONSIGNEE|To the Order of):\s*)(.+)$", rep, bl, count=1)
new_defect("consignee_1letter_typo", swap_one_letter_consignee)
def wt_plus1(si,bl,e):
    return si, re.sub(r"(?m)^((?:Gross|GROSS)[^:\n]*:\s*)(\d[\d,]*)", lambda m: m.group(1)+f"{int(m.group(2).replace(',',''))+1:,}", bl, count=1)
new_defect("weight_plus_1kg", wt_plus1)
def wt_plus10(si,bl,e):
    return si, re.sub(r"(?m)^((?:Gross|GROSS)[^:\n]*:\s*)(\d[\d,]*)", lambda m: m.group(1)+f"{int(m.group(2).replace(',',''))+10:,}", bl, count=1)
new_defect("weight_plus_10kg", wt_plus10)
def wt_mt(si,bl,e):  # BL states weight in MT but value differs by 0.5 MT
    return si, re.sub(r"(?m)^((?:Gross|GROSS)[^:\n]*:\s*)(\d[\d,]*)(.*)$", lambda m: m.group(1)+f"{(int(m.group(2).replace(',',''))+500)/1000:.3f} MT", bl, count=1)
new_defect("weight_mt_plus_500kg", wt_mt)
def cnt_plus1(si,bl,e):
    return si, re.sub(r"(?m)^((?:No\. of Containers[^:\n]*|Total Containers|Container Count):\s*)(\d+)", lambda m: m.group(1)+str(int(m.group(2))+1), bl, count=1)
new_defect("container_plus_1", cnt_plus1)
def pol_pod_swap(si,bl,e):
    def g(t,pat):
        m=re.search(pat,t); return m
    return si, bl  # placeholder
def port_swap(si,bl,e):
    pol=re.search(r"(?m)^(?:Port of Loading(?: \(POL\))?|PORT OF LOADING|POL|Load Port):\s*(.+)$", bl)
    pod=re.search(r"(?m)^(?:Port of Discharge(?: \(POD\))?|PORT OF DISCHARGE|POD|Discharge Port):\s*(.+)$", bl)
    if pol and pod:
        a,b=pol.group(1),pod.group(1)
        bl=bl.replace(pol.group(0), pol.group(0).replace(a,b)).replace(pod.group(0), pod.group(0).replace(b,a))
    return si, bl
new_defect("pol_pod_swapped", port_swap)
def notify_typo(si,bl,e):
    return si, re.sub(r"(?m)^((?:Notify[^:\n]*|NOTIFY PARTY):\s*)(.+)$", lambda m: m.group(1)+m.group(2)[:-1], bl, count=1)
new_defect("notify_dropped_last_letter", notify_typo)

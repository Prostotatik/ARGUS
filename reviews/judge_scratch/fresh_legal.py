import sys
sys.path.insert(0, r"E:/Projects/Averis x Monash/backend")
from sdoc import normalize as nz

def t(a, b, expect):
    r = nz.names_equal(a, b).match
    flag = "ok " if r == expect else "BAD"
    print(flag, repr(a), "vs", repr(b), "-> match=", r, "expected", expect)
    return r == expect

res = []
pos = [
    ("SUNRISE LOGISTICS PTY LTD", "SUNRISE LOGISTICS PTY. LTD."),
    ("KRONOS SHIPPING AG", "KRONOS SHIPPING A.G."),
    ("IBERIA TRADE S.A.", "IBERIA TRADE SA"),
    ("MEXICANA DE EXPORTACION S.A. DE C.V.", "MEXICANA DE EXPORTACION SA DE CV"),
    ("DELTA HOLDINGS N.V.", "DELTA HOLDINGS NV"),
    ("ROTTERDAM TRADE B.V.", "ROTTERDAM TRADE BV"),
    ("WARSAW COMMODITIES SP. Z O.O.", "WARSAW COMMODITIES SP Z OO"),
    ("VOLGA EXPORT OOO", "VOLGA EXPORT OOO "),
    ("SAKURA TRADING K.K.", "SAKURA TRADING KK"),
    ("BELGRADE FREIGHT D.O.O.", "BELGRADE FREIGHT DOO"),
    ("LISBOA COMERCIO LDA", "LISBOA COMERCIO LDA."),
    ("SANTIAGO EXPORT LTDA", "SANTIAGO EXPORT LTDA."),
    ("PARIS NEGOCE SARL", "PARIS NEGOCE S.A.R.L."),
]
for a, b in pos:
    res.append(t(a, b, True))

neg = [
    ("SAKURA TRADING K.K.", "SAKURA TRADING OYJ"),          # different legal form entirely
    ("DELTA HOLDINGS N.V.", "DELTA SHIPPING N.V."),          # different company name, same suffix
    ("KRONOS SHIPPING AG", "KRONOZ SHIPPING AG"),            # 1-char typo in the actual name
    ("WARSAW COMMODITIES SP. Z O.O.", "KRAKOW COMMODITIES SP. Z O.O."),
]
for a, b in neg:
    res.append(t(a, b, False))
print(sum(res), "/", len(res), "as expected")

import sys
sys.path.insert(0, r"E:/Projects/Averis x Monash/backend")
from sdoc import normalize as nz

def t(a, b, expect):
    r = nz.ports_equal(a, b).match
    flag = "ok " if r == expect else "BAD"
    print(flag, repr(a), "vs", repr(b), "-> match=", r, "expected", expect)
    return r == expect

res = []
# fresh Iran/Iraq/Colombia/Argentina/Ecuador cases (different ports/phrasing than unit_norm.py's
# BANDAR ABBAS/UMM QASR/CARTAGENA/BUENOS AIRES/GUAYAQUIL)
pos = [
    ("BANDAR IMAM KHOMEINI, IRAN", "BANDAR IMAM KHOMEINI"),                # country dropped on one side
    ("BANDAR IMAM KHOMEINI, ISLAMIC REPUBLIC OF IRAN", "BANDAR IMAM KHOMEINI, IRAN"),  # official long name
    ("ASSALUYEH, IRAN", "ASSALUYEH (IRIAB)"),                              # UN/LOCODE-style suffix
    ("KHORRAMSHAHR, IRAN", "KHORRAMSHAHR"),
    ("BASRA, IRAQ", "BASRAH"),                                             # alt spelling, no country on 2nd
    ("BASRA, REPUBLIC OF IRAQ", "BASRA, IRAQ"),                            # official long name
    ("UMM QASR, IRAQ", "UMM QASR PORT"),                                   # "PORT" suffix variant
    ("BUENAVENTURA, COLOMBIA", "BUENAVENTURA"),
    ("BARRANQUILLA, REPUBLIC OF COLOMBIA", "BARRANQUILLA, COLOMBIA"),
    ("SANTA MARTA, COLOMBIA", "SANTA MARTA"),
    ("BAHIA BLANCA, ARGENTINA", "BAHIA BLANCA"),
    ("ROSARIO, ARGENTINE REPUBLIC", "ROSARIO, ARGENTINA"),
    ("SAN LORENZO, ARGENTINA", "SAN LORENZO"),
    ("MANTA, ECUADOR", "MANTA"),
    ("PUERTO BOLIVAR, REPUBLIC OF ECUADOR", "PUERTO BOLIVAR, ECUADOR"),
    ("ESMERALDAS, ECUADOR", "ESMERALDAS"),
]
for a, b in pos:
    res.append(t(a, b, True))

# negative: must NOT match (different real countries/ports, incl. Iran vs Iraq near-miss)
neg = [
    ("BANDAR ABBAS, IRAN", "UMM QASR, IRAQ"),
    ("BASRA, IRAQ", "BANDAR IMAM KHOMEINI, IRAN"),
    ("BUENAVENTURA, COLOMBIA", "GUAYAQUIL, ECUADOR"),
    ("ROSARIO, ARGENTINA", "MONTEVIDEO, URUGUAY"),
    ("MANTA, ECUADOR", "CALLAO, PERU"),
    ("BASRA, IRAQ", "BASRA SOUTH TERMINAL"),  # different specific terminal, not a plain equivalence
]
for a, b in neg:
    res.append(t(a, b, False))
print(sum(res), "/", len(res), "as expected")

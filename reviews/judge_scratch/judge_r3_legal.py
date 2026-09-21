import sys
sys.path.insert(0, r"E:\Projects\Averis x Monash\backend")
from sdoc.normalize import names_equal

cases = [
    # (a, b, expected_match, note)
    ("BRASILIA EXPORT S/A", "BRASILIA EXPORT SA", True, "Brazilian S/A slash form (like S/B pattern) vs bare SA"),
    ("MUMBAI TRADERS PVT. LTD.", "MUMBAI TRADERS PVT LTD", True, "Indian Pvt. Ltd. dotted multi-letter-word form"),
    ("CAPETOWN LOGISTICS (PTY) LTD", "CAPETOWN LOGISTICS PTY LTD", True, "South African parenthetical (Pty) Ltd"),
    ("MOSCOW CARGO O.O.O.", "MOSCOW CARGO OOO", True, "Russian OOO written with dots"),
    ("HONGKONG FREIGHT CO., LIMITED", "HONGKONG FREIGHT CO LTD", True, "HK Co., Limited comma + full word Limited"),
    ("GENEVA COMMODITIES SARL", "GENEVA COMMODITIES SA\u0300RL", True, "Swiss accented Sarl vs plain SARL (NFKD strip)"),
    ("ISTANBUL EXPORT A.S.", "ISTANBUL EXPORT AS", True, "Turkish Anonim Sirketi dotted A.S. vs bare AS"),
    ("SINGAPORE MARINE PTE. LTD.", "SINGAPORE MARINE PTE LTD", True, "dotted PTE. LTD. vs bare"),
    ("BERLIN TRADING GMBH & CO. KG", "BERLIN TRADING GMBH AND CO KG", True, "ampersand-vs-AND with dotted CO."),
    ("KUALA LUMPUR SDN BHD", "KUALA LUMPUR SDN. BHD.", True, "Malaysian SDN BHD with trailing dots"),
    # negative controls - should NOT match
    ("HANOI IMPORT CONG TY TNHH", "HANOI EXPORT CONG TY TNHH", False, "different core name, same (unrecognised) suffix TNHH"),
    ("ISTANBUL EXPORT A.S.", "ISTANBUL EXPORT AG", False, "different suffix (Turkish AS vs German AG) should not match"),
    ("MUMBAI TRADERS PVT. LTD.", "MUMBAY TRADERS PVT LTD", False, "typo in core name"),
]

ok = 0
for a, b, expected, note in cases:
    r = names_equal(a, b)
    status = "ok " if r.match == expected else "BAD"
    if r.match == expected:
        ok += 1
    print(f"{status} {a!r} vs {b!r} -> match={r.match} near_miss={r.near_miss} expected={expected}  ({note})")
print(f"\n{ok}/{len(cases)} as expected")

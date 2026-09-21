"""Value normalisation + equality for the 7 compared fields. Pure functions, no I/O, no LLM.

Design rule: ignore *formatting* noise (case, punctuation, legal-suffix presence, country/UN-LOCODE
tails on ports, thousands separators, kg/MT/lbs units, '2 x 40HC' vs '2X40'HC') but never
ignore a real content difference (different entity, different port, +1 container, +500 kg).
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# blanks
# ---------------------------------------------------------------------------
_BLANK_WORDS = {
    "", "TBA", "TBC", "TBD", "N/A", "NA", "NIL", "NONE", "UNKNOWN", "TO BE ADVISED", "TO BE CONFIRMED",
    "TO BE DETERMINED", "NOT AVAILABLE", "NOT PROVIDED", "-", "--", "?", "XXX", "XXXX",
}
_BLANK_RE = re.compile(r"^[\s_?*\-–—./\\|:;#]*$|^(?:_+|\?+|-+)\s*(?:MT|MTS|KG|KGS)?$", re.I)


def is_blank(value: str | None) -> bool:
    if value is None:
        return True
    v = str(value).strip()
    if v.upper() in _BLANK_WORDS:
        return True
    if _BLANK_RE.match(v):
        return True
    # mostly placeholder characters e.g. "??? KG"
    letters = re.sub(r"[^A-Za-z0-9]", "", v)
    if not letters and v:
        return True
    return False


def has_placeholder(value: str | None) -> bool:
    """A value that is partly blank ('??', '___') - present but untrustworthy."""
    return bool(value) and bool(re.search(r"\?{2,}|_{3,}", value))


# ---------------------------------------------------------------------------
# names (shipper / consignee / notify)
# ---------------------------------------------------------------------------
_LEGAL_CANON = {
    "LIMITED": "LTD", "COMPANY": "CO", "CORPORATION": "CORP", "INCORPORATED": "INC",
    "PRIVATE": "PVT", "BERHAD": "BHD", "GESELLSCHAFT": "GMBH",
}
_LEGAL = {
    "LTD", "CO", "INC", "CORP", "LLC", "PTE", "PVT", "PTY", "SDN", "BHD", "GMBH", "FZE", "FZ", "FZC",
    "FZCO", "PLC", "LLP", "AG", "SA", "BV", "NV", "JSC", "SAS", "SRL", "SPA", "OY", "CV", "DMCC",
    "TBK", "LP", "THE", "AND",
}


@dataclass(frozen=True)
class NameKey:
    full: str
    core: str
    legal: frozenset[str]


def _ascii_upper(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.upper()


def norm_name(raw: str) -> NameKey:
    s = _ascii_upper(raw).replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    toks = [_LEGAL_CANON.get(t, t) for t in s.split()]
    if toks and toks[0] == "THE":
        toks = toks[1:]
    full = " ".join(toks)
    # strip trailing legal-suffix run for the 'core'
    core_toks = list(toks)
    legal: list[str] = []
    while core_toks and core_toks[-1] in _LEGAL and len(core_toks) > 1:
        legal.append(core_toks.pop())
    return NameKey(full=full, core=" ".join(core_toks), legal=frozenset(legal))


def _sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


@dataclass
class Cmp:
    match: bool
    note: str | None = None
    near_miss: bool = False


def names_equal(a: str, b: str) -> Cmp:
    ka, kb = norm_name(a), norm_name(b)
    if ka.full == kb.full:
        return Cmp(True, None if a.strip() == b.strip() else "format differences ignored (case/punctuation)")
    if ka.core == kb.core and (ka.legal <= kb.legal or kb.legal <= ka.legal):
        return Cmp(True, "legal-suffix difference ignored")
    near = _sim(ka.core, kb.core) >= 0.88
    return Cmp(False, "near-identical text (possible typo)" if near else None, near)


# ---------------------------------------------------------------------------
# ports
# ---------------------------------------------------------------------------
_COUNTRIES = {
    "UAE", "UNITED ARAB EMIRATES", "US", "USA", "UNITED STATES", "UNITED STATES OF AMERICA", "UK", "UNITED KINGDOM",
    "INDIA", "CHINA", "SINGAPORE", "MALAYSIA", "INDONESIA", "KENYA", "LITHUANIA", "VIETNAM", "VIET NAM",
    "SOUTH KOREA", "KOREA", "SLOVENIA", "POLAND", "TURKEY", "TURKIYE", "ISRAEL", "NIGERIA", "GUINEA", "CHILE",
    "PERU", "AUSTRALIA", "MYANMAR", "PAKISTAN", "JORDAN", "PHILIPPINES", "THAILAND", "JAPAN", "GERMANY",
    "NETHERLANDS", "BELGIUM", "FRANCE", "ITALY", "SPAIN", "EGYPT", "SAUDI ARABIA", "KSA", "OMAN", "QATAR",
    "BANGLADESH", "SRI LANKA", "TAIWAN", "HONG KONG", "HK", "BRAZIL", "MEXICO", "CANADA", "SOUTH AFRICA",
    "TANZANIA", "GHANA", "MOROCCO", "GREECE", "RUSSIA", "UKRAINE", "AUSTRIA", "NEW ZEALAND", "CAMBODIA",
    "PRC", "P R CHINA", "REPUBLIC OF KOREA", "R O KOREA",
}
_UNLOCODE = {
    "SGSIN": "SINGAPORE", "CNNTG": "NANTONG", "CNSHA": "SHANGHAI", "MYPKG": "PORT KLANG", "INNSA": "NHAVA SHEVA",
    "IDBUA": "BUATAN", "AEJEA": "JEBEL ALI", "KEMBA": "MOMBASA", "INTUT": "TUTICORIN", "LTKLJ": "KLAIPEDA",
    "USHOU": "HOUSTON", "USNYC": "NEW YORK", "USLGB": "LONG BEACH", "USSAV": "SAVANNAH", "USBAL": "BALTIMORE",
    "VNSGN": "HOCHIMINH CITY", "KRPTK": "PYEONGTAEK", "KRPUS": "BUSAN", "SIKOP": "KOPER", "PLGDN": "GDANSK",
    "TRMER": "MERSIN", "ILASH": "ASHDOD", "NGAPP": "APAPA", "GNCKY": "CONAKRY", "CLVAP": "VALPARAISO",
    "PECLL": "CALLAO", "AUFRE": "FREMANTLE", "AUBNE": "BRISBANE", "MMRGN": "YANGON", "PKKHI": "KARACHI",
    "JOAQB": "AQABA", "PHCEB": "CEBU",
}
_PORT_ALIASES = {
    "HO CHI MINH CITY": "HOCHIMINH CITY", "HO CHI MINH": "HOCHIMINH CITY", "HOCHIMINH": "HOCHIMINH CITY",
    "SAIGON": "HOCHIMINH CITY", "PORT KELANG": "PORT KLANG", "PELABUHAN KLANG": "PORT KLANG",
    "PUSAN": "BUSAN", "JNPT": "NHAVA SHEVA", "JAWAHARLAL NEHRU": "NHAVA SHEVA", "NHAVASHEVA": "NHAVA SHEVA",
    "JEBELALI": "JEBEL ALI", "NEWYORK": "NEW YORK", "LONGBEACH": "LONG BEACH", "NEW YORK NEW JERSEY": "NEW YORK",
    "NEW YORK NJ": "NEW YORK",
}


@dataclass(frozen=True)
class PortKey:
    core: str
    qual: frozenset[str]
    code: str | None


def norm_port(raw: str) -> PortKey:
    s = _ascii_upper(raw).strip()
    code = None
    quals: set[str] = set()

    def paren(m: re.Match) -> str:
        nonlocal code
        inner = m.group(1).strip()
        if re.fullmatch(r"[A-Z]{2}\s?[A-Z0-9]{3}", inner):
            code = inner.replace(" ", "")
        else:
            quals.update(re.sub(r"[^A-Z0-9]+", " ", inner).split())
        return " "

    s = re.sub(r"\(([^)]*)\)", paren, s)
    # trailing bare UN/LOCODE e.g. "SINGAPORE SGSIN" is left alone; a value that IS a code maps to a name
    segs = [x.strip() for x in s.split(",") if x.strip()]
    while len(segs) > 1 and (segs[-1] in _COUNTRIES or len(segs[-1]) <= 3):
        segs.pop()
    head = ", ".join(segs)
    head = re.sub(r"[^A-Z0-9]+", " ", head).strip()
    head = re.sub(r"\s+", " ", head)
    if head in _UNLOCODE:
        code = code or head
        head = _UNLOCODE[head]
    head = _PORT_ALIASES.get(head, head)
    # 'PORT OF X' / 'X PORT' wrappers
    head = re.sub(r"^PORT OF ", "", head)
    return PortKey(core=head, qual=frozenset(quals), code=code)


def ports_equal(a: str, b: str) -> Cmp:
    ka, kb = norm_port(a), norm_port(b)
    if ka.core == kb.core:
        if ka.qual == kb.qual:
            return Cmp(True, None if a.strip().upper() == b.strip().upper() else "format differences ignored (case/country/code)")
        if ka.qual <= kb.qual or kb.qual <= ka.qual:
            return Cmp(True, "terminal/qualifier difference ignored")
        return Cmp(False, "same port, different terminal qualifier")
    near = _sim(ka.core, kb.core) >= 0.88
    return Cmp(False, "near-identical text (possible typo)" if near else None, near)


# ---------------------------------------------------------------------------
# container count
# ---------------------------------------------------------------------------
_WORD_NUM = {
    "ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6, "SEVEN": 7, "EIGHT": 8, "NINE": 9,
    "TEN": 10, "ELEVEN": 11, "TWELVE": 12, "THIRTEEN": 13, "FOURTEEN": 14, "FIFTEEN": 15, "SIXTEEN": 16,
    "SEVENTEEN": 17, "EIGHTEEN": 18, "NINETEEN": 19, "TWENTY": 20,
}


@dataclass
class ContainerParse:
    count: int | None
    sizes: str | None = None
    ambiguous: bool = False


def parse_container_count(raw: str | None) -> ContainerParse:
    if raw is None or is_blank(raw):
        return ContainerParse(None)
    s = _ascii_upper(str(raw)).strip()
    s = s.replace("×", "X")
    # "1 x 20' + 2 x 40HC"  -> sum of  N x SIZE terms
    terms = re.findall(r"(\d{1,4})\s*(?:X|\*)\s*(\d{2}\s*['’`]?\s*[A-Z]{0,4}|[A-Z]{2,5})", s)
    if terms:
        n = sum(int(t[0]) for t in terms)
        sizes = " + ".join(f"{t[0]}x{re.sub(r'[^A-Z0-9]', '', t[1])}" for t in terms)
        return ContainerParse(n, sizes)
    m = re.match(r"^(\d{1,4})\s*(?:X|\*)\s*$", s)
    if m:
        return ContainerParse(int(m.group(1)))
    # word numbers: "SIX (6)" / "SIX"
    m = re.match(r"^([A-Z]+)\s*(?:\((\d+)\))?", s)
    if m and m.group(1) in _WORD_NUM:
        return ContainerParse(int(m.group(2)) if m.group(2) else _WORD_NUM[m.group(1)])
    # "6" / "6 CONTAINERS" / "6 CNTR" / "6 PKGS"
    m = re.match(r"^(\d{1,4})\s*(?:CONTAINERS?|CNTRS?|CTNRS?|UNITS?|PKGS?|PACKAGES?|FCL|CONT)?\b", s)
    if m and not re.match(r"^\d{2}\s*['’`]", s):
        return ContainerParse(int(m.group(1)))
    m = re.search(r"\b(\d{1,4})\s*(?:CONTAINERS?|CNTRS?)\b", s)
    if m:
        return ContainerParse(int(m.group(1)))
    return ContainerParse(None, ambiguous=True)


# ---------------------------------------------------------------------------
# weight
# ---------------------------------------------------------------------------
@dataclass
class WeightParse:
    kg: float | None
    converted: bool = False
    unit: str | None = None
    ambiguous: bool = False


_LB = 0.45359237


def _parse_number(txt: str, unit: str | None) -> tuple[float | None, bool]:
    """Return (value, ambiguous). Handles 131,058 / 131.058 / 22,5 / 1.234.567,89 / '131 058'."""
    t = txt.strip().replace(" ", "").replace(" ", "").replace("'", "")
    if not t or not re.fullmatch(r"[\d.,]+", t):
        return None, False
    has_c, has_d = "," in t, "." in t
    amb = False
    if has_c and has_d:
        dec = "," if t.rfind(",") > t.rfind(".") else "."
        thou = "." if dec == "," else ","
        t = t.replace(thou, "").replace(dec, ".")
    elif has_c:
        if re.fullmatch(r"\d{1,3}(,\d{3})+", t):
            t = t.replace(",", "")
        else:
            t = t.replace(",", ".")
            amb = len(txt.split(",")[-1]) == 3
    elif has_d:
        if re.fullmatch(r"\d{1,3}(\.\d{3}){2,}", t):
            t = t.replace(".", "")
        elif re.fullmatch(r"\d{1,3}\.\d{3}", t):
            # '131.058' : thousands sep (kg) or 3-dp decimal (MT)?
            if unit in ("MT", "TON"):
                pass
            else:
                t = t.replace(".", "")
                amb = True
    try:
        return float(t), amb
    except ValueError:
        return None, False


def parse_weight_kg(raw) -> WeightParse:
    if raw is None:
        return WeightParse(None)
    if isinstance(raw, (int, float)):
        return WeightParse(float(raw), False, "KG")
    s = _ascii_upper(str(raw)).strip()
    if is_blank(s):
        return WeightParse(None)
    m = re.search(r"([\d][\d.,'  ]*)\s*(KGS?|KILOS?|KILOGRAMS?|MTS?|M/T|TONS?|TONNES?|T|LBS?|POUNDS?)?\b", s)
    if not m:
        return WeightParse(None, ambiguous=True)
    unit_raw = (m.group(2) or "").replace("/", "")
    unit = None
    if unit_raw.startswith("K"):
        unit = "KG"
    elif unit_raw in ("MT", "MTS", "TON", "TONS", "TONNE", "TONNES", "T"):
        unit = "MT"
    elif unit_raw.startswith(("LB", "POUND")):
        unit = "LB"
    # unit may also appear before the number ("KGS 22,000")
    if unit is None:
        mu = re.search(r"\b(KGS?|MTS?|LBS?)\b", s)
        if mu:
            unit = {"K": "KG", "M": "MT", "L": "LB"}[mu.group(1)[0]]
    val, amb = _parse_number(m.group(1), unit)
    if val is None:
        return WeightParse(None, ambiguous=True)
    conv = False
    if unit == "MT":
        val, conv = val * 1000.0, True
    elif unit == "LB":
        val, conv = val * _LB, True
    return WeightParse(val, conv, unit or "KG", amb)


def weights_equal(a: WeightParse, b: WeightParse) -> Cmp:
    if a.kg is None or b.kg is None:
        return Cmp(False)
    tol = 0.5
    note = None
    if a.converted or b.converted:
        tol = max(1.0, 0.0005 * max(a.kg, b.kg))   # unit-conversion rounding only
        note = "units converted to kg"
    if abs(a.kg - b.kg) <= tol:
        return Cmp(True, note)
    return Cmp(False)


def fmt_kg(v: float | None) -> str | int | float | None:
    if v is None:
        return None
    return int(round(v)) if abs(v - round(v)) < 1e-6 else round(v, 3)

"""Field-label alignment: 'Port of Loading' == 'Load Port' == 'POL' == 'Loading Port'.

Alignment is by meaning, never by exact header text. Label text is normalised
(lower-case, ASCII only, parentheticals such as '(Non-Negotiable)' / '(POL)' / '(毛重)' dropped,
punctuation -> spaces) and then looked up in a synonym table; unknown labels fall back to a
conservative fuzzy match (flagged so the confidence drops).
"""
from __future__ import annotations

import difflib
import re
import unicodedata

# canonical field -> synonym phrases (already in "normalised" form: lowercase words)
FIELD_SYNONYMS: dict[str, list[str]] = {
    "shipper": [
        "shipper", "shipper exporter", "exporter", "seller", "consignor", "shipper name",
        "shipped by", "shipper principal or seller", "shipper and exporter", "shipper exporter name",
    ],
    "consignee": [
        "consignee", "consignee non negotiable", "to the order of", "to order of", "consignee name",
        "receiver", "consigned to", "consignee negotiable",
    ],
    "notify_party": [
        "notify", "notify party", "notify party intermediate consignee", "notify name", "notify address",
        "notifying party", "notify party name", "also notify",
    ],
    "port_of_loading": [
        "port of loading", "pol", "load port", "loading port", "port of load", "port of origin",
        "origin port", "place of loading", "port of shipment", "loading port pol", "from port",
        "port of loading pol",
    ],
    "port_of_discharge": [
        "port of discharge", "pod", "discharge port", "discharging port", "port of destination",
        "destination port", "port of unloading", "port of discharge pod", "unloading port", "to port",
    ],
    "container_count": [
        "no of containers", "total containers", "container count", "number of containers",
        "no of containers or packages", "containers", "no of container", "total no of containers",
        "qty of containers", "container qty", "total container", "container quantity", "no of cntrs",
        "no of containers packages", "total number of containers", "number of container",
    ],
    "gross_weight_kg": [
        "gross weight", "gross wt", "total gross weight", "total gross wt", "gross weight kg",
        "gross weight kgs", "g w", "gw", "weight gross", "gross mass", "total gross mass",
        "gross weight total", "gross wt kgs", "gross wt kg", "gr wt", "gross weight in kg",
    ],
}

_STOP_UNITS = {"kg", "kgs", "mt", "mts", "lbs", "lb", "in", "total"}


def norm_label(raw: str) -> str:
    """Lower-case ASCII words; drops parentheticals and non-ASCII (e.g. Chinese) glued to the label."""
    s = unicodedata.normalize("NFKC", raw)
    s = re.sub(r"[\(\[（【][^)\]）】]*[\)\]）】]", " ", s)      # (...) [...] and full-width variants
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _norm_label_keep_parens(raw: str) -> str:
    s = unicodedata.normalize("NFKC", raw).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_SYN_INDEX: dict[str, str] = {}
for _f, _syns in FIELD_SYNONYMS.items():
    for _s in _syns:
        _SYN_INDEX[_s] = _f

# word-tuple index for prefix matching ('Containers 6 x 40HC' - no colon/dash separator at all,
# seen on OCR-read scanned documents): the same synonym table, keyed by its word tuple instead of
# the joined string, tried longest-first so 'gross weight' wins over a lone 'gross'.
_SYN_TOKENS: dict[tuple[str, ...], str] = {tuple(_s.split()): _f for _s, _f in _SYN_INDEX.items()}
_MAX_SYN_WORDS = max((len(k) for k in _SYN_TOKENS), default=1)


def match_label_prefix_words(words: list[str]) -> tuple[str | None, int]:
    """``words``: lightly-normalised (lower-case, alnum-only) leading tokens of a line.
    Returns (field, n_words_consumed) for the longest known synonym matching a PREFIX of
    ``words``, else (None, 0). Used only as a last-resort separator-free layout fallback."""
    for n in range(min(_MAX_SYN_WORDS, len(words)), 0, -1):
        f = _SYN_TOKENS.get(tuple(words[:n]))
        if f:
            return f, n
    return None, 0


def match_label(raw_label: str, *, exact_only: bool = False) -> tuple[str | None, bool]:
    """Return (field, exact). exact=False means a fuzzy/derived match (lower confidence).

    Never matches long free text: a label longer than ~8 words is not a field label.

    ``exact_only``: skip the difflib fuzzy fallback below. That fallback scans all ~90 known
    synonyms with ``SequenceMatcher`` and is the expensive part of this function; callers that try
    many candidate substrings per line that are usually NOT a label at all (e.g. every dash/equals-
    split line, since real labels are a minority of those) should pass ``exact_only=True`` so a
    document full of non-label dashed text (addresses, vessel/voyage refs, date ranges) does not
    pay a ~90-way fuzzy scan per line for nothing. Exact and stop-word-normalised matches - the
    common case - are unaffected either way.
    """
    if not raw_label or len(raw_label) > 90:
        return None, False
    cands = [norm_label(raw_label), _norm_label_keep_parens(raw_label)]
    for c in cands:
        if c in _SYN_INDEX:
            return _SYN_INDEX[c], True
    for c in cands:
        toks = c.split()
        if not toks or len(toks) > 8:
            continue
        # drop leading 'total' and trailing unit words, retry
        t2 = [t for t in toks if t not in _STOP_UNITS] if toks[0] == "total" or toks[-1] in _STOP_UNITS else toks
        c2 = " ".join(t2)
        if c2 and c2 in _SYN_INDEX:
            return _SYN_INDEX[c2], True
        # trailing unit only ("gross weight kg")
        while t2 and t2[-1] in _STOP_UNITS:
            t2 = t2[:-1]
        c3 = " ".join(t2)
        if c3 and c3 in _SYN_INDEX:
            return _SYN_INDEX[c3], True
    if exact_only:
        return None, False
    # conservative fuzzy fallback (typos such as 'Consgnee', 'Port of Loadng')
    best, best_r = None, 0.0
    c = cands[0]
    if len(c) >= 6:
        for syn, f in _SYN_INDEX.items():
            if len(syn) < 6:
                continue
            r = difflib.SequenceMatcher(None, c, syn).ratio()
            if r > best_r:
                best, best_r = f, r
        if best_r >= 0.88:
            return best, False
    return None, False

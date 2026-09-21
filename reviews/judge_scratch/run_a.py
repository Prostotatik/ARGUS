from perturb import *
import random
# ---------- A2 separator / layout variants (applied to BOTH docs, semantic-preserving)
def lines_kv(text):
    return re.findall(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$", text)
def layout(kind):
    def f(t):
        if kind == "dash":
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$", r"\1 - \2", t)
        if kind == "equals":
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$", r"\1 = \2", t)
        if kind == "tab":
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$", r"\1\t\2", t)
        if kind == "mdtable":
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$", r"| \1 | \2 |", t)
        if kind == "lower":
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):", lambda m: m.group(1).lower() + ":", t)
        if kind == "spaced":
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$", r"\1 :   \2", t)
        if kind == "bullets":
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$", r"* \1: \2", t)
        if kind == "crlf":
            return t.replace("\n", "\r\n")
        if kind == "nexttline":
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.+)$", r"\1:\n\2", t)
        if kind == "blanklines":
            return t.replace("\n", "\n\n")
        return t
    return f
for k in ["dash","equals","tab","mdtable","lower","spaced","bullets","crlf","nexttline","blanklines"]:
    L = layout(k)
    evaluate("lay_"+k, lambda si,bl,e,L=L:(L(si),L(bl)), show=2)

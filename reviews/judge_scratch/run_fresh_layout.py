from perturb import *
def layout(kind):
    def f(t):
        if kind == "arrow":
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$", r"\1 --> \2", t)
        if kind == "dcolon":
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$", r"\1:: \2", t)
        if kind == "semicolon":
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$", r"\1; \2", t)
        if kind == "numbered":
            n = [0]
            def r(m):
                n[0] += 1
                return f"{n[0]}. {m.group(1)}: {m.group(2)}"
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$", r, t)
        if kind == "jsonish":
            return re.sub(r'(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$', r'"\1": "\2",', t)
        if kind == "gt":
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$", r"\1 > \2", t)
        if kind == "parenval":
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$", r"\1 (\2)", t)
        if kind == "colonspacecolon":
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$", r"\1  :\2", t)
        if kind == "indented":
            return re.sub(r"(?m)^([A-Za-z][^:\n]{0,60}):[ ]?(.*)$", r"    \1: \2", t)
        return t
    return f
for k in ["arrow","dcolon","semicolon","numbered","jsonish","gt","parenval","colonspacecolon","indented"]:
    L = layout(k)
    evaluate("freshlay_"+k, lambda si,bl,e,L=L:(L(si),L(bl)), show=3)

#!/usr/bin/env python3
"""Prompt routing by clause, shared by the prompt-scan and prompt-polish hooks.

Only *requested-action* text decides intent and lane:
- a structured prompt (Markdown sections) is read through its Goal/Requirements/Approach/Done-when sections;
  Context and Constraints sections are context, never the request;
- a long pasted block followed by a short instruction is read through that instruction;
- fenced code and quoted lines are context;
- a negated clause ("do not deploy", "no pushes") is a prohibition, never an intent.

    python3 -I route.py classify [--lines] < hook.json   ->  {"intent", "lane", "prohibited", "polish", "words", ...}
"""
import json
import re
import sys

REQUEST_SECTIONS = re.compile(r"^(goal|goals|task|request|requirements?|approach|done when|deliverables?|"
                              r"acceptance|steps|plan)\b", re.I)
CONTEXT_SECTIONS = re.compile(r"^(context|background|constraints?|verification|notes?|evidence|findings|"
                              r"report|output|logs?)\b", re.I)
NEGATION = re.compile(r"\b(do not|don't|dont|never|no|not|without|avoid|must not|mustn't|nothing)\b", re.I)

INTENTS = [  # most specific first; every pattern matches base forms only, so "created" is not "create"
    ("deploy", r"\b(deploy|release|roll ?out|publish the release|restart (the )?(backend|frontend|service|container))\b"),
    ("performance", r"\bslow|\blag(s|gy|ging)?\b|latenc|\bperf(orm|\b)|skele?ton|spinner|\bloading\b|\bfreez|"
                    r"\bhang(s|ing)?\b|\bstuck\b|\bjank|re-?render|prefetch|"
                    r"takes? (around |about |almost )?[0-9]+ ?(s\b|sec|ms)|[0-9]+ ?seconds"),
    ("debug", r"\berror|broken|\bbug|crash|\bfail|not working|doesn.?t work|regression|\bfix\b"),
    ("research", r"\bresearch\b|\bonline\b|\bgithub\b|\bweb search\b|search the web|look up|\bcompare\b|"
                 r"\balternatives?\b|\bbenchmark against\b"),
    ("investigate", r"i?n?v[ie]st[ie]?g|root cause|diagnos|look into|find out|\bwhy\b|\btrace\b|what happened|"
                    r"analy[sz]|took (so |too )?(long|large)|bottle ?neck|\bdetermine\b|\bevaluate\b|\bassess\b"),
    ("review", r"\breview\b|\baudit\b|\bverify\b|\binspect\b|double.?check"),
    ("plan", r"\bplan\b|\bdesign\b|\bapproach\b|\bpropos(e|al)\b|\barchitect|\bstrategy\b"),
    ("implement", r"\b(implement|add|create|build|scaffold|generate|refactor|change|update|rename|remove|delete|"
                  r"migrate|make|write|wire|port|improve|rework|redesign|refine)\b|\bshould (be|follow|show|have|use|look|open|stay|match)\b"),
]
LANES = [
    ("rust", r"\brust\b|\bcargo\b|\baxum\b|\bsqlx\b|\bclippy\b|borrow checker|\blifetime|\btokio\b|\.rs\b"),
    ("python", r"\bfastapi\b|\bpydantic\b|\bsqlalchemy\b|\bcelery\b|\balembic\b|\bpython\b|\.py\b"),
    ("frontend", r"next\.?js|\breact\b|\bcomponent|\.tsx?\b|\bfrontend\b|data.?table|\bpages?\b|\bui\b|nav ?bar|"
                 r"sidebar|skele?ton|\bbrowser\b|\bclick|eventsource|\bsse\b|router\.refresh|\bfacets?\b"),
    ("infra", r"\bdocker\b|\bcompose\b|\bnginx\b|\bssl\b|\bcontainer"),
]
QUESTION_START = re.compile(r"^(what|how|why|which|where|when|who|explain|summari[sz]e|describe|tell me|show me|"
                            r"list)\b", re.I)
ACTION_INTENTS = {"deploy", "performance", "debug", "implement", "plan", "review", "investigate+implement"}
STRUCTURE = re.compile(r"^\s*#{1,4}\s*(goal|context|requirements?|constraints?|approach|verification|done when|"
                       r"acceptance|scope)\b", re.I | re.M)
PATH_TOKEN = re.compile(r"[\w.-]+/[\w./-]+|\b[\w-]+\.(rs|ts|tsx|py|md|json|sh|toml|ya?ml|sql)\b")
VAGUE = re.compile(r"\b(everything|all of them|the same as|similar to|like before|the attached|as discussed|"
                   r"tone|feel|nicer|better|clean ?up|improve|somehow|and so on)\b", re.I)


def strip_context(text):
    """Drop fenced code and quoted lines: they are material to read, not the request."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(">"))


def sections(text):
    """[(heading or None, body)] for Markdown-structured prompts."""
    parts, heading, body = [], None, []
    for line in text.splitlines():
        m = re.match(r"^\s*#{1,4}\s*(.+?)\s*#*\s*$", line)
        if m:
            parts.append((heading, "\n".join(body)))
            heading, body = m.group(1), []
        else:
            body.append(line)
    parts.append((heading, "\n".join(body)))
    return parts


def request_text(prompt):
    text = strip_context(prompt)
    parts = sections(text)
    if len(parts) > 1:
        picked = [body for heading, body in parts if heading and REQUEST_SECTIONS.match(heading)]
        lead = parts[0][1] if parts[0][0] is None else ""
        if picked:
            return "\n".join([lead, *picked])
        return "\n".join(body for heading, body in parts if not (heading and CONTEXT_SECTIONS.match(heading)))
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) >= 2:
        last, before = paragraphs[-1], " ".join(paragraphs[:-1])
        if len(last.split()) <= 30 and len(before.split()) >= 60:
            return last  # a pasted report followed by a short instruction
    return text


def clauses(text):
    return [c.strip() for c in re.split(r"[.;:\n!?]|,\s*(?:and|but|then)\b|\s(?:and then|but)\s", text) if c.strip()]


def classify(prompt):
    request = request_text(prompt)
    found, prohibited, lanes = [], [], []
    for clause in clauses(request):
        lower = clause.lower()
        negated = NEGATION.search(lower)
        hits = []
        for name, pattern in INTENTS:
            m = re.search(pattern, lower)
            if not m:
                continue
            if negated and negated.start() < m.start():
                prohibited.append(name)
            else:
                hits.append((m.start(), name))
        # Within one clause the first verb is the request ("implement the plan"); later words are its object.
        if hits:
            name = min(hits)[1]
            if name not in found:
                found.append(name)
        for name, pattern in LANES:
            m = re.search(pattern, lower)
            if m and not (negated and negated.start() < m.start()) and name not in lanes:
                lanes.append(name)
    stripped = request.strip()
    words = len(prompt.split())
    order = [name for name, _ in INTENTS]
    intent = min(found, key=order.index) if found else ""
    wants_change = "implement" in found or re.search(r"\b(fix|resolve|repair)\b", request, re.I)
    if {"investigate", "performance"} & set(found) and wants_change and len(found) >= 2 \
            and intent in ("investigate", "performance", "debug"):
        intent = "investigate+implement"
    asks = stripped.endswith("?") or QUESTION_START.match(stripped)
    # A question about stack code (a lane is named) is an investigation; otherwise it is answered, not routed.
    if asks and not lanes and len(stripped.split()) <= 40 and intent in ("", "investigate", "review"):
        intent = "question"
    return {"intent": intent, "lane": lanes[0] if lanes else "", "prohibited": sorted(set(prohibited)),
            "polish": needs_polish(prompt, intent), "words": words}


def needs_polish(prompt, intent):
    """Polish only an action request whose scope is still open; a question, research or an exact spec is left alone."""
    if intent not in ACTION_INTENTS:
        return False
    if len(STRUCTURE.findall(prompt)) >= 2:
        return False  # already a structured spec
    words = len(prompt.split())
    precise = len(PATH_TOKEN.findall(prompt)) >= 2 or re.search(r"\b(acceptance|done when|tests? (pass|must))\b", prompt, re.I)
    if words >= 25:
        return not precise
    return bool(VAGUE.search(prompt)) and not precise


def main():
    if len(sys.argv) < 2 or sys.argv[1] != "classify":
        print("usage: route.py classify < hook.json", file=sys.stderr)
        return 2
    try:
        hook = json.load(sys.stdin)
    except ValueError:
        hook = {}
    prompt = hook.get("prompt") if isinstance(hook, dict) else None
    if not isinstance(prompt, str):
        prompt = ""
    out = classify(prompt)
    out.update(session_id=hook.get("session_id", "") if isinstance(hook, dict) else "",
               transcript_path=hook.get("transcript_path", "") if isinstance(hook, dict) else "")
    if "--lines" in sys.argv:
        # One field per line for `mapfile` in the hooks; values never contain newlines.
        fields = [out["intent"], out["lane"], " ".join(out["prohibited"]), str(out["words"]),
                  "1" if out["polish"] else "0", out["session_id"], out["transcript_path"]]
        print("\n".join(str(f).replace("\n", " ") for f in fields))
    else:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Blocks and cases. A block is the smallest unit that runs on its own: its cases share users, codes and
sessions. Every case a block can report is declared up front, so --list needs no instance and every
summary count has a fixed denominator."""
import json
import time

BLOCKS = []          # in run order
RESULTS = []
RESULTS_FILE = None


def block(suite, name, cases, emails=0, setup=False, browser=False):
    """emails: the most real emails the block makes. setup: runs before any other block of its suite."""
    def wrap(fn):
        BLOCKS.append({"suite": suite, "name": name, "fn": fn, "cases": list(cases), "emails": emails, "setup": setup,
                       "browser": browser, "doc": " ".join((fn.__doc__ or "").split())})
        return fn
    return wrap


CURRENT = {"block": None}


def result(case, ok, how):
    b = CURRENT["block"]
    declared = b is not None and case in b["cases"]
    tag = "PASS" if ok else "FAIL"
    if not declared:
        tag += " (UNDECLARED CASE)"
    print(f"RESULT {case}: {tag} | {how}")
    rec = {"suite": b["suite"] if b else None, "block": b["name"] if b else None, "case": case, "pass": bool(ok) and declared, "how": how,
           "at": time.strftime("%H:%M:%S")}
    RESULTS.append(rec)
    if RESULTS_FILE:
        with open(RESULTS_FILE, "a") as f:
            f.write(json.dumps(rec) + "\n")


def observed(text):
    """A measurement that is reported but is not a case."""
    print("OBSERVED " + text)


def select(suites=None, block_name=None, case=None):
    """The blocks to run. A case is chosen by any part of its title and runs the block that holds it, because
    cases in a block share state. Asking for one block or one case also runs its suite's setup blocks."""
    out = [b for b in BLOCKS if not suites or b["suite"] in suites]
    if block_name or case:
        want = [b for b in out if (block_name and b["name"] == block_name) or (case and any(case.lower() in c.lower() for c in b["cases"]))]
        if not want:
            raise SystemExit(f"no block or case matches {block_name or case!r}; see --list")
        names = {(b["suite"], b["name"]) for b in want}
        out = [b for b in out if (b["suite"], b["name"]) in names or (b["setup"] and b["suite"] in {s for s, _ in names})]
    return out

#!/usr/bin/env python3
"""Seedling QA suite: one entry point for setup, the three suites, build verification, clean-up and the
snapshot comparison. Run from anywhere; configuration comes from environment variables (see README.md).

  python3 tests/qa/run.py --list                       # the cases, with no instance contacted
  python3 tests/qa/run.py --guard-only                 # read the instance identity and stop (read-only)
  python3 tests/qa/run.py --yes-create-and-delete-test-data                    # everything
  python3 tests/qa/run.py --yes-create-and-delete-test-data --suite pwl        # one suite
  python3 tests/qa/run.py --yes-create-and-delete-test-data --case "10b"       # the block holding a case
  python3 tests/qa/run.py --yes-create-and-delete-test-data --cleanup-only     # finish a crashed run's clean-up
"""
import argparse
import importlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import traceback
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from lib import registry                               # noqa: E402
from lib.config import Config, APP_DIR, FIXTURES_DIR, FIXTURE_KEY_CONSTANT, FIXTURE_PATH_PREFIX, QA_DIR   # noqa: E402

SUITES = ["sec", "pwl", "cln"]
SIGN_IN_CONSTANTS = ["SIGN_IN_HMAC_KEY", "SITE_ORIGIN"]
ACK = "--yes-create-and-delete-test-data"


def load_suites():
    for s in SUITES:
        importlib.import_module("suites." + s)


def list_cases(blocks):
    by_suite = {}
    for b in blocks:
        by_suite.setdefault(b["suite"], []).append(b)
    total = sum(len(b["cases"]) for b in blocks)
    print(f"{total} cases in {len(blocks)} blocks across {len(by_suite)} suites. Nothing was contacted.\n")
    for s, bs in by_suite.items():
        n = sum(len(b["cases"]) for b in bs)
        print(f"suite {s}: {n} cases, {len(bs)} blocks, at most {sum(b['emails'] for b in bs)} real emails")
        for b in bs:
            flags = ", ".join(x for x in (["setup"] if b["setup"] else []) + (["browser"] if b["browser"] else []) + ([f"up to {b['emails']} email(s)"] if b["emails"] else []))
            print(f"  block {b['name']}{' (' + flags + ')' if flags else ''}: {b['doc']}")
            for c in b["cases"]:
                print(f"    - {c}")
        print()
    print(f"plus build verification of every file in app/, the clean-up, and the snapshot comparison (not counted as cases)")


def main():
    ap = argparse.ArgumentParser(description="Seedling QA suite. See tests/qa/README.md.")
    ap.add_argument("--list", action="store_true", help="print every block and case and exit; contacts nothing")
    ap.add_argument("--guard-only", action="store_true", help="check the configuration, read the instance identity, and stop; read-only")
    ap.add_argument(ACK, dest="ack", action="store_true", help="required to run: the suite deploys to, creates users and records on, and then deletes them from the instance")
    ap.add_argument("--suite", action="append", choices=SUITES, help="run one suite (repeatable); setup blocks of that suite always run")
    ap.add_argument("--block", help="run one block by name (see --list)")
    ap.add_argument("--case", help="run the block holding the case whose title contains this text")
    ap.add_argument("--skip-browser", action="store_true", help="skip the headless Chromium blocks")
    ap.add_argument("--cleanup-only", action="store_true", help="skip the tests; remove what an earlier run left, from its logs/pre.json")
    ap.add_argument("--keep", action="store_true", help="leave everything on the instance (no clean-up); for debugging only")
    a = ap.parse_args()

    load_suites()
    blocks = registry.select(a.suite, a.block, a.case)
    if a.skip_browser:
        blocks = [b for b in blocks if not b["browser"]]
    if a.list:
        list_cases(blocks); return 0

    cfg = Config()
    bad = cfg.problems()
    if bad:
        print("Configuration problems (nothing was contacted):"); [print("  - " + x) for x in bad]; return 2
    if not a.ack and not a.guard_only:
        print(f"STOP: this suite deploys Seedling and test pages to {cfg.url}, creates and deletes users and records there, and makes the instance "
              f"send up to {cfg.email_ceiling} emails. Pass {ACK} to confirm. Nothing was contacted.")
        return 2
    os.makedirs(cfg.log_dir, exist_ok=True)

    from lib.instance import Instance, Refused
    inst = Instance(cfg)
    try:
        inst.guard("start")
    except Refused as e:
        print(e); return 3
    if a.guard_only:
        print("guard-only: nothing else was done"); return 0
    return run(cfg, inst, a, blocks)


def run(cfg, inst, a, blocks):
    from lib import snapshot, cleanup, verify_build, client
    L = lambda n: os.path.join(cfg.log_dir, n)
    stage_dir = L("stage")
    fixture_paths = {FIXTURE_PATH_PREFIX + f for f in os.listdir(os.path.join(FIXTURES_DIR, FIXTURE_PATH_PREFIX))}
    staged = cleanup.staged_paths(APP_DIR) | fixture_paths
    summary = {"suites": {}, "emails": None, "verify": None, "cleanup": None, "snapshot_differences": None, "foreign": []}
    state_path = L("run-state.json")

    if a.cleanup_only:
        st = json.load(open(state_path))
        pre = json.load(open(L("pre.json")))
        return finish(cfg, inst, pre, staged, set(st["constants_set"]), json.load(open(L("saved-pages.json"))), summary, L, 0)

    print(f"run {cfg.run_id} on {cfg.url} at {cfg.started}; logs in {cfg.log_dir}")
    pre = snapshot.take(inst, L("pre.json"))
    print("pre-run snapshot: " + snapshot.summary(pre))
    overlap = {k: sorted(set(pre[k]) & staged) for k in cleanup.FILE_KINDS + cleanup.SCHEMA_KINDS}
    not_pages = {k: v for k, v in overlap.items() if v and k != "pages"}
    if not_pages:
        print(f"STOP: these Seedling files are already on the instance, so the suite could not remove them afterwards without deleting work it did not create: {not_pages}. "
              "Use an instance without Seedling installed. Nothing was changed.")
        return 4
    saved_pages = cleanup.save_pages(inst, overlap["pages"], L("saved-pages.json"))
    print(f"saved {len(saved_pages)} pre-existing page record(s) the deploy overwrites, to restore afterwards: {[x['physical_file_path'] for x in saved_pages]}")
    constants_set = [FIXTURE_KEY_CONSTANT]
    json.dump({"run_id": cfg.run_id, "constants_set": constants_set}, open(state_path, "w"))

    code = 1
    try:
        inst.stage(stage_dir, APP_DIR, FIXTURES_DIR)
        inst.partial_deploy(stage_dir, cfg.log_dir)
        key = secrets.token_urlsafe(32)
        inst.constant_set(FIXTURE_KEY_CONSTANT, key)
        have = inst.constants()
        for n in SIGN_IN_CONSTANTS:
            if n in have:
                continue
            if not cfg.set_sign_in_constants:
                raise SystemExit(f"STOP: {n} is not set. The Seedling migration creates SIGN_IN_HMAC_KEY once, and SITE_ORIGIN is set by hand; "
                                 "on an instance where the migration already ran, set QA_SET_SIGN_IN_CONSTANTS=1 and the suite sets both for the run and removes them after.")
            inst.constant_set(n, cfg.url if n == "SITE_ORIGIN" else secrets.token_urlsafe(48))
            constants_set.append(n)
            json.dump({"run_id": cfg.run_id, "constants_set": constants_set}, open(state_path, "w"))
            print(f"set {n} for this run (QA_SET_SIGN_IN_CONSTANTS); it is removed at the end")
        origin = inst.liquid("{{ context.constants.SITE_ORIGIN }}").rstrip("/")
        if origin != cfg.url:
            raise SystemExit(f"STOP: SITE_ORIGIN is {origin!r}, not INSITES_URL, so emailed links would point elsewhere")

        budget = client.Budget(cfg.email_ceiling)
        client.init(cfg, inst, key, L("requests.jsonl"), budget)
        for _ in range(20):
            try:
                if urllib.request.urlopen(urllib.request.Request(cfg.url + "/qa-fixture/admin?op=ip", headers={"X-Inspect-Key": key, "Accept": "*/*", "User-Agent": "seedling-qa-suite"}), timeout=30).status == 200:
                    break
            except Exception:
                time.sleep(3)
        budget.start()
        for m in list(sys.modules):
            if m.startswith("suites."):
                del sys.modules[m]
        registry.BLOCKS.clear(); load_suites()
        want = {(b["suite"], b["name"]) for b in blocks}
        run_blocks = [b for b in registry.BLOCKS if (b["suite"], b["name"]) in want]
        registry.RESULTS_FILE = L("results.jsonl")
        stopped = None
        for b in run_blocks:
            print(f"===== {b['suite']}.{b['name']} {time.strftime('%H:%M:%S')}")
            registry.CURRENT["block"] = b
            try:
                b["fn"]()
            except client.EmailCeiling as e:
                print(e); stopped = str(e); break
            except SystemExit as e:
                if str(e).startswith("REFUSED"):
                    print(e); stopped = str(e); break
                print(f"BLOCK ERROR {b['suite']}.{b['name']}: {e} (its unreported cases count as not run)")
            except Exception as e:
                print(f"BLOCK ERROR {b['suite']}.{b['name']}: {type(e).__name__}: {e} (its unreported cases count as not run)"); traceback.print_exc(limit=3)
        registry.CURRENT["block"] = None
        summary["stopped"] = stopped
        summary["emails"] = {"measured": budget.measured(), "declared": budget.declared(), "by_kind": budget.by_kind, "ceiling": cfg.email_ceiling}
        for s in SUITES:
            bs = [b for b in run_blocks if b["suite"] == s]
            if not bs: continue
            declared = [c for b in bs for c in b["cases"]]
            got = {r["case"]: r["pass"] for r in registry.RESULTS if r["suite"] == s}
            summary["suites"][s] = {"declared": len(declared), "passed": sum(1 for c in declared if got.get(c) is True),
                                    "failed": [c for c in declared if got.get(c) is False], "not_run": [c for c in declared if c not in got],
                                    "undeclared": [c for c in got if c not in declared]}
        full = not (a.suite or a.block or a.case)
        if full and cfg.testcafe != "off" and not stopped:
            summary["testcafe"] = testcafe(cfg, L)
        ok, accounted, total, lines = verify_build.verify(inst, APP_DIR, pre, fixture_paths, L("verify.json"))
        print("\n".join(lines))
        summary["verify"] = {"ok": ok, "accounted": accounted, "total": total}
        code = 0
    except SystemExit as e:
        print(e); summary["stopped"] = str(e)
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}"); traceback.print_exc(limit=5); summary["stopped"] = str(e)
    finally:
        if os.path.exists(stage_dir):
            shutil.rmtree(stage_dir)
    if a.keep:
        print("--keep: nothing was removed. Run with --cleanup-only to remove it later.")
        report(summary); return 1
    return finish(cfg, inst, pre, staged, set(constants_set), saved_pages, summary, L, code)


def finish(cfg, inst, pre, staged, constants_set, saved_pages, summary, L, code):
    from lib import snapshot, cleanup
    post = snapshot.take(inst, L("post-test.json"))
    items, foreign = cleanup.build(inst, pre, post, staged, cfg.email_regex(), constants_set)
    groups = {}
    for g, *_ in items: groups[g] = groups.get(g, 0) + 1
    print(f"clean-up: {len(items)} items {groups}")
    good, bad, failed = cleanup.run(inst, items, L("cleanup-log.jsonl"))
    for f in failed: print("CLEAN-UP FAILED", f)
    restored = cleanup.restore_pages(inst, saved_pages)
    summary["cleanup"] = {"removed": good, "of": len(items), "failed": bad, "groups": groups, "pages_restored": restored}
    summary["foreign"] = foreign
    final = snapshot.take(inst, L("final.json"))
    d = snapshot.diff(pre, final)
    for x in d: print("SNAPSHOT", x)
    summary["snapshot_differences"] = len(d)
    summary["sent_log_growth"] = final["sent_notifications_total"] - pre["sent_notifications_total"]
    if cfg.sendgrid_key:
        summary["sendgrid"] = sendgrid(cfg)
    else:
        summary["sendgrid"] = "skipped: SENDGRID_API_KEY is not set"
    report(summary)
    passed = all(not v["failed"] and not v["not_run"] and not v["undeclared"] for v in summary["suites"].values())
    clean = d == [] and bad == 0 and not foreign
    emails_ok = summary["emails"] is None or max(summary["emails"]["measured"], summary["emails"]["declared"]) <= cfg.email_ceiling
    verify_ok = summary["verify"] is None or summary["verify"]["ok"]
    return 0 if code == 0 and passed and clean and emails_ok and verify_ok and not summary.get("stopped") else 1


def testcafe(cfg, L):
    tests_dir = os.path.dirname(QA_DIR)
    if not os.path.isdir(os.path.join(tests_dir, "node_modules")):
        subprocess.run(["npm", "ci"], cwd=tests_dir, capture_output=True, text=True, timeout=600)
    target = "chrome:headless" if cfg.testcafe == "local" else "remote"
    p = subprocess.run(["npx", "testcafe", target, "e2e/**/*.e2e.js"], cwd=tests_dir, capture_output=True, text=True, timeout=1200, env=dict(os.environ, INSITES_URL=cfg.url))
    open(L("testcafe.log"), "w").write(p.stdout + p.stderr)
    import re
    m = re.search(r"(\d+) passed", p.stdout); f = re.search(r"(\d+)/(\d+) failed", p.stdout)
    return {"exit": p.returncode, "passed": int(m.group(1)) if m else 0, "failed": f.group(0) if f else None, "log": "testcafe.log"}


def sendgrid(cfg):
    q = 'subject LIKE "%%%s%%" AND last_event_time BETWEEN TIMESTAMP "%s" AND TIMESTAMP "%s"' % (cfg.run_id, cfg.started, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 600)))
    h = {"Authorization": "Bearer " + cfg.sendgrid_key, "Accept": "application/json"}
    if cfg.sendgrid_subuser: h["on-behalf-of"] = cfg.sendgrid_subuser
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request("https://api.sendgrid.com/v3/messages?limit=1000&query=" + urllib.parse.quote(q), headers=h), timeout=60))
    except Exception as e:
        return f"not read: {type(e).__name__}"
    ms = d.get("messages", [])
    by = {}
    for m in ms: by[(m.get("subject", "").split(" - ")[-1], m.get("status"))] = by.get((m.get("subject", "").split(" - ")[-1], m.get("status")), 0) + 1
    return {"messages": len(ms), "by_subject_and_status": {f"{k[0]} / {k[1]}": v for k, v in by.items()}}


def report(s):
    print("\n========== SUMMARY")
    tot_d = tot_p = 0
    for name, v in s["suites"].items():
        tot_d += v["declared"]; tot_p += v["passed"]
        print(f"suite {name}: {v['passed']} of {v['declared']} cases passed; failed {len(v['failed'])}; not run {len(v['not_run'])}; undeclared results {len(v['undeclared'])}")
        for c in v["failed"]: print(f"    FAILED  {c}")
        for c in v["not_run"]: print(f"    NOT RUN {c}")
    if s["suites"]:
        print(f"all suites run: {tot_p} of {tot_d} cases passed")
    if s.get("stopped"): print(f"stopped early: {s['stopped']}")
    if s.get("testcafe"): print(f"TestCafe e2e: {s['testcafe']}")
    if s["verify"]: print(f"build verification: {s['verify']['accounted']} of {s['verify']['total']} app files match the instance; {'OK' if s['verify']['ok'] else 'FAILED'}")
    if s["emails"]:
        e = s["emails"]
        print(f"emails: {e['measured']} sent by the instance during the tests (sent-log rows), {e['declared']} declared by the cases, ceiling {e['ceiling']}; by template {e['by_kind']}")
    if s.get("sent_log_growth") is not None: print(f"sent log grew by {s['sent_log_growth']} rows over the whole run (rows cannot be deleted)")
    if s.get("sendgrid"): print(f"SendGrid: {s['sendgrid']}")
    if s["cleanup"]:
        c = s["cleanup"]; print(f"clean-up: removed {c['removed']} of {c['of']} items {c['groups']}; failed {c['failed']}; pages restored {c['pages_restored']}")
    for f in s["foreign"]: print(f"NOT REMOVED (not this run's): {f}")
    if s["snapshot_differences"] is not None:
        print(f"snapshot comparison: {s['snapshot_differences']} differences between the pre-run and final snapshots")


if __name__ == "__main__":
    sys.exit(main())

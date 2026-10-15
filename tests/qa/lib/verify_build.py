"""Build verification: every file in the repository's app/ against its record on the instance. Content fields are
read with insites-cli exec graphql; assets by SHA-256 of the bytes the asset URL serves; migrations by their
recorded status. Fails on any mismatch, any missing file, or any extra file the run did not expect."""
import hashlib
import json
import os
import re
import urllib.request

T = {"pages": ("admin_pages", "content slug request_method"), "partials": ("admin_liquid_partials", "body"), "layouts": ("admin_liquid_layouts", "body"),
     "graphql": ("admin_graphql", "query_string"), "policies": ("admin_authorization_policies", "content"), "emails": ("admin_email_notifications", "content"),
     "forms": ("admin_forms", "liquid_body"), "tables": ("admin_tables", "name properties { name attribute_type }"),
     "profiles": ("admin_user_profile_schemas", "name properties { name attribute_type }"), "assets": ("admin_assets", "file_size url")}
FIELD = {"pages": "content", "partials": "body", "layouts": "body", "graphql": "query_string", "policies": "content", "emails": "content", "forms": "liquid_body"}


def body(s):
    m = re.match(r"^---[ \t]*\n.*?\n---[ \t]*(\n|$)(.*)$", s, re.S)
    return m.group(2) if m else s


def verify(inst, app_dir, pre, fixture_paths, out_path):
    inv = {}
    for k, (q, f) in T.items():
        page = 1
        while True:
            d = inst.gql('query { r: %s(per_page: 100, page: %d) { total_pages results { id physical_file_path %s } } }' % (q, page, f))["r"]
            for r in d["results"]: inv[r["physical_file_path"]] = (k, r)
            if page >= (d["total_pages"] or 1): break
            page += 1
    migs = inst.migrations()
    files = sorted(os.path.relpath(os.path.join(dp, fn), app_dir) for dp, _, fns in os.walk(app_dir) for fn in fns)
    res = {"exact": [], "trim": [], "present": [], "migration_done": [], "bad": [], "missing": [], "file_size_field_differs": []}
    for p in files:
        src = open(os.path.join(app_dir, p), "rb").read()
        if p.startswith("migrations/"):
            name = os.path.splitext(os.path.basename(p))[0]
            (res["migration_done"] if migs.get(name) == "done" else res["missing"]).append(p); continue
        if p not in inv: res["missing"].append(p); continue
        k, r = inv[p]
        if k == "assets":
            got = urllib.request.urlopen(urllib.request.Request(r["url"], headers={"Accept": "*/*", "User-Agent": "seedling-qa-verify"}), timeout=90).read()
            ok = hashlib.sha256(got).hexdigest() == hashlib.sha256(src).hexdigest()
            if r["file_size"] != len(src): res["file_size_field_differs"].append(p)
            (res["exact"] if ok else res["bad"]).append(p if ok else [p, "sha256 differs", len(got), len(src)]); continue
        if k in ("tables", "profiles"):
            names = sorted(x["name"] for x in r["properties"])
            want = sorted(re.findall(r"^- name:\s*(\S+)", src.decode(), re.M))
            (res["present"] if names == want else res["bad"]).append(p if names == want else [p, "properties", names, want]); continue
        c = r.get(FIELD[k]) or ""; exp = body(src.decode())
        if c == exp: res["exact"].append(p)
        elif c.strip() == exp.strip(): res["trim"].append(p)
        else: res["bad"].append([p, k, len(c), len(exp)])
    pre_paths = set().union(*[set(pre[k]) for k in T if k in pre])
    extra = sorted(p for p in inv if not p.startswith("modules/") and p not in files and p not in pre_paths and p not in fixture_paths)
    total = len(files)
    accounted = len(res["exact"]) + len(res["trim"]) + len(res["present"]) + len(res["migration_done"])
    lines = [f"release files {total}: identical {len(res['exact'])} (assets by SHA-256: {sum(1 for x in res['exact'] if x.startswith('assets/'))}), "
             f"identical after leading/trailing whitespace {len(res['trim'])}, schema present with matching properties {len(res['present'])}, "
             f"migrations recorded done {len(res['migration_done'])}, MISMATCH {len(res['bad'])}, MISSING {len(res['missing'])}, EXTRA on instance {len(extra)}",
             f"accounted for: {accounted} of {total}"]
    lines += [f"PROBLEM {x}" for x in res["bad"] + res["missing"]] + [f"EXTRA {x}" for x in extra]
    if res["file_size_field_differs"]:
        lines.append(f"observed: the asset record's file_size field differs from the byte length for {len(res['file_size_field_differs'])} assets; the served bytes are what is compared")
    json.dump({"res": res, "extra": extra, "files": files}, open(out_path, "w"), indent=1)
    ok = not res["bad"] and not res["missing"] and not extra and accounted == total
    return ok, accounted, total, lines

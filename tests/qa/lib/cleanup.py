"""Clean-up: remove exactly what a run added, worked out from the pre-run snapshot, and put back the pages
the deploy overwrote. Only paths the run staged, users matching QA_EMAIL_PATTERN, records added to the
Seedling tables since the snapshot, and the constants the run set are ever deleted. One item per
insites-cli exec graphql call, with the instance guard every 25 items."""
import json
import os
import time

MUT = {"pages": "admin_page_delete", "partials": "admin_liquid_partial_delete", "layouts": "admin_liquid_layout_delete", "graphql": "admin_graphql_delete",
       "policies": "admin_authorization_policy_delete", "emails": "admin_email_notification_delete", "forms": "admin_form_delete",
       "api_calls": "admin_api_call_notification_delete", "assets": "admin_asset_delete", "tables": "admin_table_delete", "profiles": "admin_user_profile_schema_delete"}
FILE_KINDS = ["pages", "partials", "layouts", "graphql", "policies", "emails", "api_calls", "forms", "assets"]
SCHEMA_KINDS = ["tables", "profiles"]


def staged_paths(stage_app):
    """Instance paths (physical_file_path) of everything in the staged app/ folder."""
    out = set()
    for dp, _, fns in os.walk(stage_app):
        for fn in fns:
            out.add(os.path.relpath(os.path.join(dp, fn), stage_app))
    return out


def build(inst, pre, post, staged, email_re, constants_set):
    """The clean-up list, and anything that looks added but is not the run's to delete (reported, never deleted)."""
    items, foreign = [], []
    for t, before in pre["seedling_records"].items():
        for i in sorted(set(post["seedling_records"].get(t, [])) - set(before), key=int):
            items.append(("records", f"record {t} {i}", 'mutation { r: record_delete(id: "%s", table: "%s") { id } }' % (i, t), f'"id": "{i}"'))
    for i, em in sorted(post["users"].items(), key=lambda x: int(x[0])):
        if i in pre["users"]: continue
        if email_re.match(em or ""):
            items.append(("users", f"user {i} {em}", 'mutation { r: user_delete(id: "%s") { id email } }' % i, f'"email": "{em}"'))
        else:
            foreign.append(f"user {i} {em} (does not match QA_EMAIL_PATTERN)")
    for group, kinds in (("files", FILE_KINDS), ("schema", SCHEMA_KINDS)):
        for k in kinds:
            for path in sorted(set(post[k]) - set(pre[k])):
                if path in staged:
                    items.append((group, f"{k} {path}", 'mutation { r: %s(physical_file_path: "%s") { id physical_file_path } }' % (MUT[k], path), f'"physical_file_path": "{path}"'))
                else:
                    foreign.append(f"{k} {path} (not staged by this run)")
    for n in sorted(set(post["constants"]) - set(pre["constants"])):
        if n in constants_set:
            items.append(("constants", f"constant {n}", 'mutation { r: constant_unset(name: "%s") { name } }' % n, f'"name": "{n}"'))
        else:
            foreign.append(f"constant {n} (not set by this run)")
    return items, foreign


def run(inst, items, log_path):
    good = bad = 0; failed = []
    with open(log_path, "a") as log:
        for i, (group, label, q, expect) in enumerate(items):
            if i % 25 == 0: inst.guard("clean-up")
            r = inst.gql(q, allow_errors=True); ok = expect in json.dumps(r)
            log.write(json.dumps({"at": time.strftime("%H:%M:%S"), "item": label, "ok": ok, "res": r}) + "\n")
            good += ok; bad += not ok
            if not ok: failed.append((label, json.dumps(r)[:200]))
    return good, bad, failed


def save_pages(inst, paths, out_path):
    """The full record of each pre-existing page the deploy will overwrite (System Pages' home page, for one)."""
    saved = []
    for path in sorted(paths):
        d = inst.gql('query { r: admin_pages(per_page: 2, filter: { physical_file_path: { value: %s } }) { results { id physical_file_path slug content layout max_deep_level metadata } } }' % json.dumps(path))["r"]["results"]
        saved += [x for x in d if x["physical_file_path"] == path]
    json.dump(saved, open(out_path, "w"), indent=1)
    os.chmod(out_path, 0o600)
    return saved


def restore_pages(inst, saved):
    out = []
    for a in saved:
        meta = "{" + ", ".join(f"{k}: {json.dumps(v)}" for k, v in (a.get("metadata") or {}).items()) + "}"
        q = 'mutation { r: admin_page_update(id: "%s", page: { content: %s, layout: %s, max_deep_level: %d, metadata: %s }) { id physical_file_path } }' % (
            a["id"], json.dumps(a["content"]), json.dumps(a["layout"]), a["max_deep_level"] or 0, meta)
        r = inst.guarded_gql(q, allow_errors=True)
        out.append((a["physical_file_path"], "errors" not in r))
    return out

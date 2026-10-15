"""Read-only snapshot of every file record, table, profile type, user, constant name and migration on the
instance, with a SHA-256 of each content field so a changed file shows as well as an added or removed one.
Constant values are hashed, never stored or printed. Also keeps the record ids in the Seedling tables, so
clean-up removes only the records a run added."""
import hashlib
import json
import re

TYPES = {
    "pages": ("admin_pages", "physical_file_path slug request_method content layout format metadata"),
    "partials": ("admin_liquid_partials", "physical_file_path path body metadata"),
    "layouts": ("admin_liquid_layouts", "physical_file_path path body metadata"),
    "graphql": ("admin_graphql", "physical_file_path name query_string"),
    "policies": ("admin_authorization_policies", "physical_file_path name content"),
    "emails": ("admin_email_notifications", "physical_file_path name content"),
    "forms": ("admin_forms", "physical_file_path name liquid_body"),
    "api_calls": ("admin_api_call_notifications", "physical_file_path name content to"),
    "tables": ("admin_tables", "physical_file_path name properties { name attribute_type } records_count_rc"),
    "profiles": ("admin_user_profile_schemas", "physical_file_path name properties { name attribute_type }"),
    "assets": ("admin_assets", "physical_file_path file_size updated_at"),
}
SEEDLING_TABLES = ["sign_in_code", "sign_in_link", "auth_attempt", "documentation"]


def h(v): return hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()[:16]


def paged(inst, query_name, fields, extra=""):
    rows, page = [], 1
    while True:
        d = inst.gql('query { r: %s(per_page: 100, page: %d%s) { total_entries total_pages results { id %s } } }' % (query_name, page, extra, fields))["r"]
        rows += d["results"]
        if page >= (d["total_pages"] or 1): break
        page += 1
    assert len(rows) == d["total_entries"], (query_name, len(rows), d["total_entries"])
    return rows


def record_ids(inst, table):
    d = inst.gql('query { r: records(per_page: 1, filter: { table: { value: "%s" } }) { total_entries } }' % table, allow_errors=True)
    if d.get("errors") or not (d.get("data") or {}).get("r"):
        return []
    rows = paged(inst, "records", "", ', filter: { table: { value: "%s" } }' % table)
    return sorted(str(r["id"]) for r in rows)


def take(inst, path):
    out = {}
    for k, (q, fields) in TYPES.items():
        rows = paged(inst, q, fields)
        out[k] = {r["physical_file_path"]: {"id": r["id"], "sha": h({f: r.get(f) for f in re.sub(r"\{[^}]*\}", "", fields).split() if f not in ("physical_file_path", "records_count_rc", "updated_at")}),
                                            **({"records": r["records_count_rc"]} if k == "tables" else {}), **({"name": r.get("name")} if "name" in r else {})} for r in rows}
    users = paged(inst, "users", "email")
    out["users"] = {str(u["id"]): u["email"] for u in users}
    c = inst.gql('query { c: constants(per_page: 200) { total_entries results { name value updated_at } } }')["c"]
    assert len(c["results"]) == c["total_entries"]
    out["constants"] = {r["name"]: {"sha": h(r["value"]), "updated_at": r["updated_at"]} for r in c["results"]}
    out["migrations"] = sorted(inst.migrations().items())
    out["sent_notifications_total"] = inst.gql('query { n: admin_sent_notifications(per_page: 1) { total_entries } }')["n"]["total_entries"]
    out["seedling_records"] = {t: record_ids(inst, t) for t in SEEDLING_TABLES}
    json.dump(out, open(path, "w"), indent=1, sort_keys=True)
    return out


def summary(s):
    return ", ".join(f"{k} {len(s[k])}" for k in list(TYPES) + ["users", "constants", "migrations"]) + f", sent-log rows {s['sent_notifications_total']}"


def diff(a, b):
    """Every difference between two snapshots, except the sent log, which only ever grows."""
    lines = []
    for k in sorted(set(a) | set(b)):
        if k in ("sent_notifications_total",):
            continue
        x, y = a.get(k), b.get(k)
        if k == "seedling_records":
            for t in sorted(set(x or {}) | set(y or {})):
                xs, ys = set((x or {}).get(t, [])), set((y or {}).get(t, []))
                lines += [f"ADDED   record {t} {i}" for i in sorted(ys - xs)] + [f"REMOVED record {t} {i}" for i in sorted(xs - ys)]
            continue
        if isinstance(x, list):
            x, y = {tuple(i): 1 for i in x}, {tuple(i): 1 for i in (y or [])}
        x, y = x or {}, y or {}
        for p in sorted(set(x) | set(y), key=str):
            if p not in y: lines.append(f"REMOVED {k} {p}")
            elif p not in x: lines.append(f"ADDED   {k} {p}")
            elif x[p] != y[p]: lines.append(f"CHANGED {k} {p}")
    return lines

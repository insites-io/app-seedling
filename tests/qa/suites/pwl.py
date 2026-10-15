"""Suite pwl: passwordless sign-in by emailed code and emailed link. Ported from the QA harness that passed
at e88460e. One real code email and one real link email prove delivery; every other code and link is
minted by the fixture through the app's own hash partial, return_to cleaning and named queries, so it
sends nothing. Limits are reached by inserting the earlier attempt rows."""
import html
import json
import re
import threading
import time as T
import urllib.parse

from lib.client import *          # noqa: F401,F403
from lib import client as C
from lib.registry import block, result, observed

E = emails_for("pwl")
pws, ids, secs = {}, {}, {}
NOBODY = lambda n: E(f"nobody-{n}")


def code_rows(em): return state(em)["attempts"]["codes"]["results"]
def link_rows(em): return state(em)["attempts"]["links"]["results"]
def slots(table, rid): return [s["external_id"] for s in admin(op="slots", table=table, rid=rid)["slots"]["results"]]
def checks(em): return [r for r in state(em)["attempts"]["by_email"]["results"] if r["action"] == "sign_in_code_check"]
def row_by_id(rows_, rid): return [x for x in rows_ if str(x["id"]) == str(rid)][0]


def get_code(em, return_to=""):
    """A pending code for em, minted (no email). Returns (code, row)."""
    code, rid = mint_code(em, return_to=return_to)
    return code, row_by_id(code_rows(em), rid)


def get_link(em, return_to=""):
    link, rid = mint_link(em, return_to=return_to)
    return link, row_by_id(link_rows(em), rid)


def real_link(em):
    """The one real link email of the run (delivered in c8_20), or a new one if it is missing or near expiry."""
    d = C.DELIVERED.get("sign-in link")
    if d and d[3] == em and T.time() - d[4]["t"] < 600:
        return d[0], d[4]["row"], d[1]
    C.DELIVERED.pop("sign-in link", None)
    BUDGET.expect("sign-in link")
    s = S("deliver-link"); after = last_mail_id(); r = req_link(s, em)
    assert p(r) == "/sign-in/email-link?sent=1", ("request refused", r[:2])
    m = wait_mail(em, after, SUBJECT_LINK); assert m, "no link email within 90 s"
    link = html.unescape(link_in(m[-1])); row = link_rows(em)[-1]
    C.DELIVERED["sign-in link"] = (link, m[-1], s, em, {"t": T.time(), "row": row})
    return link, row, m[-1]


def setup_2fa(n):
    em = E(n); A = S(f"2fa-setup-{n}")
    A.sign_in(em, pws[em]); b = A.get("/profile", tag="profile")[2]
    sec = re.search(r'<pre id="setup_code">([A-Z0-9]+)</pre>', b).group(1)
    r = A.otp(unused_code(em, sec), from_page="profile", csrf_from="/profile")
    st = state(em)["user"]; secs[em] = sec
    return st["client"][0]["otp_configured"] is True


def cf_decode(b):
    """The edge may rewrite an email address in HTML into data-cfemail (XOR with the first byte); a browser decodes it with JS. Decode it the same way."""
    def dec(m):
        h_ = m.group(1); k = int(h_[:2], 16)
        return "".join(chr(int(h_[i:i + 2], 16) ^ k) for i in range(2, len(h_), 2))
    return re.sub(r'<a href="/cdn-cgi/l/email-protection" class="__cf_email__" data-cfemail="([0-9a-f]+)">\[email&#160;protected\]</a>', dec, b)


def norm(b, em):
    """A page with the address and every token-like string taken out, so two answers can be compared."""
    return re.sub(r"[A-Za-z0-9_\-]{40,}", "TOKEN", b.replace(html.escape(em), "ADDR").replace(em, "ADDR"))


# ---------------------------------------------------------------- blocks

@block("pwl", "setup", [], setup=True)
def b_setup():
    """Create 20 users with a client profile and one without, and turn 2FA on for 10, 11, 12, 16 and 18."""
    for n in list(range(1, 21)) + ["nc"]:
        ids[E(n)], pws[E(n)] = create_user(E(n), client=n != "nc")
    for n in (10, 11, 12, 16, 18):
        assert setup_2fa(n), f"2FA set-up failed for {E(n)}"
    clear("otp")


@block("pwl", "smoke", ["smoke register", "smoke password sign-in, /dashboard, /profile", "smoke 2FA set-up and /verify-2fa", "smoke sign-out",
                        "smoke forgot password and reset", "smoke 401/403/404/500 served by System Pages; signed-out redirects"], emails=1)
def b_smoke():
    """The move smoke test. The reset email is real only if this run has not already proved that template."""
    clear("forgot_password", "otp", "email_check")
    stamp = str(int(T.time())); em = E(f"smoke{stamp}"); pw = new_password()
    R = S("smoke-reg"); b = R.get("/register", tag="smoke-reg-form")[2]
    r = R.post("/register", {"first_name": "Smoke", "last_name": "Test", "email": em, "password": pw, "authenticity_token": form_token(b)}, tag="smoke-register")
    st = state(em)["user"] or {}
    result("smoke register", p(r) == "/account-created" and [x["profile_type"] for x in st.get("profiles", [])] == ["client"] and st["client"][0]["otp_configured"] is False,
           f"POST /register -> {r[0]} {p(r)}; profiles {[x['profile_type'] for x in st.get('profiles', [])]}; otp_configured {st.get('client', [{}])[0].get('otp_configured')}")
    A = S("smoke-pw"); r = A.sign_in(em, pw); d = A.get("/dashboard", tag="smoke", keep_body=True); pr = A.get("/profile", tag="smoke")
    result("smoke password sign-in, /dashboard, /profile", p(r) == "/dashboard" and d[0] == 200 and "sign-out" in d[2] and pr[0] == 200, f"sign-in -> {p(r)}; /dashboard {d[0]} ({len(d[2])} bytes, sign-out present {'sign-out' in d[2]}); /profile {pr[0]}")
    b = A.get("/profile", tag="smoke")[2]; sec = re.search(r'<pre id="setup_code">([A-Z0-9]+)</pre>', b).group(1)
    r1 = A.otp(unused_code(em, sec), from_page="profile", csrf_from="/profile"); on = state(em)["user"]["client"][0]["otp_configured"]
    B = S("smoke-2fa"); r2 = B.sign_in(em, pw); d2 = signed_in(B); r3 = B.otp(wrong_code(sec)); r4 = B.otp(unused_code(em, sec)); d4 = signed_in(B)
    result("smoke 2FA set-up and /verify-2fa", p(r1) == "/profile?status=success" and on is True and p(r2) == "/verify-2fa" and d2 == (302, "/verify-2fa?return_to=%2Fdashboard") and p(r3) == "/verify-2fa?status=failed" and p(r4) == "/dashboard" and d4[0] == 200,
           f"set-up -> {p(r1)}, otp_configured {on}; sign-in -> {p(r2)}; /dashboard before code {d2}; wrong -> {p(r3)}; right -> {p(r4)}; /dashboard {d4[0]}")
    tk = form_token(B.get("/dashboard", tag="smoke-so-form")[2]); so = B.post("/sign-out", {"authenticity_token": tk}, tag="smoke-sign-out"); d5 = signed_in(B); si = B.get("/sign-in", tag="smoke")
    result("smoke sign-out", p(so) == "/sign-out" and d5 == (302, "/sign-in?return_to=%2Fdashboard") and si[0] == 200,
           f"sign-out -> {so[0]} {p(so)}; /dashboard after {d5}; /sign-in {si[0]}")
    F_ = S("smoke-forgot"); t0 = T.time()
    if "password reset" in BUDGET.by_kind:
        rf = (302, BASE + "/forgot-password?sent=1", ""); m = ["proved earlier in this run"]
        tok = admin(op="mint", email=em, hours=0.25)["token"]; q = {"email": em, "token": tok}
        how_mail = "reset email already proved in this run, so the token was minted where forgot-password stores it (no email)"
    else:
        BUDGET.expect("password reset")
        after = last_mail_id(); rf = forgot(F_, em)
        m = wait_mail(em, after, SUBJECT_RESET)
        url = html.unescape(re.search(r'href="([^"]*password-reset\?token=[^"]*)"', m[-1]["content"]).group(1)) if m else ""
        q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()}
        how_mail = f"reset email {bool(m)} after {round(T.time() - t0, 1)}s"
    st_, shown, inv, c = reset_form(F_, q.get("email", ""), q.get("token", "")); npw = new_password()
    rr = reset_submit(F_, q.get("email", ""), q.get("token", ""), npw, c)
    n1 = p(S("smoke-new").sign_in(em, npw)); o1 = p(S("smoke-old").sign_in(em, pw))
    result("smoke forgot password and reset", p(rf) == "/forgot-password?sent=1" and bool(m) and shown and p(rr) == "/password-reset?reset=done" and n1 == "/verify-2fa" and o1 == "/sign-in?error=invalid",
           f"forgot -> {p(rf)}; {how_mail}; form {shown}; submit -> {p(rr)}; new pw -> {n1}; old pw -> {o1}")
    out = {}
    for pth in ["/401", "/403", "/404", "/500", "/no-such-page-seedling-qa"]:
        st_, loc, b = S("sp").get(pth, tag="smoke-sp", keep_body=True)
        t = re.search(r"<title>([^<]*)</title>", b); out[pth] = (st_, t.group(1).strip() if t else None, "system_pages" in b)
    anon = {pth: (S("an").get(pth, tag="smoke-anon")[0], p(S("an").get(pth, tag="smoke-anon"))) for pth in ["/dashboard", "/profile", "/verify-2fa"]}
    want = {"/401": (200, "401 - Unauthorized", True), "/403": (200, "403 - Forbidden Access", True), "/404": (404, "404 - Page Not Found", True), "/500": (500, "500 - Server Error", True), "/no-such-page-seedling-qa": (404, "404 - Page Not Found", True)}
    wanta = {"/dashboard": (302, "/sign-in?return_to=%2Fdashboard"), "/profile": (302, "/sign-in?return_to=%2Fprofile"), "/verify-2fa": (302, "/403?return_to=%2Fverify-2fa")}
    result("smoke 401/403/404/500 served by System Pages; signed-out redirects", out == want and anon == wanta, f"(status, title, System Pages markup) {out}; signed out {anon}")


@block("pwl", "c1", ["1a password sign-in still goes to /dashboard", "1b /sign-in shows three choices", "1c return_to carried onto both email buttons"])
def b_c1():
    """The sign-in page."""
    em = E(1)
    A = S("c1"); st, loc, b = A.get("/sign-in", tag="c1-sign-in")
    has_pw = 'id="sign-in-form"' in b and 'name="password"' in b
    btns = re.findall(r'href="(/sign-in/email-(?:link|code)[^"]*)"', b)
    r = A.sign_in(em, pws[em]); d = signed_in(A)
    result("1a password sign-in still goes to /dashboard", p(r) == "/dashboard" and d[0] == 200, f"POST /sign-in -> {p(r)}, GET /dashboard -> {d[0]}")
    result("1b /sign-in shows three choices", has_pw and sorted(btns) == ["/sign-in/email-code", "/sign-in/email-link"], f"password form present={has_pw}, email buttons={btns}")
    B = S("c1-rt"); b = B.get("/sign-in?return_to=%2Fprofile", tag="c1-rt")[2]
    btns = re.findall(r'href="(/sign-in/email-(?:link|code)[^"]*)"', b)
    ok = sorted(btns) == ["/sign-in/email-code?return_to=%2Fprofile", "/sign-in/email-link?return_to=%2Fprofile"]
    hid = [re.search(r'name="return_to" value="([^"]*)"', B.get(u, tag="c1-rt-form")[2]).group(1) for u in sorted(btns)]
    result("1c return_to carried onto both email buttons", ok and hid == ["/profile", "/profile"], f"buttons={btns}; hidden return_to on each request page={hid}")


@block("pwl", "c8_20", ["8 code request, unknown", "8 code request, no client profile", "20 link request, unknown", "20 link request, no client profile"], emails=2)
def b_c8_20():
    """Unknown address and a user with no client profile get the real address's answer and no email. The real
    address's code and link are the run's two delivery proofs (one email each)."""
    clear("sign_in_code", "sign_in_link", "sign_in_code_check")
    after = last_mail_id(); out = {}
    BUDGET.expect("sign-in code"); BUDGET.expect("sign-in link")
    for label, em in [("real", E(13)), ("unknown", NOBODY(7)), ("no client profile", E("nc"))]:
        a = S("c8-" + label); r = req_code(a, em); b1 = a.get(p(r), tag="c8-sent")[2]
        bb = S("c20-" + label); r2 = req_link(bb, em); b2 = bb.get(p(r2), tag="c20-sent")[2]
        st = state(em); out[label] = (em, p(r), p(r2), [x["status"] for x in st["attempts"]["codes"]["results"]], [x["status"] for x in st["attempts"]["links"]["results"]],
                                      norm(b1, em), norm(b2, em))
    rc = wait_mail(E(13), after, SUBJECT_CODE); rl = wait_mail(E(13), after, SUBJECT_LINK)
    T.sleep(15)
    for label, (em, r1, r2, cs, ls, b1, b2) in out.items():
        out[label] = out[label] + (len(mails_to(em, after)),)
    code = code_in(rc[-1]) if rc else None
    ok_code = False
    if code:
        X = S("c8-real-code"); ok_code = p(submit_code(X, E(13), code)) == "/dashboard" and signed_in(X)[0] == 200
        C.DELIVERED["sign-in code"] = (code, rc[-1], X, E(13))
    if rl:
        C.DELIVERED["sign-in link"] = (html.unescape(link_in(rl[-1])), rl[-1], None, E(13), {"t": T.time(), "row": link_rows(E(13))[-1]})
    real = out["real"]
    for case, i, rows_i, kind in [("8", 1, 3, "code"), ("20", 2, 4, "link")]:
        for label in ("unknown", "no client profile"):
            o = out[label]
            same_page = o[5 + (i - 1)] == real[5 + (i - 1)]
            ok = o[i] == real[i] and o[rows_i][-1:] == ["miss"] and o[7] == 0 and same_page and real[7] == 2 and (ok_code if kind == "code" else bool(rl))
            result(f"{case} {kind} request, {label}", ok, f"-> {o[i]} (real address -> {real[i]}); rows {o[rows_i]}; emails {o[7]} (real address got {real[7]}: one code, one link; its emailed code signs in: {ok_code}); next page identical to the real one: {same_page}")


@block("pwl", "link", ["14 link request", "15 opening the link", "16 Continue", "17 reused link", "18 tampered links"], emails=1)
def b_link():
    """14 to 18 on the run's real link email, then tampered copies of minted links."""
    clear("sign_in_link")
    em = E(13); link, row, m = real_link(em)
    raw = re.search(r'<a href="([^"]+)" target="_blank"', m["content"]).group(1)
    u = urllib.parse.urlparse(link); q = urllib.parse.parse_qs(u.query)
    exp = T.mktime(T.strptime(row["expires_at"][:19], "%Y-%m-%dT%H:%M:%S")) - T.mktime(T.strptime(row["created_at"][:19], "%Y-%m-%dT%H:%M:%S"))
    ok = (f"{u.scheme}://{u.netloc}" == BASE and u.path == "/sign-in/link" and list(q) == ["e", "t", "n"] and q["e"] == [em] and "&amp;t=" in raw and "&amp;n=" in raw
          and "&t=" not in raw and row["status"] == "pending" and 895 <= exp <= 905 and q["n"][0] == row["nonce"])
    result("14 link request", ok, f"row {row['status']}, expires_at-created_at={exp:.0f}s; href in the email HTML uses &amp;: {'&amp;t=' in raw and '&amp;n=' in raw}; unescaped link {u.scheme}://{u.netloc}{u.path}?{'&'.join(q)}; e matches={q['e'] == [em]}; n matches stored nonce={q['n'][0] == row['nonce']}")
    A = S("c15-A"); a, b = open_link(A, link)
    shows = f"You are signing in as <strong>{em}</strong>" in cf_decode(b[2]) and 'label="CONTINUE"' in b[2]
    cf = "__cf_email__" in b[2]
    no_tok = q["t"][0] not in b[2] and q["n"][0] not in b[2]
    a2, b2 = open_link(A, link); B = S("c15-B"); a3, b3 = open_link(B, link)
    rr = row_by_id(link_rows(em), row["id"]); sl = slots("sign_in_link", row["id"])
    result("15 opening the link", a[0] == 302 and p(a) == "/sign-in/link" and b[0] == 200 and shows and no_tok and p(a2) == "/sign-in/link" and b2[0] == 200 and b3[0] == 200 and rr["status"] == "pending" and sl == [] and signed_in(A)[0] == 302,
           f"GET link -> {a[0]} {p(a)}; page {b[0]} shows the address and Continue={shows} (edge email-obfuscation markup present={cf}); token/nonce absent from page={no_tok}; opened twice -> {a2[0]}/{b2[0]}, second browser -> {a3[0]}/{b3[0]}; row still {rr['status']}, slots {sl}; not signed in")
    r = cont(A, body=b2[2]); d = signed_in(A)
    rr = row_by_id(link_rows(em), row["id"]); sl = slots("sign_in_link", row["id"])
    result("16 Continue", p(r) == "/dashboard" and d[0] == 200 and rr["status"] == "consumed" and sl == [f"{row['id']}-use-1"], f"-> {p(r)}, /dashboard {d[0]}; row {rr['status']}; slots {sl}")
    rB = cont(B, body=b3[2])
    C17 = S("c17"); a4, b4 = open_link(C17, link)
    result("17 reused link", p(a4) == "/sign-in/link" and p(b4) == "/sign-in/email-link?error=stale" and p(rB) == "/sign-in/email-link?error=stale" and signed_in(B)[0] == 302,
           f"fresh session opens it -> {p(a4)} then {b4[0]} {p(b4)}; the second browser's Continue (opened before use) -> {p(rB)}")
    link, row = get_link(em); q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(link).query).items()}
    link2, row2 = get_link(E(14)); q2 = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(link2).query).items()}
    def mk(d): return BASE + "/sign-in/link?" + urllib.parse.urlencode(d)
    variants = {"tampered n": dict(q, n=q["n"][:-1] + ("A" if q["n"][-1] != "A" else "B")), "swapped e (another account)": dict(q, e=E(14)),
                "swapped e (unknown)": dict(q, e=NOBODY(7)), "changed t": dict(q, t=q["t"][:-2] + ("aa" if q["t"][-2:] != "aa" else "bb")),
                "t from another account": dict(q, t=q2["t"]), "n from another account": dict(q, n=q2["n"])}
    outs = {}
    for k, d in variants.items():
        X = S("c18"); a, b = open_link(X, mk(d)); outs[k] = (p(a), p(b) if b else None)
    rr = row_by_id(link_rows(em), row["id"])
    ok = all(v == ("/sign-in/link", "/sign-in/email-link?error=stale") for v in outs.values())
    ctrl = S("c18-ctrl"); a, b = open_link(ctrl, link)
    result("18 tampered links", ok and rr["status"] == "pending" and b[0] == 200, f"{outs}; untouched link still opens: {b[0]}; row {rr['status']}")


@block("pwl", "code_basic", ["3 wrong code", "2 right code", "2 right code (first try)", "6 reused code from a fresh session", "7 A's code with another address", "9 malformed code"])
def b_code_basic():
    """Cases 2, 3, 6, 7 and 9 on minted codes."""
    clear("sign_in_code", "sign_in_code_check")
    em, em2 = E(1), E(2)
    code, row = get_code(em)
    wrong = "%06d" % ((int(code) + 1) % 1000000)
    before = len(checks(em))
    r = submit_code(S("c3"), em, wrong)
    row3 = row_by_id(code_rows(em), row["id"]); sl = slots("sign_in_code", row["id"]); after = len(checks(em))
    result("3 wrong code", p(r) == "/sign-in/code?error=invalid" and row3["status"] == "pending" and sl == [f"{row['id']}-try-1"] and after - before == 1,
           f"-> {p(r)}; row {row['id']} status={row3['status']}; slots={sl}; sign_in_code_check rows {before}->{after}")
    X = S("c2"); r = submit_code(X, em, code); d = signed_in(X)
    row2 = row_by_id(code_rows(em), row["id"]); sl = slots("sign_in_code", row["id"])
    result("2 right code", p(r) == "/dashboard" and d[0] == 200 and row2["status"] == "consumed" and sl == [f"{row['id']}-try-1", f"{row['id']}-try-2", f"{row['id']}-use-1"],
           f"-> {p(r)}, /dashboard {d[0]}; row status={row2['status']}; slots={sl} (try-1 was the wrong code in case 3, so the right code took try-2)")
    code, row = get_code(em)
    X = S("c2b"); r = submit_code(X, em, code); d = signed_in(X)
    row2 = row_by_id(code_rows(em), row["id"]); sl = slots("sign_in_code", row["id"])
    result("2 right code (first try)", p(r) == "/dashboard" and d[0] == 200 and row2["status"] == "consumed" and sl == [f"{row['id']}-try-1", f"{row['id']}-use-1"],
           f"-> {p(r)}, /dashboard {d[0]}; row status={row2['status']}; slots={sl}")
    Y = S("c6"); r = submit_code(Y, em, code); d = signed_in(Y)
    result("6 reused code from a fresh session", p(r) == "/sign-in/code?error=invalid" and d[0] == 302, f"-> {p(r)}, /dashboard {d[0]} {d[1]}")
    codeA, rowA = get_code(em); codeB, rowB = get_code(em2)
    Z = S("c7"); r = submit_code(Z, em2, codeA); d = signed_in(Z)
    rb = row_by_id(code_rows(em2), rowB["id"])
    ctrl = S("c7-ctrl"); rc = submit_code(ctrl, em, codeA)
    result("7 A's code with another address", p(r) == "/sign-in/code?error=invalid" and d[0] == 302 and rb["status"] == "pending" and p(rc) == "/dashboard",
           f"B's address + A's code -> {p(r)}, /dashboard {d[0]}; B's row still {rb['status']}; control: A's address + same code -> {p(rc)}")
    code, row = get_code(em2)
    outs = []
    for bad in ["12345", "1234567", "abcdef", "12a456", "", "１２３４５６"]:
        r = submit_code(S("c9"), em2, bad); outs.append((bad, p(r)))
    sl = slots("sign_in_code", row["id"])
    result("9 malformed code", all(o == "/sign-in/code?error=invalid" for _, o in outs) and sl == [], f"{outs}; slots on the live request after all six={sl}")


@block("pwl", "c4", ["4 five wrong then right"])
def b_c4():
    """A code dies after five wrong guesses."""
    clear("sign_in_code", "sign_in_code_check")
    em = E(2); code, row = get_code(em)
    outs = []
    for i in range(5):
        outs.append(p(submit_code(S(f"c4-{i}"), em, "%06d" % ((int(code) + 11 + i) % 1000000))))
    X = S("c4-right"); r = submit_code(X, em, code); d = signed_in(X)
    rr = row_by_id(code_rows(em), row["id"]); sl = slots("sign_in_code", row["id"])
    ok = outs[:4] == ["/sign-in/code?error=invalid"] * 4 and outs[4] == "/sign-in/code?error=too_many" and p(r) == "/sign-in/code?error=too_many" and rr["status"] == "killed" and d[0] == 302 and "use-1" not in " ".join(sl)
    result("4 five wrong then right", ok, f"wrong 1-5 -> {outs}; right -> {p(r)}; row {rr['status']}; slots={sl}; /dashboard {d[0]}")


@block("pwl", "c10", ["10a 6th request per address", "10b 21st request per IP", "10c 10 wrong codes in an hour block a fresh right code"])
def b_c10():
    """The code limits, reached by inserting the earlier rows. Each case has a control one below the limit."""
    clear("sign_in_code", "sign_in_code_check")
    em = E(4); after = last_mail_id()
    seed("sign_in_code", 5, key=em)
    r6 = p(req_code(S("c10-6"), em))
    ctl = NOBODY("10a"); seed("sign_in_code", 4, key=ctl)
    r5 = p(req_code(S("c10-5"), ctl)); ctl_rows = [x["status"] for x in code_rows(ctl)]
    T.sleep(20); n = len(mails_to(em, after, subject=SUBJECT_CODE)); rows_ = code_rows(em)
    result("10a 6th request per address", r6 == "/sign-in/email-code?error=too_many" and n == 0 and len(rows_) == 0 and r5 == "/sign-in/code?sent=1" and ctl_rows == ["miss"],
           f"5 earlier rows inserted, 6th request -> {r6}; code emails {n}; code rows {len(rows_)}; control, 4 rows then the 5th (unknown address) -> {r5}, rows {ctl_rows}")
    clear("sign_in_code")
    seed("sign_in_code", 20, key=NOBODY("ipfill"), ip="mine")
    em5 = E(5); after = last_mail_id(); r = p(req_code(S("c10ip-21"), em5))
    clear("sign_in_code"); seed("sign_in_code", 19, key=NOBODY("ipfill"), ip="mine")
    ctl = NOBODY("10b"); rc = p(req_code(S("c10ip-20"), ctl))
    clear("sign_in_code")
    T.sleep(20); n = len(mails_to(em5, after)); rows_ = code_rows(em5)
    result("10b 21st request per IP", r == "/sign-in/email-code?error=too_many" and n == 0 and rows_ == [] and rc == "/sign-in/code?sent=1",
           f"20 rows from this IP inserted, 21st (a real address) -> {r}; emails {n}; rows {len(rows_)}; control, 19 rows then the 20th -> {rc}")
    clear("sign_in_code", "sign_in_code_check")
    em = E(5); seed("sign_in_code_check", 10, key=em)
    nchk = len(checks(em))
    code, row = get_code(em)
    X = S("c10w-right"); r = submit_code(X, em, code); d = signed_in(X); sl = slots("sign_in_code", row["id"])
    rr = row_by_id(code_rows(em), row["id"])
    clear("sign_in_code_check"); seed("sign_in_code_check", 9, key=em)
    Y = S("c10w-ctl"); rc = submit_code(Y, em, code); dc = signed_in(Y)
    result("10c 10 wrong codes in an hour block a fresh right code", p(r) == "/sign-in/code?error=too_many" and d[0] == 302 and nchk == 10 and sl == [] and rr["status"] == "pending" and p(rc) == "/dashboard" and dc[0] == 200,
           f"10 sign_in_code_check rows inserted ({nchk}); fresh right code -> {p(r)}, /dashboard {d[0]}; its slots {sl}; row {rr['status']}; control, 9 rows then the same code -> {p(rc)}, /dashboard {dc[0]}")
    clear("sign_in_code_check")


def race(em, code, n, label):
    ss = [S(f"{label}-{i}") for i in range(n)]
    toks = []
    for s in ss:
        st, loc, b = s.get("/sign-in/code", tag=f"{label}-form"); toks.append(form_token(b))
    out = [None] * n; bar = threading.Barrier(n)
    def go(i):
        bar.wait(); out[i] = ss[i].post("/sign-in/code", {"email": em, "code": code, "authenticity_token": toks[i]}, tag=label)
    th = [threading.Thread(target=go, args=(i,)) for i in range(n)]; [t.start() for t in th]; [t.join() for t in th]
    dash = [signed_in(s)[0] for s in ss]
    return [p(o) for o in out], dash


@block("pwl", "c11", ["11a 16 simultaneous wrong guesses", "11a' right code after the race", "11b 2 simultaneous right codes",
                      "11b 8 simultaneous right codes", "11b 16 simultaneous right codes"])
def b_c11():
    """Simultaneous guesses and simultaneous right codes."""
    clear("sign_in_code", "sign_in_code_check")
    em = E(6); code, row = get_code(em)
    wrong = "%06d" % ((int(code) + 3) % 1000000)
    before = len(checks(em))
    outs, dash = race(em, wrong, 16, "c11-wrong16")
    sl = slots("sign_in_code", row["id"]); rr = row_by_id(code_rows(em), row["id"]); nchk = len(checks(em)) - before
    tries = [x for x in sl if "-try-" in x]
    result("11a 16 simultaneous wrong guesses", len(tries) <= 5 and nchk <= 5 and rr["status"] == "killed" and dash.count(200) == 0,
           f"answers {[(o, outs.count(o)) for o in sorted(set(outs))]}; try slots {len(tries)} of max 5; checked (sign_in_code_check rows) {nchk}; row {rr['status']}; signed in {dash.count(200)} of 16")
    X = S("c11-after"); r = submit_code(X, em, code)
    result("11a' right code after the race", p(r) == "/sign-in/code?error=too_many", f"-> {p(r)}")
    for n, u in ((2, 7), (8, 8), (16, 9)):
        clear("sign_in_code", "sign_in_code_check")
        em = E(u); code, row = get_code(em)
        outs, dash = race(em, code, n, f"c11-right{n}")
        sl = slots("sign_in_code", row["id"]); rr = row_by_id(code_rows(em), row["id"])
        result(f"11b {n} simultaneous right codes", outs.count("/dashboard") == 1 and dash.count(200) == 1 and [x for x in sl if x.endswith("-use-1")] == [f"{row['id']}-use-1"] and rr["status"] == "consumed",
               f"answers {[(o, outs.count(o)) for o in sorted(set(outs))]}; /dashboard 200 in {dash.count(200)} of {n} sessions; use slots {[x for x in sl if '-use-' in x]}; try slots {len([x for x in sl if '-try-' in x])}; row {rr['status']}")


@block("pwl", "c12", ["12a 2FA user by code", "12b 2FA user by link"])
def b_c12():
    """A 2FA user still passes 2FA after a passwordless sign-in."""
    clear("sign_in_code", "sign_in_link", "otp")
    em = E(10); code, row = get_code(em)
    X = S("c12-code"); r = submit_code(X, em, code); d = signed_in(X); pr = X.get("/profile", tag="c12-profile")
    v = X.otp(unused_code(em, secs[em])); d2 = signed_in(X)
    result("12a 2FA user by code", p(r) == "/verify-2fa" and d[0] == 302 and d[1].startswith("/verify-2fa") and pr[0] == 302 and p(v) == "/dashboard" and d2[0] == 200,
           f"code -> {p(r)}; /dashboard before 2FA -> {d}; /profile -> {pr[0]} {p(pr)}; TOTP -> {p(v)}; /dashboard after -> {d2[0]}")
    em = E(11); link, row = get_link(em)
    Y = S("c12-link"); a, b = open_link(Y, link); r = cont(Y, body=b[2]); d = signed_in(Y)
    v = Y.otp(unused_code(em, secs[em])); d2 = signed_in(Y)
    result("12b 2FA user by link", p(r) == "/verify-2fa" and d[0] == 302 and d[1].startswith("/verify-2fa") and p(v) == "/dashboard" and d2[0] == 200,
           f"Continue -> {p(r)}; /dashboard before 2FA -> {d}; TOTP -> {p(v)}; /dashboard after -> {d2[0]}")


@block("pwl", "lockout_probe", ["probe: 2FA lockout after sign-in by code", "probe: lockout holds for a new sign-in by link in the window"], emails=1)
def b_lockout_probe():
    """The 2FA lockout still applies after a passwordless sign-in. One real alert email."""
    clear("sign_in_code", "sign_in_link", "otp")
    em = E(16); after = last_mail_id()
    lk0 = len([x for x in state(em)["attempts"]["by_id"]["results"] if x["action"] == "otp_lockout"])
    code, row = get_code(em)
    X = S("lock-code"); r = submit_code(X, em, code)
    outs = [p(X.otp(wrong_code(secs[em]))) for _ in range(5)]
    BUDGET.expect("2FA lockout alert (after a passwordless sign-in)")
    right = p(X.otp(unused_code(em, secs[em]))); d = signed_in(X)
    st = state(em); lk = [x for x in st["attempts"]["by_id"]["results"] if x["action"] == "otp_lockout"]
    al = wait_mail(em, after, SUBJECT_ALERT, 60)
    result("probe: 2FA lockout after sign-in by code", p(r) == "/verify-2fa" and right == "/verify-2fa?status=failed" and d[0] == 302 and d[1].startswith("/verify-2fa") and len(lk) - lk0 == 1 and len(al) == 1,
           f"code -> {p(r)}; 5 wrong TOTP -> {outs}; right TOTP -> {right}; /dashboard {d}; new otp_lockout rows {len(lk) - lk0}; alert emails {len(al)}")
    link, row = get_link(em)
    Y = S("lock-link"); a, b = open_link(Y, link); r = cont(Y, body=b[2])
    right = p(Y.otp(unused_code(em, secs[em]))); d = signed_in(Y)
    result("probe: lockout holds for a new sign-in by link in the window", p(r) == "/verify-2fa" and right == "/verify-2fa?status=failed" and d[0] == 302 and d[1].startswith("/verify-2fa"),
           f"Continue -> {p(r)}; right TOTP -> {right}; /dashboard {d}")
    clear("otp", "otp_lockout")


@block("pwl", "c13", ["13 reset required after 3 lockouts"])
def b_c13():
    """Three lockout rows in 24 hours (inserted, so no alert emails) make code and link sign-in ask for a reset."""
    clear("sign_in_code", "sign_in_link", "otp")
    em = E(12); uid = ids[em]
    for back in (960, 1900, 2800):
        seed("otp_lockout", 1, key=uid, back=back)
    lk = [x for x in state(em)["attempts"]["by_id"]["results"] if x["action"] == "otp_lockout"]
    code, row = get_code(em)
    X = S("c13-code"); r = submit_code(X, em, code); d = signed_in(X); rr = row_by_id(code_rows(em), row["id"])
    link, lrow = get_link(em)
    Y = S("c13-link"); a, b = open_link(Y, link); r2 = cont(Y, body=b[2]); d2 = signed_in(Y)
    pw = S("c13-pw"); r3 = pw.sign_in(em, pws[em])
    result("13 reset required after 3 lockouts", len(lk) == 3 and p(r) == "/sign-in/code?error=reset" and p(r2) == "/sign-in/email-link?error=reset" and d[0] == 302 and d2[0] == 302,
           f"otp_lockout rows in 24 h: {len(lk)} (inserted); code -> {p(r)} (row now {rr['status']}); link -> {p(r2)}; /dashboard code={d[0]} link={d2[0]}; control: password sign-in -> {p(r3)}")


@block("pwl", "c19", ["19 2 simultaneous Continues", "19 8 simultaneous Continues"])
def b_c19():
    """Simultaneous Continue presses on one link."""
    for n, u in ((2, 15), (8, 17)):
        clear("sign_in_link")
        em = E(u); link, row = get_link(em)
        ss = [S(f"c19-{n}-{i}") for i in range(n)]; bodies = [open_link(x, link)[1][2] for x in ss]
        toks = [form_token(b) for b in bodies]; out = [None] * n; bar = threading.Barrier(n)
        def go(i):
            bar.wait(); out[i] = ss[i].post("/sign-in/link", {"authenticity_token": toks[i]}, tag=f"c19-{n}")
        th = [threading.Thread(target=go, args=(i,)) for i in range(n)]; [t.start() for t in th]; [t.join() for t in th]
        outs = [p(o) for o in out]; dash = [signed_in(x)[0] for x in ss]; sl = slots("sign_in_link", row["id"])
        rr = row_by_id(link_rows(em), row["id"])
        result(f"19 {n} simultaneous Continues", outs.count("/dashboard") == 1 and dash.count(200) == 1 and sl == [f"{row['id']}-use-1"] and rr["status"] == "consumed",
               f"answers {[(o, outs.count(o)) for o in sorted(set(outs))]}; /dashboard 200 in {dash.count(200)} of {n}; slots {sl}; row {rr['status']}")


@block("pwl", "fixation", ["probe: session fixation (password)", "probe: session fixation (code)", "probe: session fixation (link)"])
def b_fixation():
    """Does sign-in rotate the session cookie? For each method: the cookie before and after the request that signs
    in, an attacker holding the BEFORE value, and a control attacker holding the AFTER value."""
    clear("sign_in_code", "sign_in_link")
    import http.cookiejar as cj
    def cookie(s): return sess_cookies(s).get("_insites_session_id")
    def attacker(val, name):
        a = S(name); a.jar.set_cookie(cj.Cookie(0, "_insites_session_id", val, None, False, CFG.host, False, False, "/", True, True, None, False, None, None, {}))
        return signed_in(a)
    out = {}; em = E(14)
    for method in ("password", "code", "link"):
        V = S(f"fix-{method}")
        if method == "password":
            st, loc, b = V.get("/sign-in", tag="fix-form"); c0 = cookie(V)
            r = V.post("/sign-in", {"email": em, "password": pws[em], "authenticity_token": form_token(b)}, tag="fix-signin")
        elif method == "code":
            code, row = get_code(em); st, loc, b = V.get("/sign-in/code", tag="fix-form"); c0 = cookie(V)
            r = V.post("/sign-in/code", {"email": em, "code": code, "authenticity_token": form_token(b)}, tag="fix-signin")
        else:
            link, row = get_link(em); a, b = open_link(V, link); c0 = cookie(V)
            r = V.post("/sign-in/link", {"authenticity_token": form_token(b[2])}, tag="fix-signin")
        c1 = cookie(V); d = signed_in(V)[0]
        da = attacker(c0, f"fix-attacker-{method}"); dc = attacker(c1, f"fix-control-{method}")
        out[method] = {"sign-in answer": p(r), "victim /dashboard": d, "cookie value changed by the sign-in request": c0 != c1,
                       "attacker with the pre-sign-in cookie: /dashboard": da, "control, attacker with the post-sign-in cookie: /dashboard": dc}
    for m, v in out.items():
        result(f"probe: session fixation ({m})", v["victim /dashboard"] == 200 and v["attacker with the pre-sign-in cookie: /dashboard"][0] == 302 and v["control, attacker with the post-sign-in cookie: /dashboard"][0] == 200, json.dumps(v))


@block("pwl", "c21", ["21 SITE_ORIGIN unset"])
def b_c21():
    """With SITE_ORIGIN unset no link request is accepted. The constant is unset for this block only and put back
    with the value it had, in a finally."""
    clear("sign_in_link")
    value = INST.liquid("{{ context.constants.SITE_ORIGIN }}")
    assert value.startswith("https://"), "SITE_ORIGIN is not set, so this case cannot run (see QA_SET_SIGN_IN_CONSTANTS)"
    INST.constant_unset("SITE_ORIGIN")
    try:
        out = {}; after = last_mail_id(); addrs = [("real", E(3)), ("2FA", E(10)), ("unknown", NOBODY(8)), ("no client profile", E("nc"))]
        for label, em in addrs:
            before = len(link_rows(em)); r = req_link(S("c21"), em); out[label] = (p(r), len(link_rows(em)) - before)
    finally:
        INST.constant_set("SITE_ORIGIN", value)
    restored = INST.liquid("{{ context.constants.SITE_ORIGIN }}") == value
    T.sleep(20); n = sum(len(mails_to(em, after, subject=SUBJECT_LINK)) for _, em in addrs)
    ok = all(v == ("/sign-in/email-link?error=unavailable", 0) for v in out.values()) and n == 0 and restored
    result("21 SITE_ORIGIN unset", ok, f"{out} (answer, new rows); link emails {n}; SITE_ORIGIN restored to its earlier value {restored}")


C22_VALUES = [("/profile", "/profile"), ("https://evil.example", "/dashboard"), ("//evil.example", "/dashboard"), ("/\\evil.example", "/dashboard"),
              ("/\r\nSet-Cookie:x=1", "/dashboard"), ("/café", "/dashboard"), ("/verify-2fa", "/dashboard"), ("/api/users/id.json", "/dashboard"),
              ("/%0d%0aSet-Cookie:x=1", None)]
C22_CASES = [f"22 return_to {v!r} by {k}" for v, w in C22_VALUES if w for k in ("code", "link")] + ["22 return_to /profile, 2FA user", "22 request pages drop a bad return_to from the form"]


@block("pwl", "c22", C22_CASES)
def b_c22():
    """return_to attacks on both request kinds. For each value the real request page is posted for an unknown
    address (stores the cleaned value, sends nothing); a minted request for a real user stores the value through
    the same cleaning partial, and its code or link shows where the user lands."""
    out = []
    for v, want in C22_VALUES:
        for kind in ("code", "link"):
            if len(out) % 8 == 0: clear("sign_in_code", "sign_in_link", "sign_in_code_check")
            unk = NOBODY(f"c22-{len(out)}"); s = S(f"c22-{kind}")
            st, loc, b = s.get(f"/sign-in/email-{kind}", tag="c22-form")
            s.post(f"/sign-in/email-{kind}", {"email": unk, "authenticity_token": form_token(b), "return_to": v}, tag="c22-req")
            stored_by_page = (code_rows(unk) if kind == "code" else link_rows(unk))[-1]["return_to"]
            em = E([17, 19, 20][len(out) % 3])
            if kind == "code":
                code, row = get_code(em, return_to=v); X = S("c22-sub"); fin = submit_code(X, em, code)
            else:
                link, row = get_link(em, return_to=v); X = S("c22-sub"); a, bb = open_link(X, link); fin = cont(X, body=bb[2])
            out.append((v, want, kind, p(fin), row["return_to"], stored_by_page))
    for v, want, kind, landed, stored, by_page in out:
        if want is None:
            observed(f"22 literal (double-encoded) {v!r} by {kind}: landed {landed!r}; stored {stored!r}; the request page stored {by_page!r}")
            continue
        result(f"22 return_to {v!r} by {kind}", landed == want and stored == by_page, f"landed {landed}; stored return_to {stored!r}; the request page stores {by_page!r}")
    clear("sign_in_code", "sign_in_link")
    em = E(18); code, row = get_code(em, return_to="/profile"); X = S("c22-2fa-sub"); fin = submit_code(X, em, code)
    st, loc, vb = X.get(p(fin), tag="c22-verify-page")
    action = html.unescape(re.search(r'<form action="([^"]+)" method="post">', vb).group(1))
    v = X.post(action, {"2fa[otp_code]": unused_code(em, secs[em]), "from_page": "verify-2fa", "authenticity_token": form_token(vb)}, tag="c22-otp")
    result("22 return_to /profile, 2FA user", p(fin) == "/verify-2fa?return_to=%2Fprofile" and p(v) == "/profile", f"code -> {p(fin)}; the /verify-2fa form posts to {action}; TOTP -> {p(v)}")
    shown = []
    for v, want in C22_VALUES[1:8]:
        b = S("c22-show").get("/sign-in/email-link?return_to=" + urllib.parse.quote(v, safe=""), tag="c22-show")[2]
        shown.append(re.search(r'name="return_to" value="([^"]*)"', b).group(1))
    result("22 request pages drop a bad return_to from the form", all(x == "" for x in shown), f"hidden return_to for the 7 bad values: {shown}")


@block("pwl", "c23", ["23 CSRF missing or forged on all four POSTs", "23 control: the same code and link work with a real token"])
def b_c23():
    """A missing or forged authenticity token is refused on all four POSTs, and uses nothing up."""
    clear("sign_in_code", "sign_in_link")
    em = E(19); after = last_mail_id(); bad = "forged" + "x" * 80
    res = {}
    for kind in ("code", "link"):
        for tok in ("", bad):
            s = S("c23"); s.get(f"/sign-in/email-{kind}", tag="c23-form")
            before = len(code_rows(em) if kind == "code" else link_rows(em))
            r = s.post(f"/sign-in/email-{kind}", {"email": em, "authenticity_token": tok} if tok else {"email": em}, tag="c23-req")
            res[f"POST /sign-in/email-{kind} token={'missing' if not tok else 'forged'}"] = (p(r), len(code_rows(em) if kind == "code" else link_rows(em)) - before)
    T.sleep(20); n = len(mails_to(em, after))
    code, row = get_code(em)
    for tok in ("", bad):
        X = S("c23-sub"); X.get("/sign-in/code", tag="c23-code-form")
        r = X.post("/sign-in/code", {"email": em, "code": code, "authenticity_token": tok} if tok else {"email": em, "code": code}, tag="c23-code")
        res[f"POST /sign-in/code token={'missing' if not tok else 'forged'}"] = (p(r), signed_in(X)[0])
    sl_c = slots("sign_in_code", row["id"]); rc = row_by_id(code_rows(em), row["id"])["status"]
    link, lrow = get_link(em)
    for tok in ("", bad):
        X = S("c23-cont"); a, b = open_link(X, link)
        r = X.post("/sign-in/link", {"authenticity_token": tok} if tok else {}, tag="c23-cont")
        res[f"POST /sign-in/link token={'missing' if not tok else 'forged'}"] = (p(r), signed_in(X)[0])
    sl_l = slots("sign_in_link", lrow["id"]); rl = row_by_id(link_rows(em), lrow["id"])["status"]
    ok = all(v[0].endswith("error=session") for v in res.values()) and n == 0 and sl_c == [] and sl_l == [] and rc == "pending" and rl == "pending" \
        and all(v[1] in (0, 302) for k, v in res.items())
    result("23 CSRF missing or forged on all four POSTs", ok, f"{res}; emails from the 4 request POSTs {n}; code slots {sl_c} row {rc}; link slots {sl_l} row {rl}")
    X = S("c23-ctrl"); r = submit_code(X, em, code); Y = S("c23-ctrl2"); a, b = open_link(Y, link); r2 = cont(Y, body=b[2])
    result("23 control: the same code and link work with a real token", p(r) == "/dashboard" and p(r2) == "/dashboard", f"code -> {p(r)}; link -> {p(r2)}")


@block("pwl", "c25", ["25 already signed in"])
def b_c25():
    """A signed-in user is sent to /dashboard by every sign-in page and POST, and nothing is used up or created."""
    clear("sign_in_code", "sign_in_link")
    em = E(20); code, row = get_code(em); link, lrow = get_link(em)
    n0 = (len(code_rows(em)), len(link_rows(em)))
    A = S("c25"); A.sign_in(em, pws[em]); assert signed_in(A)[0] == 200
    tok = form_token(A.get("/profile", tag="c25-tok")[2])
    gets = {u: p(A.get(u, tag="c25")) for u in ["/sign-in", "/sign-in/email-code", "/sign-in/code", "/sign-in/email-link", "/sign-in/link", link.replace(BASE, "")]}
    posts = {u: p(A.post(u, d, tag="c25-post")) for u, d in [("/sign-in/email-code", {"email": em, "authenticity_token": tok}), ("/sign-in/code", {"email": em, "code": code, "authenticity_token": tok}),
                                                             ("/sign-in/email-link", {"email": em, "authenticity_token": tok}), ("/sign-in/link", {"authenticity_token": tok})]}
    rc = row_by_id(code_rows(em), row["id"])["status"]; rl = row_by_id(link_rows(em), lrow["id"])["status"]
    nrows = (len(code_rows(em)) - n0[0], len(link_rows(em)) - n0[1])
    sl = slots("sign_in_code", row["id"]) + slots("sign_in_link", lrow["id"])
    ok = all(v == "/dashboard" for v in gets.values()) and all(v == "/dashboard" for v in posts.values()) and rc == "pending" and rl == "pending" and sl == [] and nrows == (0, 0)
    result("25 already signed in", ok, f"GETs {gets}; POSTs {posts}; code row {rc}, link row {rl}, slots {sl}, new rows (code, link) {nrows}")


@block("pwl", "expiry", ["5a expired code", "5b unknown address after 15 min", "18 expired link"])
def b_expiry():
    """Expiry, on requests minted with an expiry already in the past (the same as waiting 15 minutes)."""
    clear("sign_in_code", "sign_in_link", "sign_in_code_check")
    em = E(3); unk = NOBODY(9)
    code, rid = mint_code(em, expires=-60)
    urid = mint_code(unk, expires=-60, status="miss")[1]
    link, lrid = mint_link(em, expires=-60)
    X = S("exp-code"); r = submit_code(X, em, code); sl = slots("sign_in_code", rid); dd = signed_in(X)
    rr = row_by_id(code_rows(em), rid)
    result("5a expired code", p(r) == "/sign-in/code?error=expired" and sl == [] and dd[0] == 302, f"request expired 60 s ago: right code -> {p(r)}; slots {sl}; row {rr['status']}; /dashboard {dd[0]}")
    Y = S("exp-unk"); r2 = submit_code(Y, unk, "123456"); sl2 = slots("sign_in_code", urid)
    result("5b unknown address after 15 min", p(r2) == "/sign-in/code?error=expired" and sl2 == [], f"miss row expired 60 s ago; a code -> {p(r2)}; slots {sl2}")
    Z = S("exp-link"); a, b = open_link(Z, link); lr = row_by_id(link_rows(em), lrid)
    result("18 expired link", p(a) == "/sign-in/link" and b and p(b) == "/sign-in/email-link?error=stale" and lr["status"] == "pending" and signed_in(Z)[0] == 302,
           f"request expired 60 s ago: open -> {p(a)} then {p(b) if b else None}; row {lr['status']}, slots {slots('sign_in_link', lrid)}")


@block("pwl", "browser", ["24 no token in address bar, history or page source", "16b Continue in a real browser"], browser=True)
def b_browser():
    """Case 24 and the Continue button in headless Chromium, on a minted link. The browser is closed in a finally."""
    from playwright.sync_api import sync_playwright
    clear("sign_in_link")
    link, row = get_link(E(13))
    q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(link).query).items()}
    needles = {"t": q["t"], "t (encoded)": urllib.parse.quote(q["t"], safe=""), "n": q["n"]}
    out = {"requests": [], "console": []}
    with sync_playwright() as pwr:
        br = pwr.chromium.launch(headless=True)
        try:
            page = br.new_context().new_page()
            page.on("request", lambda r: out["requests"].append([r.url, r.headers.get("referer")]))
            page.on("console", lambda c: out["console"].append([c.type, c.text[:200]]) if c.type in ("error", "warning") else None)
            resp = page.goto(link, wait_until="networkidle")
            out["url"] = page.url
            src = resp.text(); dom = page.content(); text = page.inner_text("body")
            out["history_length"] = page.evaluate("history.length")
            out["location_search"] = page.evaluate("location.search")
            out["navigation_entry"] = page.evaluate("performance.getEntriesByType('navigation')[0].name")
            out["shows_address"] = E(13) in text
            out["source_has_token"] = {k: v in src for k, v in needles.items()}
            out["dom_has_token"] = {k: v in dom for k, v in needles.items()}
            out["referers_with_token"] = [r for r in out["requests"] if r[1] and any(v in r[1] for v in needles.values())]
            out["requests_after_landing_with_token_in_url"] = [r[0][:80] for r in out["requests"][1:] if any(v in r[0] for v in needles.values())]
            page.go_back(wait_until="load"); out["back_url"] = page.url
            page.go_forward(wait_until="networkidle"); out["forward_url"] = page.url
            with page.expect_navigation(wait_until="networkidle"):
                page.locator("#submit-btn").click()
            out["after_continue"] = page.url
        finally:
            br.close()
    lr = row_by_id(link_rows(E(13)), row["id"])
    out["row_after"] = lr["status"]; out["slots"] = slots("sign_in_link", row["id"])
    ok = (out["url"] == BASE + "/sign-in/link" and out["location_search"] == "" and out["navigation_entry"] == BASE + "/sign-in/link"
          and not any(out["source_has_token"].values()) and not any(out["dom_has_token"].values()) and out["referers_with_token"] == []
          and out["requests_after_landing_with_token_in_url"] == [] and out["back_url"] == "about:blank" and out["shows_address"])
    result("24 no token in address bar, history or page source", ok,
           f"address bar {out['url']}; location.search {out['location_search']!r}; history.length {out['history_length']}; back -> {out['back_url']}; forward -> {out['forward_url']}; "
           f"token or nonce in served source {out['source_has_token']}, in rendered DOM {out['dom_has_token']}; Referers carrying them {len(out['referers_with_token'])} of {len(out['requests'])} requests; page shows the address {out['shows_address']}")
    result("16b Continue in a real browser", out["after_continue"] == BASE + "/dashboard" and out["row_after"] == "consumed", f"button -> {out['after_continue']}; row {out['row_after']}; slots {out['slots']}; console errors/warnings {len(out['console'])}: {out['console'][:3]}")

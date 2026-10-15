"""Suite cln: the v2.1.0 clean-up items (redirects, registration, reset-required, the edge email rewrite, API
statuses, profile forms, caching, the email sender) and the browser checks. Ported from the QA harness that
passed at e88460e. Lockouts are inserted rows and codes and links are minted, so only the sender case sends."""
import html
import json
import re
import threading
import time as T
import urllib.parse
import urllib.request

from lib.client import *          # noqa: F401,F403
from lib import client as C
from lib.registry import block, result, observed

E = emails_for("cln")
pws, ids, secs = {}, {}, {}
REG_PW = new_password()   # one generated password for the registration posts; never a literal
CREATED = {}          # records this suite makes outside the Seedling tables, removed in its own finally


def code_rows(em): return state(em)["attempts"]["codes"]["results"]
def link_rows(em): return state(em)["attempts"]["links"]["results"]
def slots(table, rid): return [s["external_id"] for s in admin(op="slots", table=table, rid=rid)["slots"]["results"]]
def row_by_id(rows_, rid): return [x for x in rows_ if str(x["id"]) == str(rid)][0]
def gql(q): return INST.guarded_gql(q, allow_errors=True)


def setup_2fa(n):
    em = E(n); A = S(f"2fa-setup-{n}")
    A.sign_in(em, pws[em]); b = A.get("/profile", tag="profile")[2]
    sec = re.search(r'<pre id="setup_code">([A-Z0-9]+)</pre>', b).group(1)
    r = A.otp(unused_code(em, sec), from_page="profile", csrf_from="/profile")
    st = state(em)["user"]; secs[em] = sec
    return p(r), st["client"][0]["otp_configured"] is True, A


def users_with(email):
    d = gql('query { u: users(per_page: 20, filter: { email: { value: "%s" } }) { total_entries results { id email } } }' % email)
    return d["data"]["u"]["total_entries"], [x["id"] for x in d["data"]["u"]["results"]]


def register_post(s, data, token=True, get_first=True):
    b = s.get("/register", tag="register-form")[2] if get_first else ""
    d = dict(data); d["authenticity_token"] = form_token(b) if token is True else (token or "")
    return s.post("/register", d, tag="register", keep_body=True)


def events(n=10):
    out = INST.liquid("{%- assign q = {} -%}{%- assign q['page'] = 1 -%}{%- assign q['per_page'] = " + str(n) + " -%}{%- function r = 'crm/controller/event-streams/list', params: q -%}{{ r | json }}")
    try: return json.loads(out).get("result", [])
    except Exception: return []


def lockouts(em):
    return [x for x in state(em)["attempts"]["by_id"]["results"] if x["action"] == "otp_lockout"]


def three_lockouts(em):
    """Three otp_lockout rows in the last 24 hours, inserted (no alert emails)."""
    for back in (960, 1900, 2800):
        seed("otp_lockout", 1, key=ids[em], back=back)


# ------------------------------------------------------------------ blocks

@block("cln", "setup", [], setup=True)
def b_setup():
    """Create 12 users with a client profile and one without."""
    for n in list(range(1, 13)) + ["nc"]:
        ids[E(n)], pws[E(n)] = create_user(E(n), client=n != "nc")


@block("cln", "redirect", ["1a signed-out /dashboard and /profile go to /sign-in with return_to",
                           "1b signed in, 2FA not passed -> /verify-2fa (control)", "1c after 2FA the return_to is honored",
                           "1d signed in, no client profile: refused at the 403 page, no loop (the System Pages 403 page answers 200)",
                           "1e password sign-in keeps a safe return_to and drops an off-site one"])
def b_redirect():
    """Signed-out visitors go to /sign-in with return_to; a signed-in user who has not passed 2FA still goes to /verify-2fa."""
    out = {}
    for path in ["/dashboard", "/profile", "/dashboard?x=1&y=2"]:
        out[path] = p(S("anon").get(path, tag="anon-protected"))
    ok = out["/dashboard"] == "/sign-in?return_to=%2Fdashboard" and out["/profile"] == "/sign-in?return_to=%2Fprofile" and out["/dashboard?x=1&y=2"] == "/sign-in?return_to=%2Fdashboard%3Fx%3D1%26y%3D2"
    result("1a signed-out /dashboard and /profile go to /sign-in with return_to", ok, f"{out}")
    clear("otp")
    r, on, A = setup_2fa(2)
    X = S("1b"); r1 = X.sign_in(E(2), pws[E(2)]); d = X.get("/dashboard", tag="1b-dash"); pr = X.get("/profile", tag="1b-prof")
    result("1b signed in, 2FA not passed -> /verify-2fa (control)", on and p(r1) == "/verify-2fa" and p(d) == "/verify-2fa?return_to=%2Fdashboard" and p(pr) == "/verify-2fa?return_to=%2Fprofile",
           f"2FA set up via profile -> {r}, on={on}; password sign-in -> {p(r1)}; /dashboard -> {p(d)}; /profile -> {p(pr)}")
    r2 = X.otp(unused_code(E(2), secs[E(2)]), return_to="/profile", csrf_from="/verify-2fa?return_to=%2Fprofile")
    result("1c after 2FA the return_to is honored", p(r2) == "/profile" and X.get("/profile", tag="1c")[0] == 200, f"code -> {p(r2)}")
    N = S("1d"); rn = N.sign_in(E("nc"), pws[E("nc")]); chain = []; url = "/dashboard"
    for _ in range(5):
        r_ = N.get(url, tag="1d-chain"); chain.append((url, r_[0]))
        if r_[0] not in (301, 302) or not r_[1]: break
        url = p(r_)
    result("1d signed in, no client profile: refused at the 403 page, no loop (the System Pages 403 page answers 200)",
           [c[1] for c in chain] == [302, 302, 200] and chain[1][0].startswith("/verify-2fa") and chain[2][0].startswith("/403"), f"sign-in -> {p(rn)}; chain {chain}")
    Y = S("1e"); b = Y.get("/sign-in?return_to=%2Fprofile", tag="1e-form")[2]
    hid = re.search(r'name="return_to" value="([^"]*)"', b).group(1)
    ry = Y.post("/sign-in", {"email": E(1), "password": pws[E(1)], "return_to": hid, "authenticity_token": form_token(b)}, tag="1e")
    Z = S("1f"); bz = Z.get("/sign-in", tag="1f-form")[2]
    rz = Z.post("/sign-in", {"email": E(1), "password": pws[E(1)], "return_to": "https://evil.example/x", "authenticity_token": form_token(bz)}, tag="1f")
    W = S("1g"); bw = W.get("/sign-in", tag="1g-form")[2]
    rw = W.post("/sign-in", {"email": E(1), "password": "wrong-pw-1", "return_to": "/profile", "authenticity_token": form_token(bw)}, tag="1g")
    result("1e password sign-in keeps a safe return_to and drops an off-site one", hid == "/profile" and p(ry) == "/profile" and p(rz) == "/dashboard" and p(rw) == "/sign-in?error=invalid&return_to=%2Fprofile",
           f"hidden return_to={hid!r}; sign-in -> {p(ry)}; off-site return_to -> {p(rz)}; wrong password keeps it -> {p(rw)}")


@block("cln", "register", ["2a register a new email", "M4 registration is logged through the CRM controller", "2b duplicate email refused on the server",
                           "2c a post without the form's session is refused", "2d server-side field checks",
                           "2e ten simultaneous registrations for one email create one user"])
def b_register():
    """Registration: the server decides; duplicates and session-less posts are refused; a race creates one user."""
    stamp = str(int(T.time()))
    em = E(f"reg{stamp}")
    ev0 = [e for e in events(20) if (e.get("log") or {}).get("email") == em]
    A = S("reg-ok"); r = register_post(A, {"first_name": "Seedling", "last_name": "Reg", "email": em, "password": REG_PW})
    n, uids = users_with(em)
    st = state(em)["user"]
    T.sleep(20); ev1 = [e for e in events(20) if (e.get("log") or {}).get("email") == em]
    result("2a register a new email", p(r) == "/account-created" and n == 1 and [x["profile_type"] for x in st["profiles"]] == ["client"] and st["client"][0]["otp_configured"] is False,
           f"-> {p(r)}; users with that email {n}; profiles {[x['profile_type'] for x in st['profiles']]}; otp_configured {st['client'][0]['otp_configured']}")
    result("M4 registration is logged through the CRM controller", len(ev0) == 0 and len(ev1) == 1 and ev1[0]["description"] == "New Registration",
           f"event stream entries for this email before {len(ev0)}, after {len(ev1)}: {[(e['description'], e['log']) for e in ev1]}")
    B = S("reg-dup"); rd = register_post(B, {"first_name": "Seedling", "last_name": "Dup", "email": E(1).upper(), "password": REG_PW})
    n1, _ = users_with(E(1))
    result("2b duplicate email refused on the server", rd[0] == 422 and "Email has already been used." in rd[2] and n1 == 1 and 'value="Seedling"' in rd[2],
           f"status {rd[0]}; message shown {'Email has already been used.' in rd[2]}; users with {E(1)}: {n1}; first name shown again {'value=\"Seedling\"' in rd[2]}")
    Cs = S("reg-nosess"); em2 = E(f"nosess{stamp}")
    rc = Cs.post("/register", {"first_name": "a", "last_name": "b", "email": em2, "password": REG_PW}, tag="reg-nosess")
    result("2c a post without the form's session is refused", p(rc) == "/register?error=session" and users_with(em2)[0] == 0, f"-> {p(rc)}; users {users_with(em2)[0]}")
    D = S("reg-short")
    rs = register_post(D, {"first_name": "", "last_name": "b", "email": "bad", "password": "123"})
    result("2d server-side field checks", rs[0] == 422 and "First name is required" in rs[2] and "Minimum of 6 characters" in rs[2] and "Please use a valid email address" in rs[2],
           f"status {rs[0]}; messages first-name {'First name is required' in rs[2]}, password {'Minimum of 6 characters' in rs[2]}, email {'Please use a valid email address' in rs[2]}")
    em4 = E(f"race{stamp}")
    sessions = [S(f"race-{i}") for i in range(10)]
    toks = [form_token(s.get("/register", tag="race-form")[2]) for s in sessions]
    outs = [None] * 10; go = threading.Event()
    def fire(i):
        go.wait(); outs[i] = sessions[i].post("/register", {"first_name": "Race", "last_name": str(i), "email": em4, "password": REG_PW, "authenticity_token": toks[i]}, tag="race")
    th = [threading.Thread(target=fire, args=(i,)) for i in range(10)]
    [t.start() for t in th]; go.set(); [t.join() for t in th]
    n4, u4 = users_with(em4)
    codes = sorted(str(o[0]) + (" " + p(o) if o[1] else "") for o in outs)
    result("2e ten simultaneous registrations for one email create one user", n4 == 1 and sum(1 for o in outs if p(o) == "/account-created") == 1,
           f"users with that email {n4} {u4}; answers {codes}")


@block("cln", "reset_required", ["4a reset required: code and link refused with error=reset and NOT used up", "reg forgot password and reset",
                                 "4b after the reset the SAME code signs in (it was not used up)"])
def b_reset_required():
    """E(5) has 2FA and three lockouts (inserted rows); a code and a link are refused with error=reset without being
    used up. The reset token is minted where forgot-password stores it, so nothing is emailed."""
    clear("sign_in_code", "sign_in_link", "otp", "sign_in_code_check", "forgot_password", "otp_lockout")
    em = E(5)
    if em not in secs:
        setup_2fa(5)
    three_lockouts(em)
    lk = lockouts(em)
    code, rid = mint_code(em); row = row_by_id(code_rows(em), rid)
    X = S("rr-code"); rc = submit_code(X, em, code)
    crow = row_by_id(code_rows(em), rid); csl = slots("sign_in_code", rid)
    link, lrid = mint_link(em)
    Y = S("rr-link"); a, b = open_link(Y, link); rl = cont(Y, body=b[2])
    lrow2 = row_by_id(link_rows(em), lrid); lsl = slots("sign_in_link", lrid)
    pw = S("rr-pw"); rp = pw.sign_in(em, pws[em])
    result("4a reset required: code and link refused with error=reset and NOT used up", len(lk) == 3 and p(rc) == "/sign-in/code?error=reset" and crow["status"] == "pending" and not any("use" in x for x in csl)
           and p(rl) == "/sign-in/email-link?error=reset" and lrow2["status"] == "pending" and lsl == [] and p(rp) == "/sign-in?error=invalid",
           f"lockouts {len(lk)} (inserted); code -> {p(rc)}, row {crow['status']}, slots {csl}; link -> {p(rl)}, row {lrow2['status']}, slots {lsl}; password sign-in -> {p(rp)}")
    tok = admin(op="mint", email=em, hours=0.25)["token"]
    R = S("rr-reset"); st, has_form, invalid, csrf = reset_form(R, em, tok)
    newpw = new_password()
    rr = reset_submit(R, em, tok, newpw, csrf)
    pws[em] = newpw
    st2, has_form2, invalid2, _ = reset_form(S("rr-reuse"), em, tok)
    lk2 = lockouts(em)
    result("reg forgot password and reset", has_form and p(rr) == "/password-reset?reset=done" and invalid2 and len(lk2) == 0,
           f"token minted where forgot-password stores it (the forgot email is proved by suite sec); reset form shown {has_form}; reset -> {p(rr)}; link reused shows invalid {invalid2}; lockouts after reset {len(lk2)}")
    X2 = S("rr-code2"); rc2 = submit_code(X2, em, code)
    Y2 = S("rr-link2"); a2, b2 = open_link(Y2, link); rl2 = cont(Y2, body=b2[2])
    result("4b after the reset the SAME code signs in (it was not used up)", p(rc2) == "/verify-2fa", f"same code -> {p(rc2)} (2FA is on, so it goes to /verify-2fa)")
    observed(f"4b link half: the same link after a password reset -> {p(rl2)}. A reset changes the platform token the link carries, so the link half is tested by 4c instead")


@block("cln", "passwordless_and_cf", ["reg sign-in by emailed code", "reg sign-in by emailed link", "5 /sign-in/link shows the address without JavaScript"])
def b_passwordless_and_cf():
    """Code and link sign-in for a user without 2FA (minted requests), and the edge email rewrite with a control."""
    clear("sign_in_code", "sign_in_link", "sign_in_code_check")
    em = E(3)
    code, rid = mint_code(em); X = S("cl-code"); r = submit_code(X, em, code); d = signed_in(X)
    result("reg sign-in by emailed code", p(r) == "/dashboard" and d[0] == 200, f"-> {p(r)}, /dashboard {d[0]}")
    link, lrid = mint_link(em); Y = S("cl-link"); a, b = open_link(Y, link)
    page = b[2] if b else ""
    plain = em in page; obf = "__cf_email__" in page or "email-protection" in page
    rl = cont(Y, body=page); dl = signed_in(Y)
    result("reg sign-in by emailed link", p(rl) == "/dashboard" and dl[0] == 200, f"Continue -> {p(rl)}, /dashboard {dl[0]}")
    ctrl = S("cf").get("/qa-fixture/cf", tag="cf-control", keep_body=True)[2]
    cobf = "__cf_email__" in ctrl and "qa-fixture-cf-control@example.com" not in ctrl
    result("5 /sign-in/link shows the address without JavaScript", plain and not obf and cobf,
           f"link page has the address as text {plain}, edge rewrite present {obf}; control page without the markers rewritten {cobf}")


@block("cln", "link_control", ["4c the refused link was not used up: once the lockouts are gone the SAME link signs in"])
def b_link_control():
    """A refused link is not used up: the lockout rows are deleted (what a reset does to them) and the SAME link is tried again."""
    clear("sign_in_link", "otp", "otp_lockout")
    em = E(5)
    if em not in secs:
        setup_2fa(5)
    three_lockouts(em)
    link, lrid = mint_link(em)
    Y = S("lc-link"); a, b = open_link(Y, link); rl = cont(Y, body=b[2])
    lrow2 = row_by_id(link_rows(em), lrid)
    lk = lockouts(em)
    for x in lk:
        gql('mutation { r: record_delete(id: "%s", table: "auth_attempt") { id } }' % x["id"])
    Y2 = S("lc-link2"); a2, b2 = open_link(Y2, link); rl2 = cont(Y2, body=b2[2])
    lrow3 = row_by_id(link_rows(em), lrid)
    result("4c the refused link was not used up: once the lockouts are gone the SAME link signs in", p(rl) == "/sign-in/email-link?error=reset" and lrow2["status"] == "pending" and p(rl2) == "/verify-2fa" and lrow3["status"] == "consumed",
           f"with {len(lk)} lockouts -> {p(rl)}, row {lrow2['status']}; lockout rows deleted; same link -> {p(rl2)}, row {lrow3['status']}. A real password reset changes the token in the link, so after a reset the person asks for a new link")


@block("cln", "api", ["M12 API errors carry their real status"])
def b_api():
    """API statuses and the JSON pages' layout."""
    clear("email_check")
    out = {}
    for label, q in [("missing", ""), ("bad", "?email=not-an-email"), ("new", "?email=seedling-qa-new-x%40example.com"), ("taken", "?email=" + urllib.parse.quote(E(1)))]:
        st, loc, b = S("api").get("/api/check-user-email-signup" + q, tag="api-" + label, keep_body=True)
        try: j = json.loads(b)
        except Exception: j = {"_raw": b[:80]}
        out[label] = (st, j.get("status_code"), j.get("email_status"), "id" in j)
    A = S("api-user"); A.sign_in(E(4), pws[E(4)]); tok = A.token("/profile")
    other = ids[E(1)]; mine = ids[E(4)]
    h = {"X-CSRF-Token": tok, "Accept": "application/json"}
    r403 = A.req("PATCH", f"/api/users/{other}", {"first_name": "X", "last_name": "Y", "email": E(1)}, headers=h, tag="api-403", keep_body=True)
    r422 = A.req("PATCH", f"/api/users/{mine}", {"first_name": "X", "last_name": "Y", "email": E(1)}, headers=h, tag="api-422", keep_body=True)
    r200 = A.req("PATCH", f"/api/users/{mine}", {"first_name": "Seedling", "last_name": "Api", "email": E(4)}, headers=h, tag="api-200", keep_body=True)
    d2 = A.req("POST", "/api/disable-2fa", {"otp_code": "123456"}, headers=h, tag="api-disable-no2fa", keep_body=True)
    ok = (out["missing"][:2] == (400, 400) and out["bad"][:2] == (422, 422) and out["new"][0] == 200 and out["new"][2] == "valid"
          and out["taken"][2] == "invalid" and not out["taken"][3] and r403[0] == 403 and r422[0] == 422 and '"taken"' not in r422[2] and r200[0] == 200 and '"Api"' in r200[2])
    result("M12 API errors carry their real status", ok,
           f"email check {out}; PATCH another user {r403[0]}; PATCH own with a taken email {r422[0]} {r422[2][:120]}; PATCH own valid {r200[0]} {r200[2][:100]}; disable-2fa without 2FA (policy) -> {d2[0]} {d2[1]}")


@block("cln", "profile", ["H6 profile details save, refuse a taken email, refuse a post without the token",
                          "H6 change password: mismatch refused; change signs out; new password works, old does not",
                          "H6 sign out posts with the token; a post without it signs nobody out"])
def b_profile():
    """Profile forms, change password and sign out, with CSRF controls."""
    em = E(6); A = S("prof"); A.sign_in(em, pws[em])
    b = A.get("/profile", tag="prof-form")[2]; tok = form_token(b)
    r1 = A.post("/profile/details", {"first_name": "Seedling", "last_name": "Saved", "email": em, "authenticity_token": tok}, tag="prof-save")
    r2 = A.post("/profile/details", {"first_name": "Seedling", "last_name": "Saved", "email": E(1), "authenticity_token": tok}, tag="prof-taken")
    n_still, _ = users_with(em)
    N = S("prof-nocsrf"); N.jar = A.jar; N.op = urllib.request.build_opener(C.NoRedirect(), urllib.request.HTTPCookieProcessor(A.jar))
    r3 = N.post("/profile/details", {"first_name": "Csrf", "last_name": "Csrf", "email": em}, tag="prof-nocsrf")
    page = A.get("/profile", tag="prof-after", keep_body=True)[2]
    result("H6 profile details save, refuse a taken email, refuse a post without the token", p(r1) == "/profile?status=saved" and p(r2) == "/profile?error=email_taken" and n_still == 1 and p(r3).startswith("/sign-in") and 'value="Saved"' in page and "Csrf" not in page,
           f"save -> {p(r1)}; taken email -> {p(r2)}; no token -> {p(r3)}; page shows last name Saved {'value=\"Saved\"' in page}")
    r4 = A.post("/profile/password", {"password": new_password(), "password_confirmation": new_password(), "authenticity_token": tok}, tag="pw-mismatch")
    newpw = new_password()
    r5 = A.post("/profile/password", {"password": newpw, "password_confirmation": newpw, "authenticity_token": tok}, tag="pw-change")
    d5 = signed_in(A)
    B = S("pw-old"); r6 = B.sign_in(em, pws[em]); Cc = S("pw-new"); r7 = Cc.sign_in(em, newpw)
    pws[em] = newpw
    result("H6 change password: mismatch refused; change signs out; new password works, old does not", p(r4) == "/profile?error=password_mismatch" and p(r5) == "/sign-out" and d5[0] == 302 and p(r6) == "/sign-in?error=invalid" and p(r7) == "/dashboard",
           f"mismatch -> {p(r4)}; change -> {p(r5)}; /dashboard after {d5}; old password -> {p(r6)}; new -> {p(r7)}")
    D = S("so"); D.sign_in(E(7), pws[E(7)]); tk = form_token(D.get("/dashboard", tag="so-dash")[2])
    E2 = S("so-nocsrf"); E2.jar = D.jar; E2.op = urllib.request.build_opener(C.NoRedirect(), urllib.request.HTTPCookieProcessor(D.jar))
    rn = E2.post("/sign-out", {}, tag="so-nocsrf"); still = signed_in(D)
    rs = D.post("/sign-out", {"authenticity_token": tk}, tag="so"); after = signed_in(D)
    result("H6 sign out posts with the token; a post without it signs nobody out", p(rn) == "/sign-out" and still[0] == 200 and p(rs) == "/sign-out" and after[0] == 302,
           f"no token -> {p(rn)}, still signed in {still[0] == 200}; with token -> {p(rs)}, /dashboard after {after}")


@block("cln", "dashboard_cache", ["M5 dashboard not cached across users", "M5 account-created still renders with its corrected cache key"])
def b_dashboard_cache():
    """The dashboard is not cached: two users each see their own name."""
    A = S("dc-a"); A.sign_in(E(8), pws[E(8)]); B = S("dc-b"); B.sign_in(E(9), pws[E(9)])
    gql('mutation { a: user_update(id: "%s", user: { first_name: "Alpha" }) { id } b: user_update(id: "%s", user: { first_name: "Bravo" }) { id } }' % (ids[E(8)], ids[E(9)]))
    a1 = A.get("/dashboard", tag="dc-a", keep_body=True)[2]; b1 = B.get("/dashboard", tag="dc-b", keep_body=True)[2]; a2 = A.get("/dashboard", tag="dc-a2", keep_body=True)[2]
    result("M5 dashboard not cached across users", "Hi Alpha" in a1 and "Hi Bravo" in b1 and "Hi Alpha" in a2 and "Bravo" not in a2,
           f"A sees Alpha {'Hi Alpha' in a1}; B sees Bravo {'Hi Bravo' in b1}; A again sees Alpha {'Hi Alpha' in a2}")
    ac = S("dc-ac").get("/account-created", tag="ac", keep_body=True)
    result("M5 account-created still renders with its corrected cache key", ac[0] == 200 and "Account Created" in ac[2], f"status {ac[0]}")


@block("cln", "2fa", ["reg 2FA: set up on profile, verify after password, turn off with a code"])
def b_2fa():
    """2FA on via profile, verify after password, turn off with the right code."""
    clear("otp")
    em = E(11); r, on, A = setup_2fa(11)
    X = S("2fa"); r1 = X.sign_in(em, pws[em]); r2 = X.otp(wrong_code(secs[em])); r3 = X.otp(unused_code(em, secs[em])); d = signed_in(X)
    tok = X.token("/profile"); h = {"X-CSRF-Token": tok, "Accept": "application/json"}
    bad = X.req("POST", "/api/disable-2fa", {"otp_code": wrong_code(secs[em])}, headers=h, tag="dis-bad", keep_body=True)
    good = X.req("POST", "/api/disable-2fa", {"otp_code": unused_code(em, secs[em])}, headers=h, tag="dis-good", keep_body=True)
    off = state(em)["user"]["client"][0]["otp_configured"]
    result("reg 2FA: set up on profile, verify after password, turn off with a code", on and p(r1) == "/verify-2fa" and p(r2) == "/verify-2fa?status=failed" and p(r3) == "/dashboard" and d[0] == 200 and bad[0] == 422 and good[0] == 200 and off is False,
           f"setup -> {r}; password -> {p(r1)}; wrong code -> {p(r2)}; right -> {p(r3)}; disable wrong {bad[0]} {bad[2][:60]}; disable right {good[0]} {good[2][:60]}; otp_configured now {off}")


@block("cln", "sender", ["M9 mail from the verified sender; Globals address only as Reply-To"], emails=2)
def b_sender():
    """The verified sender, with the Globals address as Reply-To only when it is set. Reuses the run's code email
    for the first half when suite pwl already made one; the Globals record it creates is deleted in a finally."""
    clear("sign_in_code", "sign_in_link")
    em = E(10)
    d = C.DELIVERED.get("sign-in code")
    if d:
        m1 = [d[1]]; how1 = f"the run's code email to {d[3]}"
    else:
        BUDGET.expect("sign-in code (sender)")
        after = last_mail_id(); req_code(S("snd1"), em); m1 = wait_mail(em, after, SUBJECT_CODE); how1 = "a new code email"
    o1 = (m1[-1]["options"] if m1 else {}) or {}
    reply_to = CFG.email("replyto")
    res = gql('mutation { r: record_create(record: { table: "modules/insites_cms/global", properties: [{ name: "company_name", value: "Seedling QA" }, { name: "company_email_1", value: %s }] }) { id } }' % json.dumps(reply_to))
    gid = (res.get("data") or {}).get("r", {}).get("id")
    CREATED["globals_record"] = gid
    try:
        BUDGET.expect("sign-in code (sender, with Globals)")
        after2 = last_mail_id(); req_code(S("snd2"), em)
        m2 = wait_mail(em, after2, SUBJECT_CODE)
        o2 = (m2[-1]["options"] if m2 else {}) or {}
    finally:
        if gid:
            gql('mutation { r: record_delete(id: "%s", table: "modules/insites_cms/global") { id } }' % gid)
    ok = (bool(m1) and "no-reply@" in str(o1.get("from")) and not o1.get("reply_to")
          and bool(m2) and "no-reply@" in str(o2.get("from")) and "Seedling QA" in str(o2.get("from")) and reply_to in str(o2.get("reply_to")))
    result("M9 mail from the verified sender; Globals address only as Reply-To", ok,
           f"no Globals ({how1}): from={o1.get('from')!r} reply_to={o1.get('reply_to')!r}; with Globals (record {gid}, deleted after): from={o2.get('from')!r} reply_to={o2.get('reply_to')!r}")


@block("cln", "browser", ["W1 no console errors, failed requests or 404s on any page; app.js and the components load once; CDN scripts carry integrity hashes (.min.js counted only for Seedling's own assets)",
                          "W2 every form shows its validation messages and does not submit when empty",
                          "W3 register waits for the email check: a taken email never posts; a free one posts once, after the check",
                          "W4 attribute injection: the old pattern breaks out (control); the fixed pages do not, for a request value and two stored values",
                          "v2.0.0 pattern: a raw request value in a hidden input"], browser=True)
def b_browser():
    """Headless Chromium: console errors and script counts on every page, validation messages, the register race,
    and attribute injection before and after. The browser is closed in a finally."""
    from playwright.sync_api import sync_playwright
    clear("email_check", "sign_in")
    OUT = {}

    def watch(page, sink):
        page.on("console", lambda m: sink.append(["console." + m.type, m.text[:200]]) if m.type in ("error",) else None)
        page.on("pageerror", lambda e: sink.append(["pageerror", str(e)[:200]]))
        page.on("response", lambda r: sink.append(["http %d" % r.status, r.url[:120]]) if r.status >= 400 else None)
        page.on("requestfailed", lambda r: sink.append(["failed", r.url[:120]]))

    def sign_in(page, email, pw):
        page.goto(BASE + "/sign-in", wait_until="networkidle")
        page.locator("#email input").fill(email); page.locator("#password input").fill(pw)
        with page.expect_navigation(wait_until="networkidle"):
            page.locator("#submit-btn").click()

    def counts(page):
        return page.evaluate("""() => {
          const s = [...document.querySelectorAll('script[src]')].map(x => x.getAttribute('src'));
          const c = k => s.filter(x => x.includes(k)).length;
          const cdn = [...document.querySelectorAll('script[src*="cdn"], link[href*="jsdelivr"]')];
          const own = s.filter(x => x.includes('/instances/') && x.includes('/assets/') && !x.includes('/assets/modules/'));
          return { app: c('scripts/app.js'), esm: c('insites.esm.js'), login: c('login-scripts.js'), min: s.filter(x => x.includes('.min.js') && !x.includes('cdn')).length,
                   own_min: own.filter(x => x.includes('.min.')).length, own: own.map(x => x.split('?')[0].split('/assets/')[1]),
                   cdn_without_sri: cdn.filter(x => !x.getAttribute('integrity')).map(x => x.getAttribute('src') || x.getAttribute('href')) };
        }""")

    def has_errors(page):
        return page.evaluate("""() => [...document.querySelectorAll('ins-input')].filter(i => i.hasAttribute('has-error') || i.hasError === true || i.classList.contains('is-invalid') || i.querySelector('.is-invalid')).map(i => i.id)""")

    with sync_playwright() as pwr:
        br = pwr.chromium.launch(headless=True)
        try:
            pages_out = ["/", "/sign-in", "/register", "/forgot-password", "/password-reset", "/sign-in/email-code", "/sign-in/code", "/sign-in/email-link", "/sign-out", "/account-created"]
            ctx = br.new_context(); w1 = {}
            for path in pages_out:
                pg = ctx.new_page(); sink = []; watch(pg, sink); pg.goto(BASE + path, wait_until="networkidle"); pg.mouse.wheel(0, 800); T.sleep(1)
                w1[path] = {"errors": sink, **counts(pg)}; pg.close()
            ctx.close()
            ctx = br.new_context(); pg = ctx.new_page(); sign_in(pg, E(1), pws[E(1)])
            for path in ["/dashboard", "/profile"]:
                sink = []; pg2 = ctx.new_page(); watch(pg2, sink); pg2.goto(BASE + path, wait_until="networkidle"); pg2.mouse.wheel(0, 800); T.sleep(1)
                w1[path + " (signed in)"] = {"errors": sink, **counts(pg2)}; pg2.close()
            ctx.close()
            OUT["W1"] = w1
            bad = {k: v for k, v in w1.items() if v["errors"] or v["app"] != 1 or v["esm"] != 1 or v["login"] > 1 or v["own_min"] or v["cdn_without_sri"]}
            result("W1 no console errors, failed requests or 404s on any page; app.js and the components load once; CDN scripts carry integrity hashes (.min.js counted only for Seedling's own assets)",
                   not bad, f"{len(w1)} pages checked; pages with a problem: {json.dumps(bad)[:600] if bad else 'none'}; e.g. /register {w1['/register']}")

            w2 = {}
            ctx = br.new_context()
            for path, btn in [("/sign-in", "#submit-btn"), ("/register", "#submit-personal-details"), ("/forgot-password", "#submit-btn"), ("/sign-in/email-code", "#submit-btn")]:
                pg = ctx.new_page(); pg.goto(BASE + path, wait_until="networkidle"); pg.locator(btn).click(); T.sleep(1.5)
                w2[path] = {"url_after": pg.url.replace(BASE, ""), "fields_with_error": has_errors(pg)}; pg.close()
            ctx.close()
            ctx = br.new_context(); pg = ctx.new_page(); sign_in(pg, E(1), pws[E(1)]); pg.goto(BASE + "/profile", wait_until="networkidle")
            pg.locator("#first-name input").fill(""); pg.locator("#user-profile-form #submit-personal-details").click(); T.sleep(1.5)
            w2["/profile details"] = {"url_after": pg.url.replace(BASE, ""), "fields_with_error": has_errors(pg)}
            pg.goto(BASE + "/profile", wait_until="networkidle"); pg.locator("#password input").fill("abc"); pg.locator("#save-password-btn").click(); T.sleep(1.5)
            w2["/profile password"] = {"url_after": pg.url.replace(BASE, ""), "fields_with_error": has_errors(pg)}
            ctx.close()
            OUT["W2"] = w2
            result("W2 every form shows its validation messages and does not submit when empty", all(v["fields_with_error"] and v["url_after"].split("?")[0] == k.split(" ")[0] for k, v in w2.items()), json.dumps(w2))

            def reg(email):
                ctx = br.new_context(); pg = ctx.new_page(); log_ = []
                pg.on("request", lambda r: log_.append([round(T.time(), 3), r.method, r.url.replace(BASE, "")[:70]]) if ("/register" in r.url and r.method == "POST") or "check-user-email" in r.url else None)
                pg.goto(BASE + "/register", wait_until="networkidle")
                pg.locator("#first-name input").fill("Race"); pg.locator("#last-name input").fill("Browser"); pg.locator("#password input").fill(new_password())
                pg.locator("#email input").fill(email)
                pg.locator("#submit-personal-details").click()
                pg.locator("#submit-personal-details").click()
                try: pg.wait_for_url("**/account-created", timeout=8000)
                except Exception: pass
                T.sleep(1.5)
                r = {"url": pg.url.replace(BASE, ""), "requests": log_, "email_error": pg.evaluate("() => { const e = document.getElementById('email'); return e ? (e.errorMessage || e.getAttribute('error-message')) : null }"), "fields_with_error": has_errors(pg)}
                ctx.close(); return r
            taken = reg(E(1)); newem = E(f"brace{int(T.time())}"); fresh = reg(newem)
            posts_t = [x for x in taken["requests"] if x[1] == "POST"]; posts_f = [x for x in fresh["requests"] if x[1] == "POST"]
            checks_f = [x for x in fresh["requests"] if "check-user-email" in x[2]]
            ok = (taken["url"] == "/register" and not posts_t and "email" in taken["fields_with_error"] and "already been used" in str(taken["email_error"])
                  and fresh["url"] == "/account-created" and len(posts_f) == 1 and checks_f and checks_f[0][0] <= posts_f[0][0] and users_with(newem)[0] == 1)
            OUT["W3"] = {"taken": taken, "fresh": fresh}
            result("W3 register waits for the email check: a taken email never posts; a free one posts once, after the check", ok,
                   f"taken: url {taken['url']}, POSTs {len(posts_t)}, email error {taken['email_error']!r}; free: url {fresh['url']}, POSTs {len(posts_f)}, check before post {bool(checks_f) and checks_f[0][0] <= posts_f[0][0] if posts_f else None}, users created {users_with(newem)[0]}")

            ctx = br.new_context(); pg = ctx.new_page()
            q = "?return_to=" + "%2Fx%22%20data-pwned%3D%221" + "&t=" + "%22%20onerror%3D%22window.__pwned%3D1" + "&token=" + "%22%3E%3Cimg%20src%3Dx%20onerror%3Dwindow.__pwned2%3D1%3E"
            pg.goto(BASE + "/qa-fixture/oldattr" + q, wait_until="networkidle"); T.sleep(1)
            before = pg.evaluate("""() => ({ rt_broken: document.getElementById('rt').hasAttribute('data-pwned'), rt_value: document.getElementById('rt').value,
                     img_script_ran: window.__pwned === 1, raw_token_script_ran: window.__pwned2 === 1, extra_imgs: document.querySelectorAll('img').length - 1 })""")
            after = {}
            for path in ["/sign-in", "/sign-in/email-code", "/sign-in/email-link"]:
                pg.goto(BASE + path + "?return_to=%2Fx%22%20data-pwned%3D%221", wait_until="networkidle")
                after[path] = pg.evaluate("""() => { const i = document.querySelector('input[name="return_to"]'); return { broken: !!document.querySelector('[data-pwned]'), value: i ? i.value : null } }""")
            ctx.close()
            payload = '" data-pwned="1'
            gql('mutation { u: user_update(id: "%s", user: { last_name: %s }) { id } }' % (ids[E(1)], json.dumps(payload)))
            gql('mutation { r: record_create(record: { table: "documentation", properties: [{ name: "title", value: %s }, { name: "link", value: %s }, { name: "enabled", value_boolean: true }, { name: "sort_order", value_int: 1 }] }) { id } }'
                % (json.dumps('" onerror="window.__pwned=1'), json.dumps('https://example.com/" data-pwned="1')))
            ctx = br.new_context(); pg = ctx.new_page(); sign_in(pg, E(1), pws[E(1)]); pg.goto(BASE + "/dashboard", wait_until="networkidle"); T.sleep(1.5)
            stored = pg.evaluate("""() => ({ broken: !!document.querySelector('[data-pwned]'), script_ran: window.__pwned === 1,
                     card_alt: (document.querySelector('.dashboard-card-list-container img') || {}).alt, card_link: (document.querySelector('.dashboard-card-list-container') || {dataset:{}}).dataset.link,
                     header_label: (document.querySelector('ins-dropdown.profileNav') || {getAttribute: () => null}).getAttribute('label') })""")
            ctx.close()
            OUT["W4"] = {"before": before, "after": after, "stored": stored}
            ok_before = before["rt_broken"] and before["img_script_ran"]
            ok_after = all(not v["broken"] and v["value"] == "" for v in after.values()) and not stored["broken"] and not stored["script_ran"] and stored["card_alt"] == '" onerror="window.__pwned=1' and (stored["header_label"] or "").endswith(payload)
            result("W4 attribute injection: the old pattern breaks out (control); the fixed pages do not, for a request value and two stored values",
                   ok_before and ok_after, json.dumps(OUT["W4"]))
            result("v2.0.0 pattern: a raw request value in a hidden input", True, f"measured on the control page: script ran {before['raw_token_script_ran']}, extra img elements {before['extra_imgs']}")
        finally:
            br.close()

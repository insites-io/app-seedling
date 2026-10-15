"""Suite sec: the security cases for password sign-in, 2FA, password reset and the rate limits.
Ported from the QA harness that passed at e88460e. Rate limits are reached by inserting the earlier
attempt rows (seed), then making only the request that must be refused plus one control below the limit."""
import calendar
import collections
import json
import re
import threading
import time as T
import urllib.parse

from lib.client import *          # noqa: F401,F403  (BASE, S, admin, state, ... are set by run.py first)
from lib import client as C
from lib.registry import block, result

E = emails_for("sec")
pws, secs, ids = {}, {}, {}


def short(r): return f"{r[0]} {p(r)} {r[2].strip()[:110] if r[2].lstrip().startswith('{') else ''}".rstrip()
def rows(em, action, by="by_id"): return [r for r in state(em)["attempts"][by]["results"] if r["action"] == action]


def setup_2fa(n):
    em = E(n); A = S(f"2fa-setup-{n}")
    A.sign_in(em, pws[em]); b = A.get("/profile", tag="profile")[2]
    sec = re.search(r'<pre id="setup_code">([A-Z0-9]+)</pre>', b).group(1)
    r = A.otp(unused_code(em, sec), from_page="profile", csrf_from="/profile")
    st = state(em)["user"]; secs[em] = sec
    return p(r), st["client"][0]["otp_configured"] is True and st["otp"]["secret"] == sec


@block("sec", "setup", ["setup 26 users, 2FA on through /profile for 24 of them (not 2 and 3)"], setup=True)
def b_setup():
    """Create 26 users and turn 2FA on for 24 of them the way a user does."""
    for n in range(1, 27):
        ids[E(n)], pws[E(n)] = create_user(E(n))
    out = {}
    for n in [1] + list(range(4, 27)):
        out[n] = setup_2fa(n)
        if n % 10 == 0: clear("otp")
    clear("otp")
    ok = all(v == ("/profile?status=success", True) for v in out.values())
    result("setup 26 users, 2FA on through /profile for 24 of them (not 2 and 3)", ok and len(ids) == 26,
           f"ids {min(map(int, ids.values()))}..{max(map(int, ids.values()))}; 2FA set-up answers {sorted(set(out.values()))}")


@block("sec", "crit12", ["C2 password-only blocks /dashboard and /profile; code then opens them",
                         "C2 second browser with the password alone is still blocked",
                         "C1 disable-2fa refused: un-passed session (with and without a code), no session, anon CSRF, passed session with no code or a wrong code"])
def b_crit12():
    """2FA cannot be skipped with the password alone, and cannot be turned off without a passed session and a code."""
    clear("otp", "sign_in")
    em = E(1); pw = pws[em]; sec = secs[em]
    A, B, N = S("A"), S("B"), S("nosession")
    a1 = A.sign_in(em, pw); a2 = A.get("/dashboard"); a3 = A.get("/profile"); a4 = A.otp(unused_code(em, sec)); a5 = A.get("/dashboard")
    b1 = B.sign_in(em, pw); b2 = B.get("/dashboard"); b3 = B.get("/profile")
    result("C2 password-only blocks /dashboard and /profile; code then opens them", p(a1) == "/verify-2fa" and p(a2) == "/verify-2fa?return_to=%2Fdashboard" and p(a3) == "/verify-2fa?return_to=%2Fprofile" and p(a4) == "/dashboard" and a5[0] == 200,
           f"A sign-in {short(a1)}; /dashboard {short(a2)}; /profile {short(a3)}; code {short(a4)}; /dashboard {a5[0]}")
    result("C2 second browser with the password alone is still blocked", p(b1) == "/verify-2fa" and p(b2) == "/verify-2fa?return_to=%2Fdashboard" and p(b3) == "/verify-2fa?return_to=%2Fprofile",
           f"B sign-in {short(b1)}; /dashboard {short(b2)}; /profile {short(b3)}")
    tB = B.token("/verify-2fa")
    c1 = B.post("/api/disable-2fa", {"authenticity_token": tB, "otp_code": unused_code(em, sec)})
    c2 = B.post("/api/disable-2fa", {"authenticity_token": tB})
    c3 = N.post("/api/disable-2fa", {"otp_code": totp(sec)})
    tN = N.token("/sign-in"); c4 = N.post("/api/disable-2fa", {"authenticity_token": tN, "otp_code": totp(sec)})
    tA = A.token("/profile")
    c5 = A.post("/api/disable-2fa", {"authenticity_token": tA}); c6 = A.post("/api/disable-2fa", {"authenticity_token": tA, "otp_code": wrong_code(sec)})
    a6 = A.get("/dashboard"); b4 = B.get("/dashboard"); u = state(em)["user"]
    result("C1 disable-2fa refused: un-passed session (with and without a code), no session, anon CSRF, passed session with no code or a wrong code",
           [c1[0], c2[0], c3[0], c4[0], c5[0], c6[0]] == [403, 403, 403, 403, 422, 422] and a6[0] == 200 and b4[0] == 302 and u["client"][0]["otp_configured"] is True and [x["profile_type"] for x in u["profiles"]] == ["client"],
           f"B+code {short(c1)}; B no code {c2[0]}; no session {c3[0]}; anon csrf {c4[0]}; A no code {short(c5)}; A wrong {c6[0]}; A /dashboard {a6[0]}; B /dashboard {b4[0]}; otp_configured {u['client'][0]['otp_configured']}; profiles {[x['profile_type'] for x in u['profiles']]}")


@block("sec", "f1", ["F1 the same code in a second browser is refused; the next code works",
                     "F1 simultaneous submissions of one code: exactly one sign-in, no 5xx",
                     "F1 a code used to sign in is refused at disable-2fa; the next code works (control)"])
def b_f1():
    """A 2FA code works once, including under simultaneous submission."""
    clear("otp")
    em = E(15); sec = secs[em]
    A, B = S("F1a-A"), S("F1a-B"); A.sign_in(em, pws[em]); B.sign_in(em, pws[em])
    c = unused_code(em, sec, 10)
    r1 = A.otp(c); r2 = B.otp(c); d2 = B.get("/dashboard"); r3 = B.otp(unused_code(em, sec, 10)); d3 = B.get("/dashboard")
    result("F1 the same code in a second browser is refused; the next code works", p(r1) == "/dashboard" and p(r2) == "/verify-2fa?status=failed" and d2[0] == 302 and p(r3) == "/dashboard" and d3[0] == 200,
           f"A code {short(r1)}; B same code {short(r2)}; B /dashboard {d2[0]}; control B next code {short(r3)}, /dashboard {d3[0]}")
    plan = [16, 16, 14, 14, 19, 19, 15, 15, 16, 16]
    admin(op="backdate", k=ids[E(15)], act="otp", secs=960)
    ok = 0; slow = []; lines = []
    for t, n in enumerate(plan, 1):
        if t == 9: admin(op="backdate", k=ids[E(16)], act="otp", secs=960)
        em = E(n); sec = secs[em]
        X, Y = S(f"F1c{t}-X"), S(f"F1c{t}-Y"); X.sign_in(em, pws[em]); Y.sign_in(em, pws[em])
        tx, ty = X.token("/verify-2fa"), Y.token("/verify-2fa")
        c = unused_code(em, sec, 12); out = {}; dur = {}; bar = threading.Barrier(2)

        def go(name, s, tok):
            bar.wait(); t0 = T.time()
            out[name] = s.post("/account/2fa", {"2fa[otp_code]": c, "from_page": "verify-2fa", "authenticity_token": tok}, tag=f"F1-concurrent-{t}")
            dur[name] = round(T.time() - t0, 1)
        th = [threading.Thread(target=go, args=("X", X, tx)), threading.Thread(target=go, args=("Y", Y, ty))]
        [x.start() for x in th]; [x.join() for x in th]
        dx, dy = X.get("/dashboard")[0], Y.get("/dashboard")[0]
        ins = [k for k, v in out.items() if (v[1] or "").endswith("/dashboard")]
        ok += len(ins) == 1 and sorted([dx, dy]) == [200, 302]
        slow += [(t, k, out[k][0], dur[k]) for k in out if out[k][0] >= 500 or dur[k] > 15]
        lines.append(f"t{t} {n}: X {p(out['X'])} {dur['X']}s Y {p(out['Y'])} {dur['Y']}s dash {dx}/{dy}")
    print("\n".join(lines))
    result("F1 simultaneous submissions of one code: exactly one sign-in, no 5xx", ok == 10 and not slow, f"trials with exactly one sign-in {ok} of 10; 5xx or >15 s responses {slow}")
    em = E(17); sec = secs[em]; P = S("F1d"); P.sign_in(em, pws[em]); c = unused_code(em, sec, 12)
    r1 = P.otp(c); t = P.token("/profile")
    r2 = P.post("/api/disable-2fa", {"authenticity_token": t, "otp_code": c}); o2 = state(em)["user"]["client"][0]["otp_configured"]
    r3 = P.post("/api/disable-2fa", {"authenticity_token": t, "otp_code": unused_code(em, sec, 8)}); o3 = state(em)["user"]["client"][0]["otp_configured"]
    result("F1 a code used to sign in is refused at disable-2fa; the next code works (control)", p(r1) == "/dashboard" and r2[0] == 422 and o2 is True and r3[0] == 200 and o3 is False,
           f"sign-in {short(r1)}; disable same code {short(r2)} otp_configured {o2}; control next code {short(r3)} otp_configured {o3}")


@block("sec", "crit5", ["reset link works once", "made-up reset token refused", "another user's reset token refused (control: own email accepts it)",
                        "expired reset token refused (18 s token, opened 45 s later)",
                        "forgot-password limit 5 per email; the 6th and an unknown email get the same answer",
                        "email-check response shape: same keys for registered and unregistered, no id or number",
                        "email check 30 per IP, then 429"], emails=1)
def b_crit5():
    """Password reset tokens, the forgot-password limit and the email-check endpoint. The one real reset email is
    the 5th request for its address (4 earlier rows inserted), so it is also the control below the limit."""
    clear("forgot_password", "email_check")
    em = E(5); other = E(1)
    seed("forgot_password", 4, key=em)
    BUDGET.expect("password reset")
    after0 = last_mail_id(); s = S("fp5"); f1 = forgot(s, em)
    fm = wait_mail(em, after0, SUBJECT_RESET)
    tok = state(em)["user"]["token"][0]["password_token"]
    st, shown, invalid, csrf = reset_form(s, em, tok)
    pw1 = new_password()
    a = reset_submit(s, em, tok, pw1, csrf); a2 = S("t1").sign_in(em, pw1); stored = state(em)["user"]["token"][0]["password_token"]
    pws[em] = pw1
    s2 = S("fp5b"); st2, shown2, invalid2, _ = reset_form(s2, em, tok)
    c = s2.token("/password-reset"); pw2 = new_password()
    b = reset_submit(s2, em, tok, pw2, c); b2 = S("t2").sign_in(em, pw2)
    in_mail = bool(fm) and urllib.parse.quote(tok, safe="") in fm[-1]["content"] or (bool(fm) and tok in fm[-1]["content"])
    result("reset link works once", p(f1) == "/forgot-password?sent=1" and len(fm) == 1 and in_mail and st == 200 and shown and not invalid and p(a) == "/password-reset?reset=done" and p(a2) == "/verify-2fa" and not stored
           and shown2 is False and invalid2 and p(b) == "/password-reset" and p(b2) == "/sign-in?error=invalid",
           f"forgot (5th request for the address, 4 earlier rows inserted) -> {short(f1)}; reset emails {len(fm)}, token in it {in_mail}; open {st} form {shown}; submit -> {p(a)}; new pw -> {p(a2)}; stored token after {stored!r}; reuse open form {shown2} invalid {invalid2}; reuse POST -> {p(b)}; that pw -> {p(b2)}")
    fake = "MXwxNzkxOTA0MDAwMA==--0123456789abcdef0123456789abcdef01234567"
    fo = reset_form(S("c"), em, fake); fp = reset_submit(s2, em, fake, pw2, c)
    result("made-up reset token refused", fo[:3] == (200, False, True) and p(fp) == "/password-reset", f"open {fo[:3]}; POST -> {p(fp)}")
    t2 = admin(op="mint", email=em, hours=0.005)["token"]
    x1 = reset_form(S("x1"), other, t2); x2 = reset_form(S("x2"), em, t2)
    result("another user's reset token refused (control: own email accepts it)", x1[:3] == (200, False, True) and x2[:3] == (200, True, False), f"U5 token + U1 email {x1[:3]}; control own email {x2[:3]}")
    T.sleep(45)
    e1 = reset_form(S("x3"), em, t2); e2 = reset_submit(S("x4"), em, t2, pw2, S("x5").token("/password-reset")); e3 = S("t5").sign_in(em, pw2)
    result("expired reset token refused (18 s token, opened 45 s later)", e1[:3] == (200, False, True) and p(e2) == "/password-reset" and p(e3) == "/sign-in?error=invalid", f"open {e1[:3]}; POST -> {p(e2)}; pw2 -> {p(e3)}")
    after = last_mail_id()
    sixth = p(forgot(S("f6"), em)); T.sleep(20)
    nrows = len(rows(em, "forgot_password", "by_email")); nmail = len(mails_to(em, after, subject=SUBJECT_RESET))
    unk = p(forgot(S("fu"), E("nobody")))
    result("forgot-password limit 5 per email; the 6th and an unknown email get the same answer", sixth == "/forgot-password?sent=1" and nrows == 5 and nmail == 0 and unk == "/forgot-password?sent=1",
           f"4 inserted rows + the 5th request above = {nrows} forgot_password rows (expected 5); the 6th -> {sixth}; reset emails for the 6th {nmail} (expected 0); unknown email -> {unk}")
    e = S("ec")
    r1 = e.get("/api/check-user-email-signup?email=" + urllib.parse.quote(E(2)), keep_body=True, headers={"Accept": "application/json"})
    r2 = e.get("/api/check-user-email-signup?email=" + urllib.parse.quote(E("nobody")), keep_body=True, headers={"Accept": "application/json"})
    j1, j2 = json.loads(r1[2]), json.loads(r2[2])
    result("email-check response shape: same keys for registered and unregistered, no id or number", r1[0] == 200 and r2[0] == 200 and sorted(j1) == sorted(j2) == ["email_status", "message"] and j1["email_status"] == "invalid" and j2["email_status"] == "valid" and not re.search(r'"id"|\d', r1[2] + r2[2]),
           f"registered {r1[0]} {r1[2].strip()}; unregistered {r2[0]} {r2[2].strip()}")
    seed("email_check", 27, ip="mine")
    codes = [e.get("/api/check-user-email-signup?email=probe%d%%40example.com" % i, tag="ec-rl", headers={"Accept": "application/json"})[0] for i in range(30, 33)]
    result("email check 30 per IP, then 429", codes == [200, 429, 429], f"2 checks above + 27 inserted rows from this IP, then requests 30..32 -> {codes} (expected 200 as the control below the limit, then 429, 429)")


@block("sec", "f4", ["F4 turning 2FA off and on rotates the secret: the old authenticator entry stops working"])
def b_f4():
    """Turning 2FA off and on gives a new secret."""
    clear("otp")
    em = E(18); S1 = secs[em]; A = S("F4A"); A.sign_in(em, pws[em])
    r1 = A.otp(unused_code(em, S1)); t = A.token("/profile")
    r2 = A.post("/api/disable-2fa", {"authenticity_token": t, "otp_code": unused_code(em, S1, 8)})
    st = state(em)["user"]; S2 = st["otp"]["secret"]
    b = A.get("/profile")[2]; m = re.search(r'<pre id="setup_code">([A-Z0-9]+)</pre>', b)
    r3 = A.otp(unused_code(em, S2), from_page="profile", csrf_from="/profile"); o3 = state(em)["user"]["client"][0]["otp_configured"]
    secs[em] = S2
    admin(op="backdate", k=ids[em], act="otp", secs=960)
    B = S("F4B"); r4 = B.sign_in(em, pws[em])
    r5 = B.otp(unused_code(em, S1)); d5 = B.get("/dashboard")[0]
    r6 = B.otp(unused_code(em, S2)); d6 = B.get("/dashboard")[0]
    t = B.token("/profile"); r7 = B.post("/api/disable-2fa", {"authenticity_token": t, "otp_code": unused_code(em, S1, 8)}); o7 = state(em)["user"]["client"][0]["otp_configured"]
    ok = (p(r1) == "/dashboard" and r2[0] == 200 and st["client"][0]["otp_configured"] is False and S2 != S1 and bool(m) and m.group(1) == S2 and "<svg" in b
          and p(r3) == "/profile?status=success" and o3 is True and p(r4) == "/verify-2fa" and p(r5) == "/verify-2fa?status=failed" and d5 == 302 and p(r6) == "/dashboard" and d6 == 200 and r7[0] == 422 and o7 is True)
    result("F4 turning 2FA off and on rotates the secret: the old authenticator entry stops working", ok,
           f"pass {p(r1)}; off {r2[0]}; secret changed {S2 != S1}; profile shows new secret {bool(m) and m.group(1) == S2}, QR {'<svg' in b}; on with new {p(r3)} otp {o3}; new session {p(r4)}; OLD code {p(r5)} dash {d5}; NEW code {p(r6)} dash {d6}; disable with OLD {r7[0]} otp {o7}")


@block("sec", "f2", ["F2 correct sign-ins write no attempt rows; a wrong one writes one",
                     "sign-in limit 10 per email: the 11th wrong and then the right password are refused",
                     "spoofed X-Real-IP / X-Forwarded-For are ignored"])
def b_f2():
    """The password sign-in limit and its recording."""
    clear("sign_in")
    em = E(2)
    res = [p(S(f"F2ok{i}").sign_in(em, pws[em])) for i in range(1, 10)]; n0 = len(rows(em, "sign_in", "by_email"))
    w1 = p(S("F2w").sign_in(em, "wrong-1")); n1 = len(rows(em, "sign_in", "by_email"))
    ok1 = p(S("F2ok10").sign_in(em, pws[em])); n2 = len(rows(em, "sign_in", "by_email"))
    result("F2 correct sign-ins write no attempt rows; a wrong one writes one", res == ["/dashboard"] * 9 and n0 == 0 and w1 == "/sign-in?error=invalid" and n1 == 1 and ok1 == "/dashboard" and n2 == 1,
           f"9 correct -> {sorted(set(res))}, rows {n0}; wrong -> {w1}, rows {n1}; correct -> {ok1}, rows {n2}")
    seed("sign_in", 8, key=em)
    out = [p(S(f"F2w{i}").sign_in(em, f"wrong-{i}")).replace("/sign-in?error=", "") for i in (10, 11)]; n3 = len(rows(em, "sign_in", "by_email"))
    after = p(S("F2ok11").sign_in(em, pws[em]))
    result("sign-in limit 10 per email: the 11th wrong and then the right password are refused", out == ["invalid", "too_many"] and n3 == 10 and after == "/sign-in?error=too_many",
           f"1 real + 8 inserted wrong attempts, then wrong #10 (control) and #11 -> {out}; rows {n3}; correct after -> {after}")
    em3 = E(3); s = S("rl3"); t = s.token("/sign-in")
    r1 = s.post("/sign-in", {"email": em3, "password": "wrong-0", "authenticity_token": t}, headers={"X-Real-IP": "203.0.113.9", "X-Forwarded-For": "203.0.113.10"}, tag="spoof")
    ips = [r["ip"] for r in rows(em3, "sign_in", "by_email")]
    seed("sign_in", 8, key=em3)
    out = [p(s.sign_in(em3, f"wrong-{i}")).replace("/sign-in?error=", "") for i in (10, 11)]; after = p(s.sign_in(em3, pws[em3]))
    result("spoofed X-Real-IP / X-Forwarded-For are ignored", p(r1) == "/sign-in?error=invalid" and len(ips) == 1 and not ips[0].startswith("203.0.113") and out == ["invalid", "too_many"] and after == "/sign-in?error=too_many",
           f"spoofed wrong sign-in -> {p(r1)}, recorded ip {ips}; then 8 inserted rows, wrong #10 and #11 {out}; correct {after}")


@block("sec", "f3", ["F3 return_to stays on site: off-site, backslash, control characters and non-ASCII (U+0085, U+2028, U+2029, U+200B, U+FEFF, e-acute) are dropped; /profile is kept"])
def b_f3():
    """return_to on the 2FA step."""
    clear("otp")
    cases = [(8, "//example.com"), (8, "https://example.com"), (8, "/\\example.com"), (8, "/profile"),
             (9, "/\t/example.com"), (10, "/\n/example.com"), (11, "/\r/example.com"), (12, "/\x7f/example.com"), (13, "/\x00/example.com"),
             (20, "/\u0085/example.com"), (21, "/ /example.com"), (22, "/ /example.com"), (23, "/​/example.com"), (24, "/﻿/example.com"), (25, "/é/example.com"), (26, "/profile")]
    bad = []
    for n, rt in cases:
        em = E(n); s = S(f"rt{n}"); s.sign_in(em, pws[em])
        st, loc, b = s.get("/verify-2fa?return_to=" + urllib.parse.quote(rt, safe=""), tag="verify-form")
        m = re.search(r'<form action="([^"]*)"', b); act = m.group(1) if m else None
        r = s.otp(unused_code(em, secs[em]), return_to=rt, tag="return_to"); d = s.get("/dashboard")[0]
        want_act, want = ("/account/2fa?return_to=%2Fprofile", "/profile") if rt == "/profile" else ("/account/2fa", "/dashboard")
        good = act == want_act and r[0] == 302 and p(r) == want and d == 200
        if not good: bad.append((rt, act, r[0], p(r), d, r[2][:100]))
        print(f"  U{n:<2} return_to={urllib.parse.quote(rt, safe=''):28s} action={act!r:42s} POST -> {r[0]} {p(r)} | /dashboard {d}")
    result("F3 return_to stays on site: off-site, backslash, control characters and non-ASCII (U+0085, U+2028, U+2029, U+200B, U+FEFF, e-acute) are dropped; /profile is kept",
           not bad, f"{len(cases) - len(bad)} of {len(cases)} cases as expected; failures {bad}")


@block("sec", "crit3", ["quote, injection and wrong-length codes are refused; a valid code works (control)"])
def b_crit3():
    """Malformed 2FA codes."""
    clear("otp")
    lines = []; ok = True
    for n, payloads in [(6, ['12345"', 'VALID"', '123456", "valid": true, "x": "', '", "id": "1']), (7, ['1234567', '12345', 'abcdef', "' OR '1'='1"])]:
        em = E(n); sec = secs[em]; s = S(f"inj{n}"); s.sign_in(em, pws[em])
        for pl in payloads:
            code = pl.replace("VALID", totp(sec)); r = s.otp(code, tag="inject"); d = s.get("/dashboard")[0]
            lines.append((n, code, p(r), d)); ok = ok and p(r) == "/verify-2fa?status=failed" and d == 302
        nrows = len(rows(em, "otp")); lines.append((n, "otp rows", nrows)); ok = ok and nrows == 4
    admin(op="backdate", k=ids[E(6)], act="otp", secs=960)
    em = E(6); s = S("inj6ctl"); s.sign_in(em, pws[em]); r = s.otp(unused_code(em, secs[em])); d = s.get("/dashboard")[0]
    result("quote, injection and wrong-length codes are refused; a valid code works (control)", ok and p(r) == "/dashboard" and d == 200, f"{lines}; control -> {p(r)}, /dashboard {d}")


def alerts(em, after):
    return mails_to(em, after, subject=SUBJECT_ALERT)


@block("sec", "lock", ["2FA code limit 5 per user; the 6th wrong code locks out and even a right code is refused",
                       "6 wrong codes give one alert email, without the reset line",
                       "3 lockouts in 24 h force a reset: right code and right password refused, same answer as a wrong password and an unknown email",
                       "only the 3rd alert carries the reset line",
                       "the reset clears the lockouts and the user signs in with 2FA again",
                       "lockouts more than 24 h apart do not force a reset"], emails=2)
def b_lock():
    """2FA lockouts. Two real alert emails: the first lockout (no reset line) and the third (with it). The second
    lockout is an inserted row, and the reset token is minted, so neither sends an email."""
    clear("otp", "otp_lockout", "sign_in")
    def cnt(em, a): return len(rows(em, a))
    def locks(em): return [r["created_at"][:19] for r in rows(em, "otp_lockout")]
    em = E(4); sec = secs[em]; K = ids[em]; after0 = last_mail_id()
    BUDGET.expect("2FA lockout alert")
    s = S("lock4-1"); s.sign_in(em, pws[em]); l1 = []
    for i in range(1, 8):
        r = s.otp(wrong_code(sec), tag=f"L1-wrong-{i}"); l1.append((p(r), cnt(em, "otp"), cnt(em, "otp_lockout")))
    rc = s.otp(unused_code(em, sec)); dc = s.get("/dashboard")[0]
    a1 = wait_mail(em, after0, SUBJECT_ALERT, timeout=60)
    result("2FA code limit 5 per user; the 6th wrong code locks out and even a right code is refused", [x[1] for x in l1] == [1, 2, 3, 4, 5, 5, 5] and [x[2] for x in l1] == [0, 0, 0, 0, 0, 1, 1]
           and all(x[0] == "/verify-2fa?status=failed" for x in l1) and p(rc) == "/verify-2fa?status=failed" and dc == 302,
           f"7 wrong -> (answer, otp rows, lockouts) {l1}; right code during lockout {p(rc)}, /dashboard {dc}")
    T.sleep(10); a1 = alerts(em, after0)
    result("6 wrong codes give one alert email, without the reset line", len(a1) == 1 and RESET_LINE not in a1[0]["content"], f"alert emails after lockout 1: {len(a1)}; reset line present {[RESET_LINE in m['content'] for m in a1]}")
    admin(op="backdate", k=K, act="otp", secs=960); admin(op="backdate", k=K, act="otp_lockout", secs=1900)
    seed("otp_lockout", 1, key=K, back=960)
    ls = {2: locks(em)}
    after1 = last_mail_id()
    BUDGET.expect("2FA lockout alert with the reset line")
    s = S("lock4-3"); s.sign_in(em, pws[em])
    for i in range(6): s.otp(wrong_code(sec), tag="L3-wrong")
    ls[3] = locks(em)
    a3 = wait_mail(em, after1, SUBJECT_ALERT, timeout=60)
    rc = s.otp(unused_code(em, sec)); dc = s.get("/dashboard")[0]
    pa = p(S("l4a").sign_in(em, pws[em])); pb = p(S("l4b").sign_in(em, "nope")); pc = p(S("l4c").sign_in(E("none"), "nope"))
    result("3 lockouts in 24 h force a reset: right code and right password refused, same answer as a wrong password and an unknown email",
           len(ls[3]) == 3 and p(rc) == "/verify-2fa?status=failed" and dc == 302 and pa == pb == pc == "/sign-in?error=invalid",
           f"lockouts (the 2nd an inserted row) {ls}; right code {p(rc)} /dashboard {dc}; right pw {pa}; wrong pw {pb}; unknown {pc}")
    result("only the 3rd alert carries the reset line", len(a1) == 1 and RESET_LINE not in a1[0]["content"] and len(a3) == 1 and RESET_LINE in a3[0]["content"],
           f"alert for lockout 1 has the reset line: {RESET_LINE in a1[0]['content'] if a1 else None}; alerts for lockout 3: {len(a3)}, reset line {[RESET_LINE in m['content'] for m in a3]} (lockout 2 was an inserted row, so it sent nothing)")
    tok = admin(op="mint", email=em, hours=0.25)["token"]
    f = S("fp4"); st, shown, inv, c = reset_form(f, em, tok)
    npw = new_password()
    rr = reset_submit(f, em, tok, npw, c); lk, orow = cnt(em, "otp_lockout"), cnt(em, "otp")
    pws[em] = npw
    s = S("lock4-after"); r1 = s.sign_in(em, npw); r2 = s.otp(unused_code(em, sec)); d2 = s.get("/dashboard")[0]
    result("the reset clears the lockouts and the user signs in with 2FA again", shown and p(rr) == "/password-reset?reset=done" and lk == 0 and orow == 0 and p(r1) == "/verify-2fa" and p(r2) == "/dashboard" and d2 == 200,
           f"reset token minted where forgot-password stores it (no email); form {shown}; reset {p(rr)}; lockouts after {lk}, otp rows {orow}; new pw {p(r1)}; code {p(r2)}; /dashboard {d2}")
    em = E(7); sec = secs[em]; K = ids[em]
    admin(op="backdate", k=K, act="otp", secs=960)
    seed("otp_lockout", 1, key=K, back=90000); seed("otp_lockout", 1, key=K, back=1900); seed("otp_lockout", 1, key=K, back=960)
    lk = rows(em, "otp_lockout")
    age = lambda ts: T.time() - calendar.timegm(T.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
    in_day = [x for x in lk if age(x["created_at"]) < 86400]
    s = S("far7-final"); r1 = s.sign_in(em, pws[em]); r2 = s.otp(unused_code(em, sec)); d2 = s.get("/dashboard")[0]
    result("lockouts more than 24 h apart do not force a reset", len(lk) == 3 and len(in_day) == 2 and p(r1) == "/verify-2fa" and p(r2) == "/dashboard" and d2 == 200,
           f"3 lockout rows inserted, one 25 h back, so {len(in_day)} of {len(lk)} are in 24 h; password {p(r1)}; code {p(r2)}; /dashboard {d2}")


@block("sec", "final", ["no administrator profile on any of the 26 users", "/tests is not served",
                        "claim records cleaned: after a fresh claim none is older than 3 minutes"])
def b_final():
    """Profiles, the old test page and claim clean-up."""
    c = collections.Counter(); adm = []
    for n in range(1, 27):
        u = state(E(n))["user"]; pt = tuple(sorted(x["profile_type"] for x in u["profiles"])); c[pt] += 1; adm += [x for x in pt if "admin" in x]
    result("no administrator profile on any of the 26 users", not adm and set(c) <= {("client",), ("client", "modules/insites_crm/token")}, f"profile sets {dict(c)}; administrator-type {adm}")
    st = {pth: S("t").get(pth)[0] for pth in ["/tests", "/tests.json", "/test"]}
    result("/tests is not served", all(v == 404 for v in st.values()), f"{st}")
    clear("otp")
    em = E(1); A = S("claim-final"); A.sign_in(em, pws[em]); r = A.otp(unused_code(em, secs[em]))
    cl = state(em)["attempts"]["claims"]
    age = lambda ts: T.time() - calendar.timegm(T.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S"))
    ages = sorted(int(age(x["created_at"])) for x in cl["results"])
    result("claim records cleaned: after a fresh claim none is older than 3 minutes", p(r) == "/dashboard" and cl["total_entries"] >= 1 and ages and max(ages) <= 185, f"sign-in {p(r)}; claims {cl['total_entries']}, ages (s) {ages}")


@block("sec", "browser", ["C2 in a real browser: A passes 2FA, B with the password only is held at /verify-2fa",
                          "F5 headless pass over every page: 0 responses at 400+, 0 console errors"], browser=True)
def b_browser():
    """C2 and F5 in headless Chromium. The browser is closed in a finally."""
    from playwright.sync_api import sync_playwright
    em = E(10); pw = pws[em]; sec = secs[em]
    out = {"console": [], "failed": [], "steps": [], "requests": 0}

    def watch(page, name):
        page.on("console", lambda m: out["console"].append([name, m.type, m.text[:200], page.url]) if m.type == "error" else None)
        page.on("response", lambda r: out.__setitem__("requests", out["requests"] + 1) or (out["failed"].append([name, r.status, r.url[:200], page.url]) if r.status >= 400 else None))
        page.on("pageerror", lambda e: out["console"].append([name, "pageerror", str(e)[:200], page.url]))
        page.on("requestfailed", lambda r: out["failed"].append([name, "requestfailed", r.url[:200], page.url]))

    def step(name, page): out["steps"].append([name, page.url.replace(BASE, "")])

    def sign_in(page):
        page.goto(BASE + "/sign-in", wait_until="networkidle")
        page.locator("#email input").fill(em); page.locator("#password input").fill(pw)
        with page.expect_navigation(wait_until="networkidle"):
            page.locator("#submit-btn").click()

    clear("otp")
    with sync_playwright() as pwr:
        br = pwr.chromium.launch(headless=True)
        try:
            pc = br.new_context().new_page(); watch(pc, "anon")
            for path in ["/", "/sign-in", "/register", "/forgot-password", "/password-reset", "/sign-out", "/account-created",
                         "/sign-in/email-code", "/sign-in/code", "/sign-in/email-link", "/sign-in/link"]:
                pc.goto(BASE + path, wait_until="networkidle"); pc.mouse.wheel(0, 1200); pc.wait_for_timeout(500); step("anon " + path, pc)
            pa = br.new_context().new_page(); pb = br.new_context().new_page(); watch(pa, "A"); watch(pb, "B")
            sign_in(pa); step("A after password", pa)
            code = unused_code(em, sec, 10)
            with pa.expect_navigation(wait_until="networkidle"):
                pa.evaluate("c => { document.querySelector('input[name=\"2fa[otp_code]\"]').value = c; document.querySelector('form[action^=\"/account/2fa\"]').submit(); }", code)
            step("A after code", pa)
            for path in ["/dashboard", "/profile"]:
                pa.goto(BASE + path, wait_until="networkidle"); pa.mouse.wheel(0, 1200); pa.wait_for_timeout(500); step("A " + path, pa)
            sign_in(pb); step("B after password", pb)
            for path in ["/dashboard", "/profile"]:
                pb.goto(BASE + path, wait_until="networkidle"); step("B " + path, pb)
            pa.goto(BASE + "/dashboard", wait_until="networkidle"); step("A /dashboard again", pa)
        finally:
            br.close()
    want = {"A after password": "/verify-2fa", "A after code": "/dashboard", "A /dashboard": "/dashboard", "A /profile": "/profile", "B after password": "/verify-2fa",
            "B /dashboard": "/verify-2fa?return_to=%2Fdashboard", "B /profile": "/verify-2fa?return_to=%2Fprofile", "A /dashboard again": "/dashboard"}
    got = {s[0]: s[1] for s in out["steps"]}
    result("C2 in a real browser: A passes 2FA, B with the password only is held at /verify-2fa", all(got.get(k) == v for k, v in want.items()), json.dumps({k: got.get(k) for k in want}))
    result("F5 headless pass over every page: 0 responses at 400+, 0 console errors", out["requests"] > 0 and not out["failed"] and not out["console"],
           f"{len(out['steps'])} page loads, {out['requests']} responses; at 400+: {len(out['failed'])} {out['failed'][:5]}; console errors: {len(out['console'])} {out['console'][:5]}")

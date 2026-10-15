"""Suite fix: the two fixes made after v2.1.0 (TW#26894026).

  1. An emailed sign-in link that is no longer valid answers error=expired, including after a password reset.
  2. Changing a password on /profile asks for the current password, checks it on the server, and counts a
     wrong one against the same limit as password sign-in.

Every case carries its controls: the answers that must NOT change, and the live case that must still work.
One real link email proves that a link the instance emails behaves like a minted one; everything else is
minted or inserted by the fixture, so the suite sends 1 email."""
import re
import time as T
import urllib.parse

from lib.client import *          # noqa: F401,F403
from lib import client as C
from lib.registry import block, result, observed

E = emails_for("fix")
pws, ids = {}, {}
LINK_ERR = "/sign-in/email-link?error="


def link_rows(em): return state(em)["attempts"]["links"]["results"]
def row_by_id(rows_, rid): return [x for x in rows_ if str(x["id"]) == str(rid)][0]
def attempts(em, action="sign_in"): return [r for r in state(em)["attempts"]["by_email"]["results"] if r["action"] == action]


def reset_password(em, newpw):
    """The password reset flow with the email skipped: a token stored where forgot-password stores it, then the
    real /password-reset form and POST. Returns the POST answer."""
    tok = admin(op="mint", email=em, hours=0.25)["token"]
    F_ = S("fix-reset-" + em.split("@")[0][-6:])
    st, shown, invalid, csrf = reset_form(F_, em, tok)
    assert st == 200 and shown and csrf, ("reset form", st, shown, invalid)
    return reset_submit(F_, em, tok, newpw, csrf)


@block("fix", "setup", [], setup=True)
def b_setup():
    """Create the users the two fixes use."""
    for n in range(1, 9):
        ids[E(n)], pws[E(n)] = create_user(E(n), client=True)


@block("fix", "fix_link", ["F1 an emailed link used after a password reset answers expired",
                       "F1 controls: the other link answers are unchanged"])
def b_link():
    """An old emailed link after a password reset answers expired, and every other answer is what it was."""
    clear("forgot_password", "sign_in_link")
    em = E(1)
    # --- the case: open the link in two browsers, reset the password, then use it
    link, rid = mint_link(em)
    A = S("f1-A"); a, b = open_link(A, link)                 # A holds the link in its session, with the Continue form
    B = S("f1-B"); a2, b2 = open_link(B, link)
    live = b[0] == 200 and 'label="CONTINUE"' in b[2]
    newpw = new_password(); rr = reset_password(em, newpw); pws[em] = newpw
    reset_ok = p(rr) == "/password-reset?reset=done" and p(S("f1-new").sign_in(em, newpw)) == "/dashboard"
    again = A.get("/sign-in/link", tag="f1-again")           # the same browser asks for the link page again, before Continue
    rA = cont(A, body=b[2])                                  # Continue from the page opened before the reset
    C_ = S("f1-C"); a3, b3 = open_link(C_, link)             # a fresh browser opens the old link
    rB = cont(B, body=b2[2])                                 # the second browser's Continue
    # the person who resets in the SAME browser that holds the link
    em6 = E(6); link6, rid6 = mint_link(em6)
    G = S("f1-G"); g1, gb = open_link(G, link6)
    npw6 = new_password()
    tok6 = admin(op="mint", email=em6, hours=0.25)["token"]
    st6, shown6, inv6, csrf6 = reset_form(G, em6, tok6); rr6 = reset_submit(G, em6, tok6, npw6, csrf6); pws[em6] = npw6
    gagain = G.get("/sign-in/link", tag="f1-G-again"); rG = cont(G, body=gb[2])
    row = row_by_id(link_rows(em), rid)
    got = {"same browser resets, then Continue": p(rG), "same browser, link page before Continue": p(gagain), "Continue after the reset": p(rA), "link page before Continue": p(again), "old link, fresh browser": p(b3), "Continue, second browser": p(rB)}
    reset_ok = reset_ok and p(rr6) == "/password-reset?reset=done"
    ok = (live and reset_ok and all(v == LINK_ERR + "expired" for v in got.values()) and row["status"] == "pending"
          and signed_in(A)[0] == 302 and signed_in(C_)[0] == 302 and signed_in(B)[0] == 302)
    result("F1 an emailed link used after a password reset answers expired", ok,
           f"link opened and showed Continue before the reset: {live}; reset worked and the new password signs in: {reset_ok}; after the reset {got}; "
           f"row still {row['status']}; nobody signed in {signed_in(A)[0] == 302 and signed_in(C_)[0] == 302 and signed_in(B)[0] == 302}")

    # --- controls: the answers that must not change
    em2 = E(2); out = {}
    link2, rid2 = mint_link(em2)
    ok_s = S("c-live"); open_link(ok_s, link2); r_live = cont(ok_s); live_in = signed_in(ok_s)
    out["live link signs in"] = (p(r_live), live_in[0])
    r_reuse = S("c-reuse"); a, b = open_link(r_reuse, link2); out["reused link"] = p(b)
    link3, rid3 = mint_link(em2)
    q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(link3).query).items()}
    other, _ = mint_link(E(3)); q_other = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(other).query).items()}
    def mk(d): return BASE + "/sign-in/link?" + urllib.parse.urlencode(d)
    variants = {"tampered nonce": dict(q, n=q["n"][:-1] + ("A" if q["n"][-1] != "A" else "B")),
                "nonce from another account": dict(q, n=q_other["n"]),
                "swapped email (another account)": dict(q, e=E(3)),
                "swapped email (unknown address)": dict(q, e=E("nobody"))}
    for k, d in variants.items():
        X = S("c-var"); a, b = open_link(X, mk(d)); out[k] = p(b) if b else p(a)
    expired_by_time, rid4 = mint_link(E(4), expires=-60)
    X = S("c-time"); a, b = open_link(X, expired_by_time); out["link past its 15 minutes"] = p(b)
    # a post with no session at all (no form flag): the forged or missing CSRF case, still `session`
    N = S("c-nocsrf"); r_nc = N.post("/sign-in/link", {}, tag="c-nocsrf")
    out["post with no valid form session"] = p(r_nc)
    N2 = S("c-nocsrf2"); st, loc, body = N2.get("/sign-in/link", tag="c-flag")
    r_forged = N2.post("/sign-in/link", {"authenticity_token": "forged"}, tag="c-forged")
    out["post with a forged token"] = p(r_forged)
    row3 = row_by_id(link_rows(em2), rid3)
    want = {"live link signs in": ("/dashboard", 200), "reused link": LINK_ERR + "stale", "tampered nonce": LINK_ERR + "stale",
            "nonce from another account": LINK_ERR + "stale", "swapped email (another account)": LINK_ERR + "stale",
            "swapped email (unknown address)": LINK_ERR + "stale", "link past its 15 minutes": LINK_ERR + "expired",
            "post with no valid form session": LINK_ERR + "session", "post with a forged token": LINK_ERR + "session"}
    result("F1 controls: the other link answers are unchanged", out == want and row3["status"] == "pending",
           f"{out}; untouched link's row {row3['status']}")



@block("fix", "fix_link_real", ["F1 a link the instance emailed behaves the same after a reset"], emails=1)
def b_link_real():
    """The run's one real email: the same behaviour on a link the instance itself emailed."""
    clear("forgot_password", "sign_in_link")
    BUDGET.expect("sign-in link")
    em5 = E(5); s = S("f1-real"); after = last_mail_id(); r = req_link(s, em5)
    m = wait_mail(em5, after, SUBJECT_LINK)
    real = html_unescape(link_in(m[-1])) if m else ""
    Z = S("f1-real-open"); a, b = open_link(Z, real) if real else (None, None)
    shows = bool(b) and b[0] == 200 and 'label="CONTINUE"' in b[2]
    npw = new_password(); rr = reset_password(em5, npw)
    rZ = cont(Z, body=b[2]) if shows else None
    W = S("f1-real-fresh"); a2, b2 = open_link(W, real) if real else (None, None)
    result("F1 a link the instance emailed behaves the same after a reset", p(r) == "/sign-in/email-link?sent=1" and bool(m) and shows and p(rr) == "/password-reset?reset=done"
           and rZ is not None and p(rZ) == LINK_ERR + "expired" and b2 is not None and p(b2) == LINK_ERR + "expired",
           f"request -> {p(r)}; email {bool(m)}; link showed Continue {shows}; reset -> {p(rr)}; Continue after it -> {p(rZ) if rZ else None}; fresh browser -> {p(b2) if b2 else None}")


def html_unescape(s):
    import html
    return html.unescape(s)


def change_password(A, current, new, confirm=None, tag="fix-pw", token=None):
    b = A.get("/profile", tag="fix-pw-form")[2]
    d = {"password": new, "password_confirmation": new if confirm is None else confirm, "authenticity_token": token or form_token(b)}
    if current is not None:
        d["current_password"] = current
    return A.post("/profile/password", d, tag=tag)


@block("fix", "fix_password", ["F2 changing a password needs the current one",
                                   "F2 a wrong current password is refused, counted, and limited like sign-in",
                                   "F2 the correct current password changes the password as before"])
def b_current_password():
    """The profile password form asks for the current password and checks it on the server."""
    # --- refused without it, and with a wrong one: nothing changes
    em = E(6); pw = pws[em]
    A = S("f2-A"); A.sign_in(em, pw)
    page = A.get("/profile", tag="f2-page", keep_body=True)[2]
    has_field = 'name="current_password"' in page
    attempted = new_password()
    r_none = change_password(A, None, attempted)
    r_blank = change_password(A, "", attempted)
    still_in = signed_in(A)
    n0 = len(attempts(em))
    old_ok = p(S("f2-old").sign_in(em, pw)) == "/dashboard"
    new_ok = p(S("f2-new").sign_in(em, attempted)) == "/dashboard"
    result("F2 changing a password needs the current one", has_field and p(r_none) == "/profile?error=current_required" and p(r_blank) == "/profile?error=current_required"
           and still_in[0] == 200 and old_ok and not new_ok and n0 == 0,
           f"profile page has a current_password field {has_field}; post without the field -> {p(r_none)}; with it blank -> {p(r_blank)}; still signed in {still_in[0] == 200}; "
           f"attempt rows {n0} (a missing password is not a wrong one); "
           f"old password still works {old_ok}; the attempted new password works {new_ok}")

    # --- a wrong current password: refused, counted as a sign-in attempt, refused for good at the limit
    em = E(7); pw = pws[em]; A = S("f2-B"); A.sign_in(em, pw)
    w0 = len(attempts(em))
    r_wrong = change_password(A, "not-the-password", attempted)
    w1 = len(attempts(em)); still = signed_in(A)
    old_ok = p(S("f2-old2").sign_in(em, pw)) == "/dashboard"
    w1b = len(attempts(em))                                   # a correct password sign-in records nothing
    seed("sign_in", 8, key=em, ip=OTHER_IP)                   # 1 + 8 = 9 failures so far
    r_ninth_plus = change_password(A, "wrong-again", attempted); w10 = len(attempts(em))   # the 10th failure
    r_locked = change_password(A, pw, attempted)              # the right password, but the limit is reached
    r_signin = p(S("f2-lock").sign_in(em, pw))
    still2 = signed_in(A); old_ok2 = r_signin == "/sign-in?error=too_many"
    # control below the limit: 9 failures then the correct current password works
    em2 = E(8); pw2 = pws[em2]; seed("sign_in", 9, key=em2, ip=OTHER_IP)
    C2 = S("f2-C"); C2.sign_in(em2, pw2); npw = new_password(); r_ctrl = change_password(C2, pw2, npw)
    pws[em2] = npw
    ok = (p(r_wrong) == "/profile?error=current_invalid" and w0 == 0 and w1 == 1 and still[0] == 200 and old_ok and w1b == 1
          and p(r_ninth_plus) == "/profile?error=current_invalid" and w10 == 10 and p(r_locked) == "/profile?error=too_many" and old_ok2 and still2[0] == 200
          and p(r_ctrl) == "/sign-out")
    result("F2 a wrong current password is refused, counted, and limited like sign-in", ok,
           f"wrong -> {p(r_wrong)}; attempt rows {w0}->{w1}; still signed in {still[0] == 200}; old password still works {old_ok}; "
           f"after 8 inserted rows a 10th wrong -> {p(r_ninth_plus)} (rows {w10}); the RIGHT current password at the limit -> {p(r_locked)}; "
           f"password sign-in at the limit -> {r_signin}; control, 9 failures then the right one -> {p(r_ctrl)}")

    # --- the right current password: as before
    em = E(2); pw = pws[em]; A = S("f2-D"); A.sign_in(em, pw)
    n_before = len(attempts(em)); npw = new_password()
    r_bad_confirm = change_password(A, pw, npw, confirm=new_password())
    r_ok = change_password(A, pw, npw); after = signed_in(A)
    old = p(S("f2-o").sign_in(em, pw)); new = p(S("f2-n").sign_in(em, npw)); pws[em] = npw
    T_ = S("f2-nocsrf"); T_.sign_in(E(3), pws[E(3)]); r_nt = T_.post("/profile/password", {"current_password": pws[E(3)], "password": npw, "password_confirmation": npw}, tag="f2-nocsrf")
    result("F2 the correct current password changes the password as before", p(r_bad_confirm) == "/profile?error=password_mismatch" and p(r_ok) == "/sign-out" and after[0] == 302
           and old == "/sign-in?error=invalid" and new == "/dashboard" and len(attempts(em)) == n_before + 1 and p(r_nt).startswith("/sign-in"),
           f"right current + mismatched confirmation -> {p(r_bad_confirm)}; right current -> {p(r_ok)}; /dashboard after {after}; old password -> {old}; new -> {new}; "
           f"no token -> {p(r_nt)}; sign_in attempt rows {n_before} -> {len(attempts(em))} (one is the old-password sign-in above)")

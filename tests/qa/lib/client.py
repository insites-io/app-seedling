"""The HTTP side of the suite: one cookie-jar browser session per S(name), the test fixture, the sent-email
log, TOTP, and the email budget. run.py calls init() before any suite module is imported, because the
suites take BASE and the helpers from here with `from lib.client import *`. Every request is appended to
logs/requests.jsonl with passwords redacted."""
import base64
import hashlib
import hmac
import html as _html
import http.cookiejar
import json
import os
import re
import secrets as _secrets
import struct
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = None
CFG = None
INST = None
KEY = None
LOG = None
BUDGET = None
HDR = {"Accept": "*/*", "User-Agent": "seedling-qa-suite"}
OTHER_IP = "192.0.2.77"            # TEST-NET-1: seeded per-key rows never count towards this machine's per-IP limits
USED = {}                          # TOTP codes already used per address (codes are single use)
DELIVERED = {}                     # the real emails a run made, reused by later cases in the same run


class EmailCeiling(SystemExit):
    pass


def init(cfg, inst, key, log_path, budget):
    global BASE, CFG, INST, KEY, LOG, BUDGET
    BASE, CFG, INST, KEY, LOG, BUDGET = cfg.url, cfg, inst, key, log_path, budget


def log(e):
    e["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if LOG:
        with open(LOG, "a") as f:
            f.write(json.dumps(e) + "\n")
    return e


# ---------------------------------------------------------------- TOTP
def totp(secret, t=None, step=30):
    s = secret.strip().replace(" ", "").upper(); s += "=" * (-len(s) % 8)
    c = int((t or time.time()) // step)
    h = hmac.new(base64.b32decode(s), struct.pack(">Q", c), hashlib.sha1).digest(); o = h[-1] & 15
    return "%06d" % ((struct.unpack(">I", h[o:o + 4])[0] & 0x7FFFFFFF) % 1000000)


def unused_code(email, secret, min_left=6):
    """A current code this run has not used for this user yet (codes are single use)."""
    while True:
        left = 30 - (time.time() % 30)
        if left < min_left:
            time.sleep(left + 0.5); continue
        c = totp(secret)
        if c not in USED.get(email, []):
            USED.setdefault(email, []).append(c); return c
        time.sleep(left + 0.5)


def wrong_code(secret):
    return "%06d" % ((int(totp(secret)) + 500000) % 1000000)


# ---------------------------------------------------------------- sessions
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class S:
    def __init__(self, name):
        self.name = name; self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPCookieProcessor(self.jar))

    def req(self, method, path, data=None, headers=None, tag=None, keep_body=False):
        h = dict(HDR); h.update(headers or {})
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        if body is not None: h.setdefault("Content-Type", "application/x-www-form-urlencoded")
        url = path if path.startswith("http") else BASE + path
        if urllib.parse.urlparse(url).netloc != CFG.host:
            raise SystemExit(f"REFUSED: a request to {urllib.parse.urlparse(url).netloc}, which is not INSITES_URL")
        t0 = time.time()
        for attempt in range(4):
            r = urllib.request.Request(url, data=body, headers=h, method=method)
            try:
                resp = self.op.open(r, timeout=90); st, hd, b = resp.status, resp.headers, resp.read().decode("utf-8", "replace"); break
            except urllib.error.HTTPError as e:
                st, hd, b = e.code, e.headers, e.read().decode("utf-8", "replace")
                if st in (521, 522, 523, 525) and attempt < 3:
                    log({"s": self.name, "tag": "EDGE-RETRY", "m": method, "path": path[:120], "status": st}); time.sleep(3); continue
                break
            except (urllib.error.URLError, ConnectionError, OSError) as e:
                log({"s": self.name, "tag": "NETWORK-RETRY", "m": method, "path": path[:120], "err": str(getattr(e, "reason", e))})
                if attempt == 3: raise
                time.sleep(3)
        safe = {k: ("<redacted>" if k in ("password", "password_confirmation") else v) for k, v in (data or {}).items()}
        e = {"s": self.name, "tag": tag, "m": method, "path": path[:200], "data": safe, "status": st, "loc": hd.get("Location"), "len": len(b), "secs": round(time.time() - t0, 2)}
        if keep_body or len(b) < 400: e["body"] = b[:400]
        log(e)
        return st, hd.get("Location"), b

    def get(self, p, **k): return self.req("GET", p, **k)
    def post(self, p, d, **k): return self.req("POST", p, d, **k)

    def token(self, path):
        st, loc, b = self.get(path, tag="csrf-src")
        m = re.search(r'name="authenticity_token" value="([^"]+)"', b) or re.search(r"name='authenticity_token' value='([^']+)'", b)
        return m.group(1) if m else None

    def sign_in(self, email, pw, tag="sign_in"):
        t = self.token("/sign-in")
        return self.post("/sign-in", {"email": email, "password": pw, "authenticity_token": t}, tag=tag)

    def otp(self, code, return_to=None, from_page="verify-2fa", csrf_from="/verify-2fa", tag="otp"):
        t = self.token(csrf_from)
        p = "/account/2fa" + ("?return_to=" + urllib.parse.quote(return_to, safe="") if return_to is not None else "")
        return self.post(p, {"2fa[otp_code]": code, "from_page": from_page, "authenticity_token": t or ""}, tag=tag)


def p(r): return (r[1] or "").replace(BASE, "")
def sess_cookies(s): return {c.name: c.value for c in s.jar}


def form_token(body):
    m = re.search(r'name="authenticity_token" value="([^"]+)"', body); return m.group(1) if m else None


def signed_in(s):
    st, loc, b = s.get("/dashboard", tag="probe-dashboard"); return st, (loc or "").replace(BASE, "")


# ---------------------------------------------------------------- the fixture
def admin(**q):
    r = urllib.request.Request(BASE + "/qa-fixture/admin?" + urllib.parse.urlencode(q), headers=dict(HDR, **{"X-Inspect-Key": KEY}))
    for attempt in range(4):
        try:
            d = json.loads(urllib.request.urlopen(r, timeout=90).read().decode()); break
        except Exception:
            if attempt == 3: raise
            time.sleep(3)
    log({"tag": "fixture", "q": {k: (v if k not in ("pw", "code") else "<redacted>") for k, v in q.items()}, "res": d if q.get("op") not in ("mail", "mint_link", "mint") else "<omitted>"})
    return d


def state(email): return admin(op="state", email=email)


def emails_for(suite):
    """E(n) for one suite: a test address built from QA_EMAIL_PATTERN."""
    return lambda n: CFG.email(f"{suite}-{n}")


def new_password(prefix="Pq9!"):
    return prefix + _secrets.token_urlsafe(12)


def create_user(email, client=True):
    pw = new_password()
    r = admin(op="create", email=email, pw=pw, client="1" if client else "0")
    u = (r.get("res") or {}).get("user_create") or {}
    assert u.get("id"), r
    return u["id"], pw


def seed(act, n, key="", ip=OTHER_IP, back=0):
    """Insert n auth_attempt rows for one action. ip='mine' counts towards this machine's per-IP limit."""
    d = admin(op="seed", act=act, k=key, n=n, ip=ip, back=back)
    assert len([x for x in d["seeded"] if x]) == n, d
    return d


def clear(*acts, secs_back=None):
    """Move auth_attempt rows for these actions out of their window (the same as waiting)."""
    n = 0
    for a in acts:
        back = secs_back or (3700 if a == "sign_in_code_check" else (90000 if a == "otp_lockout" else 960))
        for _ in range(10):
            u = admin(op="backdate", act=a, secs=back)["updated"]; n += len(u)
            if len(u) < 100: break
    print(f"  [moved {n} attempt rows for {acts} out of the window]")


def mint_code(email, return_to="", expires=900, status="pending"):
    """A sign-in code request saved the way /sign-in/email-code saves one, for a known code, with no email."""
    code = "%06d" % _secrets.randbelow(1000000)
    d = admin(op="mint_code", email=email, code=code, return_to=return_to, expires=expires, status=status)
    assert d.get("id") and d.get("hash_set"), "the fixture could not mint a code (is SIGN_IN_HMAC_KEY set?)"
    return code, str(d["id"])


def mint_link(email, return_to="", expires=900, status="pending"):
    """A sign-in link request and its link, built the way /sign-in/email-link builds them, with no email."""
    d = admin(op="mint_link", email=email, return_to=return_to, expires=expires, status=status)
    assert d.get("id") and d.get("link", "").startswith(BASE + "/sign-in/link?"), "the fixture could not mint a link (is SITE_ORIGIN set to INSITES_URL?)"
    return d["link"], str(d["id"])


# ---------------------------------------------------------------- the sent-email log
def mail(n=20, page=1): return admin(op="mail", n=n, page=page)["mail"]
def sent_total(): return int(admin(op="sent_total")["total"])


def mails_to(email, after_id=0, kind=None, subject=None):
    """Sent-log rows addressed to email with id > after_id, oldest first."""
    got, page, PER = [], 1, 5
    while page <= 40:
        d = mail(PER, page)
        if d is None:
            r = []
            for i in range(PER):
                one = mail(1, (page - 1) * PER + i + 1)
                if one is None: continue
                r += one["results"]
        else:
            r = d["results"]
        got += r
        if not r or int(r[-1]["id"]) <= int(after_id): break
        page += 1
    rows = [m for m in got if int(m["id"]) > int(after_id) and email in (m["options"] or {}).get("to", [])]
    if kind: rows = [m for m in rows if m["notification_id"] == kind]
    if subject: rows = [m for m in rows if (m["options"] or {}).get("subject", "").startswith(subject)]
    return sorted(rows, key=lambda m: int(m["id"]))


def last_mail_id():
    """Id of the newest sent-log row the fixture can read (rows without a notification id are skipped)."""
    for i in range(1, 40):
        d = mail(1, i)
        if d is not None and d.get("results"): return int(d["results"][0]["id"])
        if d is not None and not d.get("results"): return 0
    raise SystemExit("no readable sent-log row in the newest 39")


def wait_mail(email, after, subject, timeout=90, want=1):
    t0 = time.time()
    while time.time() - t0 < timeout:
        m = mails_to(email, after, subject=subject)
        if len(m) >= want: return m
        time.sleep(3)
    return mails_to(email, after, subject=subject)


SUBJECT_CODE, SUBJECT_LINK = "Your sign-in code", "Your sign-in link"
SUBJECT_ALERT, SUBJECT_RESET = "Security alert for your account", "Password reset"
RESET_LINE = "your account now needs a password reset before you can sign in again"


def code_in(m):
    x = re.search(r"letter-spacing: 8px;\"><strong>(\d{6})</strong>", m["content"]); return x.group(1) if x else None


def link_in(m):
    x = re.search(r'<a href="([^"]+)" target="_blank"', m["content"]); return x.group(1) if x else None


class Budget:
    """Counts the emails a run causes and stops before the ceiling. Every case that makes the instance send
    an email calls expect() first; the instance's own sent-log total is checked as well, so an email
    nobody declared still counts."""

    def __init__(self, ceiling):
        self.ceiling, self.base, self.by_kind = ceiling, None, {}

    def start(self):
        self.base = sent_total()

    def measured(self):
        return sent_total() - self.base if self.base is not None else 0

    def declared(self):
        return sum(self.by_kind.values())

    def expect(self, kind, n=1):
        m = self.measured(); d = self.declared()
        if max(m, d) + n > self.ceiling:
            raise EmailCeiling(f"STOP: the next step would send {n} more email(s) ({kind}); this run has caused {max(m, d)} "
                               f"and the ceiling is {self.ceiling} (QA_EMAIL_CEILING). Nothing more was sent.")
        self.by_kind[kind] = self.by_kind.get(kind, 0) + n


# ---------------------------------------------------------------- page flows
def forgot(s, email, tag="forgot"):
    st, loc, b = s.get("/forgot-password", tag="forgot-form")
    return s.post("/forgot-password", {"email": email, "authenticity_token": form_token(b) or ""}, tag=tag)


def reset_form(s, email, token):
    q = "/password-reset?token=" + urllib.parse.quote(token, safe="") + "&email=" + urllib.parse.quote(email, safe="")
    st, loc, b = s.get(q, tag="reset-open")
    m = re.search(r'name="authenticity_token" value="([^"]+)"', b)
    return st, ('name="password"' in b or "name='password'" in b), ("Invalid Token" in b), (m.group(1) if m else None)


def reset_submit(s, email, token, pw, csrf):
    return s.post("/password-reset", {"email": email, "token": token, "password": pw, "password_confirmation": pw, "authenticity_token": csrf or ""}, tag="reset-submit")


def req_code(s, email, return_to=None, tag="req-code", token=True):
    q = "" if return_to is None else "?return_to=" + urllib.parse.quote(return_to, safe="")
    st, loc, b = s.get("/sign-in/email-code" + q, tag="req-code-form")
    d = {"email": email, "authenticity_token": form_token(b) if token is True else (token or "")}
    m = re.search(r'name="return_to" value="([^"]*)"', b)
    if m: d["return_to"] = _html.unescape(m.group(1))
    return s.post("/sign-in/email-code", d, tag=tag)


def submit_code(s, email, code, tag="submit-code", token=True, fresh_form=True):
    if fresh_form or not getattr(s, "_code_tok", None):
        st, loc, b = s.get("/sign-in/code", tag="code-form"); s._code_tok = form_token(b)
    d = {"email": email, "code": code, "authenticity_token": s._code_tok if token is True else (token or "")}
    return s.post("/sign-in/code", d, tag=tag)


def req_link(s, email, return_to=None, tag="req-link", token=True):
    q = "" if return_to is None else "?return_to=" + urllib.parse.quote(return_to, safe="")
    st, loc, b = s.get("/sign-in/email-link" + q, tag="req-link-form")
    d = {"email": email, "authenticity_token": form_token(b) if token is True else (token or "")}
    m = re.search(r'name="return_to" value="([^"]*)"', b)
    if m: d["return_to"] = _html.unescape(m.group(1))
    return s.post("/sign-in/email-link", d, tag=tag)


def open_link(s, url, tag="open-link"):
    """GET the emailed link, then follow its one redirect to /sign-in/link. Returns (first, second)."""
    a = s.get(url, tag=tag)
    b = s.get(a[1], tag=tag + "-follow", keep_body=True) if a[0] in (301, 302) and a[1] else None
    return a, b


def cont(s, tag="continue", token=True, body=None):
    if body is None:
        st, loc, body = s.get("/sign-in/link", tag="continue-form")
    return s.post("/sign-in/link", {"authenticity_token": form_token(body) if token is True else (token or "")}, tag=tag)

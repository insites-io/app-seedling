# Seedling QA suite

This folder holds the QA suite for Seedling's sign-in, 2FA, password reset, passwordless sign-in and the v2.1.0 clean-up work. It deploys the release to a test instance, runs 138 cases across four suites, checks that every file in `app/` reached the instance, removes everything it added, and compares a snapshot of the instance taken before the run with one taken after.

**Status.** The suite was ported from the QA harness that passed 132 of 132 cases against Seedling at commit `e88460e` on 15 October 2026. It has **not yet been run end to end in its committed form.** What has been checked so far: every Python file compiles, `--help` and `--list` work without contacting an instance, and the safety guard refuses an instance whose uuid does not match (and passes, read-only, one that does). Treat the first full run as the suite's own test, and expect to fix the suite before trusting a failure as a finding about Seedling.

## Before you start: this suite changes the instance

Run it only on an instance you can afford to change, never on production. A run:

- deploys `app/` plus the test pages in `fixtures/` with a **partial** deploy (`-p`), after a `--dry-run` that must show 0 deleted;
- creates about 60 test users, plus test records in Seedling's four tables, and sets a few constants;
- makes the instance send a handful of real emails (see [The email method](#the-email-method));
- then deletes all of it and puts back the one page Seedling overwrites.

Some things **cannot be undone**, because the instance keeps them:

| What | Why it stays |
|---|---|
| Rows in the instance's sent-email log | Sent-email records cannot be deleted |
| Event-stream entries | Registration writes a "New Registration" entry through the CRM controller, and those entries are permanent |
| Migration records | The two Seedling migrations are recorded as done the first time they run. Later deploys skip them, which is why `QA_SET_SIGN_IN_CONSTANTS` exists |
| Emails already delivered | On a staging stack every email reaches a real inbox |

The suite also needs an instance **without Seedling installed**. If any Seedling file other than the home page is already there, it stops before deploying, because clean-up could not tell Seedling's files from the run's.

## Prerequisites

| Need | For | Notes |
|---|---|---|
| `insites-cli` | the guard, GraphQL and Liquid reads and writes, the deploy, migrations | An environment in `.insites` that points at the instance |
| Python 3.9 or later | everything | The suite itself uses only the standard library |
| `playwright` (Python) and Chromium | the three browser blocks | `pip install -r tests/qa/requirements.txt` then `python3 -m playwright install chromium`. Skip them with `--skip-browser` |
| Node.js 18 or later | the TestCafe e2e step | `npm ci` in `tests/` (the runner does it if `node_modules` is missing) |
| macOS: Screen Recording permission | TestCafe in local mode | Or set `QA_TESTCAFE=remote` and open the printed URL in any browser, or `QA_TESTCAFE=off` |

Every browser runs headless and is closed when its block ends, including when the block fails.

## Configuration

Everything is set with environment variables. Nothing about an instance, a person or a secret is written in the suite.

| Variable | Required | Meaning |
|---|---|---|
| `INSITES_URL` | yes | The instance origin, for example `https://your-instance.example.com` |
| `QA_INSITES_ENV` | yes | The environment name in `.insites` that points at `INSITES_URL` |
| `QA_INSITES_CONFIG_DIR` | no | The folder holding that `.insites` file. Default: the repository root (where `.insites` is already ignored by git) |
| `QA_EXPECTED_INSTANCE_UUID` | yes | The uuid of the instance the suite is allowed to write to. The guard refuses any other |
| `QA_EMAIL_PATTERN` | yes | How test addresses are built. Must contain `{tag}` once, before the `@`, for example `qa+{tag}@example.com`. Every user the suite creates matches it, and clean-up deletes only users that match it |
| `QA_EMAIL_CEILING` | no | The most emails a run may cause. Default `15` |
| `QA_SET_SIGN_IN_CONSTANTS` | no | `1` to set `SIGN_IN_HMAC_KEY` (random) and `SITE_ORIGIN` (`INSITES_URL`) for the run when they are not set, and remove them afterwards. Needed when the Seedling migrations already ran on the instance in an earlier install, so the deploy skips the migration that creates the key |
| `QA_TESTCAFE` | no | `local` (default, headless Chrome), `remote`, or `off` |
| `SENDGRID_API_KEY` | no | When set, the run also reads SendGrid's Email Activity for the run's messages. When unset, the step is skipped with a printed note |
| `SENDGRID_SUBUSER` | no | The SendGrid subuser to read as, if the key belongs to a parent account |
| `QA_LOG_DIR` | no | Where logs go. Default `tests/qa/logs/`, which git ignores |

Each run picks a random six-character run id and puts it in every address, for example `qa+3fa9c1-pwl-13@example.com`, so a crashed run's leftovers never collide with the next run.

## How to run

```bash
pip install -r tests/qa/requirements.txt
python3 -m playwright install chromium

export INSITES_URL=https://your-instance.example.com
export QA_INSITES_ENV=qa
export QA_EXPECTED_INSTANCE_UUID=00000000-0000-0000-0000-000000000000   # your test instance's uuid
export QA_EMAIL_PATTERN='qa+{tag}@example.com'

python3 tests/qa/run.py --list                       # every block and case; contacts nothing
python3 tests/qa/run.py --guard-only                 # read the instance identity and stop; read-only
python3 tests/qa/run.py --yes-create-and-delete-test-data                       # the whole run
python3 tests/qa/run.py --yes-create-and-delete-test-data --suite pwl           # one suite
python3 tests/qa/run.py --yes-create-and-delete-test-data --case "10b"          # the block holding one case
python3 tests/qa/run.py --yes-create-and-delete-test-data --block lock          # one block by name
python3 tests/qa/run.py --yes-create-and-delete-test-data --cleanup-only        # finish a crashed run's clean-up
```

Cases in one block share users, codes and sessions, so asking for one case runs the block that holds it. Asking for any block also runs its suite's `setup` block first.

The run prints one `RESULT` line per case, then a summary with every count against its denominator: cases passed of cases declared per suite, cases failed and not run, app files that match the instance, emails caused against the ceiling, clean-up items removed, and the number of differences between the two snapshots. It exits 0 only when every selected case passed, the build matches, clean-up removed everything, the snapshots are equal and the email ceiling held.

The TestCafe e2e step runs only on a whole run, not with `--suite`, `--block` or `--case`. Build verification runs on every run.

## What a run does, in order

1. Checks the configuration and the `--yes-create-and-delete-test-data` flag. Nothing is contacted until both pass.
2. **The guard.** Reads `{{ context.instance.uuid }}|{{ context.location.host }}` with `insites-cli exec liquid` and refuses unless the uuid equals `QA_EXPECTED_INSTANCE_UUID`, the host equals `INSITES_URL`, and the `.insites` environment points at `INSITES_URL`. The guard runs again before the dry run, before the deploy, before every constant change and every GraphQL write made with `insites-cli`, and every 25 clean-up items. HTTP requests, including those to the fixture, are refused unless they go to the host of `INSITES_URL`.
3. Takes a read-only snapshot of every file record, table, profile type, user, constant name and migration, with a hash of each content field. Constant values are hashed, never stored.
4. Saves the full record of System Pages' home page (`views/pages/index.liquid`), which Seedling's `index.liquid` overwrites.
5. Copies `app/` and `fixtures/` into a build folder under the log folder. **`fixtures/` is never part of `app/`, so a normal deploy never ships the test pages.** Runs `insites-cli deploy -p --dry-run`, stops unless every line shows 0 deleted, then runs the partial deploy. Never a full deploy.
6. Sets `SEEDLING_QA_FIXTURE_KEY` to a random value for this run. The fixture pages answer 404 without that value in an `X-Inspect-Key` header.
7. Runs the selected blocks, then TestCafe, then build verification.
8. **Clean-up**, always, even after a failure: removes the records the run added to Seedling's tables, the users that match `QA_EMAIL_PATTERN`, the files and tables it deployed, and the constants it set (including the fixture key). Anything that looks added but is not the run's (a path it did not stage, a user that does not match the pattern) is reported and left alone. Then the saved home page is put back.
9. Takes the final snapshot and prints every difference from the first. A clean run shows 0.

If a run is interrupted, `--cleanup-only` rebuilds the clean-up list from the saved `logs/pre.json` and removes what is left.

## The email method

On a staging stack every email reaches a real inbox. Earlier passes sent about 150 and 90. This suite sends at most 10 on a full run, and usually 7 or 8:

| Email | Real ones | Where |
|---|---|---|
| Sign-in code | 1 | `pwl.c8_20`: the real address beside the unknown ones. Its code is then used to sign in |
| Sign-in link | 1 | `pwl.c8_20`, then reused by cases 14 to 17 |
| Password reset | 1 | `sec.crit5`: the 5th request for its address, so it is also the control below the limit. `pwl.smoke` sends one more only when suite `sec` did not run first |
| 2FA lockout alert | 2 | `sec.lock` (first lockout), `pwl.lockout_probe` (after a passwordless sign-in) |
| Alert with the reset line | 1 | `sec.lock` (third lockout) |
| Sign-in code with Globals as Reply-To | 1 | `cln.sender`, plus 1 more when suite `pwl` did not run first |
| Sign-in link, for suite `fix` | 1 | `fix.fix_link_real`: a link the instance emailed, used after a password reset. The reset itself is minted, not emailed |

Everything else avoids sending:

- **Delivery is proved once per template**, read back from the instance's sent-email log. Every other email case reads the sent log, including to prove that nothing was sent.
- **Codes and links are minted.** The fixture saves a sign-in code or link request the way the request page does: the same hash partial, the same `return_to` cleaning, the same named queries and the same `SITE_ORIGIN` link. Only the email is skipped.
- **Rate limits and lockouts are reached by inserting the earlier attempt rows** with the app's own `record_attempt` query. The suite then makes only the request that must be refused, plus one control just below the limit. Per-address rows carry a documentation IP address (192.0.2.77) so they never count toward this machine's per-IP limits; per-IP rows carry this machine's address as the instance sees it.
- **Reset tokens are minted** where forgot-password stores them, except for the one real reset email.
- **Expiry uses requests minted with an expiry in the past**, instead of waiting 15 minutes.

Each block that sends declares it first, and the run stops with a clear message before an email would take it past `QA_EMAIL_CEILING`. The instance's sent-log total is checked as well, so an email nobody declared still counts. The summary prints the emails caused, by template.

## What it proves

Suite `fix` was added after v2.1.0 (TW#26894026) and is not part of the 132. It holds the checks for two fixes made after the release, and its blocks are named `fix_link`, `fix_link_real` and `fix_password`, so `--suite fix` runs them alone. `fix_link_real` is the only block that sends an email (1). Run it on its own with `python3 tests/qa/run.py --yes-create-and-delete-test-data --suite fix`.


The 132 cases of suites `sec`, `pwl` and `cln` below come from the harness that passed 132 of 132 at `e88460e`. Every expectation and control was carried over. Where the method changed to save emails, the case title is the same and the printed detail says what was inserted or minted.

### Suite `fix`: The two fixes after v2.1.0 (6 cases)

| Block | Case |
|---|---|
| `fix_link` | F1 an emailed link used after a password reset answers expired (opened and used in separate browsers, and with the reset made in the same browser) |
| `fix_link` | F1 controls: a live link signs in; a reused link, a wrong nonce, a nonce from another account and a swapped address (known or unknown) answer stale; a link past its 15 minutes answers expired; a post with no valid form session or a forged token answers session |
| `fix_link_real` | F1 a link the instance emailed behaves the same after a reset (the one real email) |
| `fix_password` | F2 changing a password needs the current one: no field and a blank field are refused, nothing changes |
| `fix_password` | F2 a wrong current password is refused, counted as a sign-in attempt and limited like sign-in; the right one is refused at the limit; the right one works with 9 failures (control) |
| `fix_password` | F2 the correct current password changes the password as before: signs out, the old password stops working, the new one works, and a post without the token is refused |

### Suite `sec`: Security: password sign-in, 2FA, password reset and the rate limits (31 cases)

| Block | Case |
|---|---|
| `setup` | setup 26 users, 2FA on through /profile for 24 of them (not 2 and 3) |
| `crit12` | C2 password-only blocks /dashboard and /profile; code then opens them |
| `crit12` | C2 second browser with the password alone is still blocked |
| `crit12` | C1 disable-2fa refused: un-passed session (with and without a code), no session, anon CSRF, passed session with no code or a wrong code |
| `f1` | F1 the same code in a second browser is refused; the next code works |
| `f1` | F1 simultaneous submissions of one code: exactly one sign-in, no 5xx |
| `f1` | F1 a code used to sign in is refused at disable-2fa; the next code works (control) |
| `crit5` | reset link works once |
| `crit5` | made-up reset token refused |
| `crit5` | another user's reset token refused (control: own email accepts it) |
| `crit5` | expired reset token refused (18 s token, opened 45 s later) |
| `crit5` | forgot-password limit 5 per email; the 6th and an unknown email get the same answer |
| `crit5` | email-check response shape: same keys for registered and unregistered, no id or number |
| `crit5` | email check 30 per IP, then 429 |
| `f4` | F4 turning 2FA off and on rotates the secret: the old authenticator entry stops working |
| `f2` | F2 correct sign-ins write no attempt rows; a wrong one writes one |
| `f2` | sign-in limit 10 per email: the 11th wrong and then the right password are refused |
| `f2` | spoofed X-Real-IP / X-Forwarded-For are ignored |
| `f3` | F3 return_to stays on site: off-site, backslash, control characters and non-ASCII (U+0085, U+2028, U+2029, U+200B, U+FEFF, e-acute) are dropped; /profile is kept |
| `crit3` | quote, injection and wrong-length codes are refused; a valid code works (control) |
| `lock` | 2FA code limit 5 per user; the 6th wrong code locks out and even a right code is refused |
| `lock` | 6 wrong codes give one alert email, without the reset line |
| `lock` | 3 lockouts in 24 h force a reset: right code and right password refused, same answer as a wrong password and an unknown email |
| `lock` | only the 3rd alert carries the reset line |
| `lock` | the reset clears the lockouts and the user signs in with 2FA again |
| `lock` | lockouts more than 24 h apart do not force a reset |
| `final` | no administrator profile on any of the 26 users |
| `final` | /tests is not served |
| `final` | claim records cleaned: after a fresh claim none is older than 3 minutes |
| `browser` | C2 in a real browser: A passes 2FA, B with the password only is held at /verify-2fa |
| `browser` | F5 headless pass over every page: 0 responses at 400+, 0 console errors |

### Suite `pwl`: Passwordless: emailed code and emailed link (70 cases)

| Block | Case |
|---|---|
| `setup` | (setup only: Create 20 users with a client profile and one without, and turn 2FA on for 10, 11, 12, 16 and 18) |
| `smoke` | smoke register |
| `smoke` | smoke password sign-in, /dashboard, /profile |
| `smoke` | smoke 2FA set-up and /verify-2fa |
| `smoke` | smoke sign-out |
| `smoke` | smoke forgot password and reset |
| `smoke` | smoke 401/403/404/500 served by System Pages; signed-out redirects |
| `c1` | 1a password sign-in still goes to /dashboard |
| `c1` | 1b /sign-in shows three choices |
| `c1` | 1c return_to carried onto both email buttons |
| `c8_20` | 8 code request, unknown |
| `c8_20` | 8 code request, no client profile |
| `c8_20` | 20 link request, unknown |
| `c8_20` | 20 link request, no client profile |
| `link` | 14 link request |
| `link` | 15 opening the link |
| `link` | 16 Continue |
| `link` | 17 reused link |
| `link` | 18 tampered links |
| `code_basic` | 3 wrong code |
| `code_basic` | 2 right code |
| `code_basic` | 2 right code (first try) |
| `code_basic` | 6 reused code from a fresh session |
| `code_basic` | 7 A's code with another address |
| `code_basic` | 9 malformed code |
| `c4` | 4 five wrong then right |
| `c10` | 10a 6th request per address |
| `c10` | 10b 21st request per IP |
| `c10` | 10c 10 wrong codes in an hour block a fresh right code |
| `c11` | 11a 16 simultaneous wrong guesses |
| `c11` | 11a' right code after the race |
| `c11` | 11b 2 simultaneous right codes |
| `c11` | 11b 8 simultaneous right codes |
| `c11` | 11b 16 simultaneous right codes |
| `c12` | 12a 2FA user by code |
| `c12` | 12b 2FA user by link |
| `lockout_probe` | probe: 2FA lockout after sign-in by code |
| `lockout_probe` | probe: lockout holds for a new sign-in by link in the window |
| `c13` | 13 reset required after 3 lockouts |
| `c19` | 19 2 simultaneous Continues |
| `c19` | 19 8 simultaneous Continues |
| `fixation` | probe: session fixation (password) |
| `fixation` | probe: session fixation (code) |
| `fixation` | probe: session fixation (link) |
| `c21` | 21 SITE_ORIGIN unset |
| `c22` | 22 return_to '/profile' by code |
| `c22` | 22 return_to '/profile' by link |
| `c22` | 22 return_to 'https://evil.example' by code |
| `c22` | 22 return_to 'https://evil.example' by link |
| `c22` | 22 return_to '//evil.example' by code |
| `c22` | 22 return_to '//evil.example' by link |
| `c22` | 22 return_to '/\\evil.example' by code |
| `c22` | 22 return_to '/\\evil.example' by link |
| `c22` | 22 return_to '/\r\nSet-Cookie:x=1' by code |
| `c22` | 22 return_to '/\r\nSet-Cookie:x=1' by link |
| `c22` | 22 return_to '/café' by code |
| `c22` | 22 return_to '/café' by link |
| `c22` | 22 return_to '/verify-2fa' by code |
| `c22` | 22 return_to '/verify-2fa' by link |
| `c22` | 22 return_to '/api/users/id.json' by code |
| `c22` | 22 return_to '/api/users/id.json' by link |
| `c22` | 22 return_to /profile, 2FA user |
| `c22` | 22 request pages drop a bad return_to from the form |
| `c23` | 23 CSRF missing or forged on all four POSTs |
| `c23` | 23 control: the same code and link work with a real token |
| `c25` | 25 already signed in |
| `expiry` | 5a expired code |
| `expiry` | 5b unknown address after 15 min |
| `expiry` | 18 expired link |
| `browser` | 24 no token in address bar, history or page source |
| `browser` | 16b Continue in a real browser |

### Suite `cln`: Clean-up items and the browser checks (31 cases)

| Block | Case |
|---|---|
| `setup` | (setup only: Create 12 users with a client profile and one without) |
| `redirect` | 1a signed-out /dashboard and /profile go to /sign-in with return_to |
| `redirect` | 1b signed in, 2FA not passed -> /verify-2fa (control) |
| `redirect` | 1c after 2FA the return_to is honored |
| `redirect` | 1d signed in, no client profile: refused at the 403 page, no loop (the System Pages 403 page answers 200) |
| `redirect` | 1e password sign-in keeps a safe return_to and drops an off-site one |
| `register` | 2a register a new email |
| `register` | M4 registration is logged through the CRM controller |
| `register` | 2b duplicate email refused on the server |
| `register` | 2c a post without the form's session is refused |
| `register` | 2d server-side field checks |
| `register` | 2e ten simultaneous registrations for one email create one user |
| `reset_required` | 4a reset required: code and link refused with error=reset and NOT used up |
| `reset_required` | reg forgot password and reset |
| `reset_required` | 4b after the reset the SAME code signs in (it was not used up) |
| `passwordless_and_cf` | reg sign-in by emailed code |
| `passwordless_and_cf` | reg sign-in by emailed link |
| `passwordless_and_cf` | 5 /sign-in/link shows the address without JavaScript |
| `link_control` | 4c the refused link was not used up: once the lockouts are gone the SAME link signs in |
| `api` | M12 API errors carry their real status |
| `profile` | H6 profile details save, refuse a taken email, refuse a post without the token |
| `profile` | H6 change password: mismatch refused; change signs out; new password works, old does not |
| `profile` | H6 sign out posts with the token; a post without it signs nobody out |
| `dashboard_cache` | M5 dashboard not cached across users |
| `dashboard_cache` | M5 account-created still renders with its corrected cache key |
| `2fa` | reg 2FA: set up on profile, verify after password, turn off with a code |
| `sender` | M9 mail from the verified sender; Globals address only as Reply-To |
| `browser` | W1 no console errors, failed requests or 404s on any page; app.js and the components load once; CDN scripts carry integrity hashes (.min.js counted only for Seedling's own assets) |
| `browser` | W2 every form shows its validation messages and does not submit when empty |
| `browser` | W3 register waits for the email check: a taken email never posts; a free one posts once, after the check |
| `browser` | W4 attribute injection: the old pattern breaks out (control); the fixed pages do not, for a request value and two stored values |
| `browser` | v2.0.0 pattern: a raw request value in a hidden input |

## Logs

Everything a run writes goes to `QA_LOG_DIR` (default `tests/qa/logs/`, ignored by git): every HTTP request with passwords redacted (`requests.jsonl`), one line per case (`results.jsonl`), the dry run and deploy reports, the three snapshots, build verification, the clean-up log and the TestCafe log. The build folder holds a copy of `.insites` during the run and is deleted when the run ends. Never commit anything from `logs/`.

## Files

| Path | What it is |
|---|---|
| `run.py` | The entry point |
| `suites/sec.py`, `suites/pwl.py`, `suites/cln.py`, `suites/fix.py` | The four suites. Each case is declared on its block |
| `lib/config.py` | The environment variables |
| `lib/instance.py` | The guard, `insites-cli` calls and the partial deploy |
| `lib/client.py` | HTTP sessions, the fixture, the sent-email log, TOTP and the email budget |
| `lib/snapshot.py`, `lib/cleanup.py`, `lib/verify_build.py` | The snapshots, the clean-up and the build verification |
| `fixtures/views/pages/qa_fixture/` | The test pages the run deploys and removes. Never part of `app/` |
| `requirements.txt` | The one package the browser blocks need |

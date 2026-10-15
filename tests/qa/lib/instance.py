"""Everything that talks to the instance through insites-cli: the guard, GraphQL, Liquid, constants and the
partial deploy. Every write goes through guarded_*; the guard reads the instance uuid with exec liquid and
refuses unless it equals QA_EXPECTED_INSTANCE_UUID."""
import json
import os
import re
import shutil
import subprocess


class Refused(SystemExit):
    pass


class Instance:
    def __init__(self, cfg, log=print):
        self.cfg = cfg
        self.log = log
        self.writes_since_guard = 0

    # ------------------------------------------------------------ insites-cli
    def cli(self, args, cwd=None, timeout=300):
        p = subprocess.run(["insites-cli"] + args, cwd=cwd or self.cfg.config_dir, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr

    def liquid(self, code):
        rc, out, err = self.cli(["exec", "liquid", self.cfg.env_name, code], timeout=180)
        lines = [x for x in out.strip().splitlines() if x.strip()]
        return lines[-1].strip() if lines else (err.strip().splitlines() or [""])[-1]

    def gql(self, q, allow_errors=False):
        rc, out, err = self.cli(["exec", "graphql", self.cfg.env_name, q], timeout=300)
        if "{" not in out:
            raise SystemExit("insites-cli exec graphql gave no JSON for: " + q[:120] + "\n" + (out + err)[-600:])
        d = json.loads(out[out.find("{"):])
        if d.get("errors") and not allow_errors:
            raise SystemExit("graphql error: " + json.dumps(d["errors"])[:400])
        return d if allow_errors else d["data"]

    # ------------------------------------------------------------ the guard
    def read_identity(self):
        return self.liquid("{{ context.instance.uuid }}|{{ context.location.host }}")

    def guard(self, why="write"):
        """Refuse unless the environment really is the expected instance. Read-only."""
        envs = json.load(open(os.path.join(self.cfg.config_dir, ".insites")))
        env = envs.get(self.cfg.env_name) or {}
        env_url = (env.get("url") or "").rstrip("/")
        got = self.read_identity()
        uuid, _, host = got.partition("|")
        self.log(f"GUARD ({why}): environment {self.cfg.env_name} -> {env_url or '(none)'}; instance answers {uuid or got[:80]!r} on {host!r}")
        if env_url != self.cfg.url:
            raise Refused(f"REFUSED: environment {self.cfg.env_name} points at {env_url or 'nothing'}, not INSITES_URL {self.cfg.url}. Nothing was changed.")
        if uuid.strip().lower() != self.cfg.expected_uuid:
            raise Refused(f"REFUSED: the instance uuid is {uuid.strip() or 'unreadable'}, not QA_EXPECTED_INSTANCE_UUID {self.cfg.expected_uuid}. Nothing was changed.")
        if host.strip().lower() != self.cfg.host.lower():
            raise Refused(f"REFUSED: the instance answers as {host.strip()}, not {self.cfg.host}. Nothing was changed.")
        self.writes_since_guard = 0
        self.log("GUARD OK")

    def guarded_gql(self, q, allow_errors=False, every=1):
        if self.writes_since_guard % every == 0:
            self.guard("graphql write")
        self.writes_since_guard += 1
        return self.gql(q, allow_errors=allow_errors)

    # ------------------------------------------------------------ constants
    def constants(self):
        c = self.gql("query { c: constants(per_page: 200) { total_entries results { name } } }")["c"]
        return {r["name"] for r in c["results"]}

    def constant_set(self, name, value):
        d = self.guarded_gql('mutation { c: constant_set(name: %s, value: %s) { name } }' % (json.dumps(name), json.dumps(value)))
        assert d["c"]["name"] == name, d

    def constant_unset(self, name):
        d = self.guarded_gql('mutation { c: constant_unset(name: %s) { name } }' % json.dumps(name), allow_errors=True)
        return "errors" not in d

    def constant_value(self, name):
        """Read inside the instance only; the value is never printed or logged."""
        return self.liquid("{{ context.constants.%s | json }}" % name)

    # ------------------------------------------------------------ deploy
    def stage(self, stage_dir, app_dir, fixtures_dir):
        """A build folder holding the release app/ plus the test fixtures. app/ in the repository is never written."""
        if os.path.exists(stage_dir):
            shutil.rmtree(stage_dir)
        shutil.copytree(app_dir, os.path.join(stage_dir, "app"))
        shutil.copytree(fixtures_dir, os.path.join(stage_dir, "app"), dirs_exist_ok=True)
        dst = os.path.join(stage_dir, ".insites")
        shutil.copyfile(os.path.join(self.cfg.config_dir, ".insites"), dst)
        os.chmod(dst, 0o600)
        return stage_dir

    def partial_deploy(self, stage_dir, log_dir):
        """A --dry-run first, which must show 0 deleted on every line, then the partial (-p) deploy. Never a full deploy."""
        self.guard("dry run")
        rc, out, err = self.cli(["deploy", self.cfg.env_name, "-p", "--dry-run"], cwd=stage_dir, timeout=900)
        open(os.path.join(log_dir, "deploy-dry-run.txt"), "w").write(out + err)
        report = re.findall(r"^\s*(\w+)\s+(\d+) upserted\s+(\d+) deleted", out + err, re.M)
        if rc != 0 or not report:
            raise SystemExit(f"STOP: the dry run failed or printed no deploy report (exit {rc}); see deploy-dry-run.txt")
        deleting = [(k, d) for k, u, d in report if int(d)]
        if deleting:
            raise SystemExit(f"STOP: the dry run would delete {deleting}; nothing was deployed")
        self.log("dry run: " + ", ".join(f"{k} {u} upserted {d} deleted" for k, u, d in report))
        self.guard("partial deploy")
        rc, out, err = self.cli(["deploy", self.cfg.env_name, "-p"], cwd=stage_dir, timeout=1800)
        open(os.path.join(log_dir, "deploy.txt"), "w").write(out + err)
        report = re.findall(r"^\s*(\w+)\s+(\d+) upserted\s+(\d+) deleted", out + err, re.M)
        if rc != 0 or "succeeded" not in (out + err):
            raise SystemExit(f"STOP: the partial deploy failed (exit {rc}); see deploy.txt")
        if any(int(d) for k, u, d in report):
            raise SystemExit("STOP: the deploy report shows deletions; see deploy.txt")
        self.log("deploy: " + ", ".join(f"{k} {u} upserted {d} deleted" for k, u, d in report))

    def migrations(self):
        rc, out, err = self.cli(["migrations", "list", self.cfg.env_name], timeout=180)
        return dict(re.findall(r"Name: (\S+) - Status: (\S+)", out + err))

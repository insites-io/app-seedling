"""Configuration for the QA suite. Everything comes from environment variables; nothing about an
instance, a person or a secret is written in the code. See tests/qa/README.md, Configuration."""
import os
import re
import secrets
import time
from urllib.parse import urlparse

QA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(QA_DIR))
APP_DIR = os.path.join(REPO, "app")
FIXTURES_DIR = os.path.join(QA_DIR, "fixtures")
FIXTURE_KEY_CONSTANT = "SEEDLING_QA_FIXTURE_KEY"
FIXTURE_PATH_PREFIX = "views/pages/qa_fixture/"


class ConfigError(Exception):
    pass


class Config:
    def __init__(self, env=os.environ):
        self.url = (env.get("INSITES_URL") or "").strip().rstrip("/")
        self.env_name = (env.get("QA_INSITES_ENV") or "").strip()
        self.config_dir = os.path.abspath(env.get("QA_INSITES_CONFIG_DIR") or REPO)
        self.expected_uuid = (env.get("QA_EXPECTED_INSTANCE_UUID") or "").strip().lower()
        self.email_pattern = (env.get("QA_EMAIL_PATTERN") or "").strip().lower()
        self.email_ceiling = int(env.get("QA_EMAIL_CEILING") or "15")
        self.set_sign_in_constants = (env.get("QA_SET_SIGN_IN_CONSTANTS") or "").strip() in ("1", "yes", "true")
        self.testcafe = (env.get("QA_TESTCAFE") or "local").strip().lower()
        self.sendgrid_key = env.get("SENDGRID_API_KEY") or ""
        self.sendgrid_subuser = env.get("SENDGRID_SUBUSER") or ""
        self.log_dir = os.path.abspath(env.get("QA_LOG_DIR") or os.path.join(QA_DIR, "logs"))
        self.run_id = secrets.token_hex(3)
        self.started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    @property
    def host(self):
        return urlparse(self.url).netloc

    def problems(self):
        """Every missing or malformed setting, so one run reports them all."""
        out = []
        u = urlparse(self.url)
        if u.scheme != "https" or not u.netloc or u.path not in ("", "/"):
            out.append("INSITES_URL must be the instance origin, for example https://your-instance.example.com")
        if not self.env_name:
            out.append("QA_INSITES_ENV must name the environment in .insites that points at INSITES_URL")
        elif not os.path.exists(os.path.join(self.config_dir, ".insites")):
            out.append(f"no .insites file in {self.config_dir} (set QA_INSITES_CONFIG_DIR, or run insites-cli env add there)")
        if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", self.expected_uuid):
            out.append("QA_EXPECTED_INSTANCE_UUID must be the uuid of the instance the suite may write to")
        if self.email_pattern.count("{tag}") != 1 or "@" not in self.email_pattern or not self.email_pattern.index("{tag}") < self.email_pattern.index("@"):
            out.append("QA_EMAIL_PATTERN must hold {tag} once, before the @, for example qa+{tag}@example.com")
        if self.email_ceiling < 1:
            out.append("QA_EMAIL_CEILING must be 1 or more")
        if self.testcafe not in ("local", "remote", "off"):
            out.append("QA_TESTCAFE must be local, remote or off")
        return out

    def email(self, tag):
        """A test address. The run id keeps a crashed run's leftovers from colliding with the next run."""
        return self.email_pattern.replace("{tag}", f"{self.run_id}-{tag}".lower())

    def email_regex(self):
        """Matches every address this suite can create, from any run, and nothing else."""
        a, b = self.email_pattern.split("{tag}")
        return re.compile("^" + re.escape(a) + r"[0-9a-f]{6}-[a-z0-9.\-]+" + re.escape(b) + "$")

from config.settings import *  # noqa
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "/tmp/mtj_e2e.db"}}
MIGRATION_MODULES = {"jobs": None, "accounts": None, "tools": None}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
ALLOWED_HOSTS = ["*"]
SECURE_SSL_REDIRECT = False

# E2E only: MTJ_FAKE_AI=1 swaps OpenAI for a deterministic fake (no network, no cost).
import os as _os
if _os.environ.get("MTJ_FAKE_AI") == "1":
    import json as _json, re as _re, openai as _openai
    _os.environ.setdefault("OPENAI_API_KEY", "fake")

    class _Msg:
        def __init__(self, c): self.message = type("M", (), {"content": c})()

    class _Completions:
        def create(self, **kw):
            prompt = kw["messages"][0]["content"]
            m = _re.search(r"--- BEGIN RESUME ---\n(.*?)\n--- END RESUME ---", prompt, _re.S)
            lines = [l for l in (m.group(1) if m else "").splitlines() if l.strip().startswith("- ")]
            changes = [{"before": l.strip(), "after": "Led: " + l.strip()[2:], "why": "Stronger opening verb"} for l in lines[:3]]
            if "tips" in prompt and "BEGIN RESUME" in prompt and "Output JSON" in prompt:
                return type("R", (), {"choices": [_Msg(_json.dumps({"tips": ["Tip one", "Tip two", "Tip three"]}))]})()
            return type("R", (), {"choices": [_Msg(_json.dumps({"summary": "Marketing Ops specialist with hands-on platform administration.", "changes": changes}))]})()

    class _FakeOpenAI:
        def __init__(self, *a, **k): self.chat = type("C", (), {"completions": _Completions()})()

    _openai.OpenAI = _FakeOpenAI

# E2E: never try real SMTP from the sandbox (egress is blocked -> requests hang).
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

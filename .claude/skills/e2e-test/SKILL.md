---
name: e2e-test
description: Mandatory end-to-end testing before ANY push/deploy of martechjobs.io — production-sized data, real browser (Playwright/Chromium), full scenario checklist. Use whenever code is ready to ship or the founder asks to test.
---

# E2E testing for martechjobs.io (run before every push)

Founder's rule: test every scenario end to end before deploying. A Sept 2026 outage
(Resume Scanner 500s) passed tests on 3 sample jobs but timed out on ~190 real jobs.
Never test only with toy data.

## 1. Unit/integration suite (must be 100% green)
```bash
DEBUG=True SECRET_KEY=x python manage.py test
```
Tests build the DB from models (MIGRATION_MODULES=None for `test`). New features MUST add tests.
Also run `python manage.py makemigrations --check --dry-run` (DEBUG/SECRET_KEY env) for new models.

## 2. Production-sized local server
```bash
H=.claude/skills/e2e-test
export DEBUG=True SECRET_KEY=x PYTHONPATH=$H:. DJANGO_SETTINGS_MODULE=test_settings
rm -f /tmp/mtj_e2e.db && python manage.py migrate --run-syncdb -v0 && python $H/seed.py
python manage.py runserver 8765 --noreload   # run_in_background
```
Gotchas (learned the hard way):
- Django caches templates; with --noreload you MUST restart the server after editing a template.
- Stop the server with `pgrep -f "[m]anage.py runserver" | xargs -r kill` (a plain `pkill -f` matches its own shell).
- Never name a scratch script after a library (e.g. `click.py` shadows the `click` package).
- Sandbox can't reach martechjobs.io or Google Fonts (fallback fonts in screenshots are expected).
- Chromium: `glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome')`; never `playwright install`.
- Production is Python 3.9: grep new code for 3.10+ syntax (match/case, `X | None`, removeprefix).

Suites (each needs a FRESH seed + server restart — they share users/limits):
- `resume_scanner_e2e.py` — Resume Scanner core (49 scenarios).
- `phases_e2e.py` — fit badges, My Matches, AI tailor/docx/Pro gate. Start the server with
  `MTJ_FAKE_AI=1` (test_settings swaps OpenAI for a deterministic fake: no network, no cost).

## 3. Browser scenario checklist (write/extend a Playwright script; resume_scanner_e2e.py is the model)
For every changed page/flow cover:
- Happy path, anonymous AND signed-in.
- Every error: empty input, too short, wrong file type, oversized, corrupt, non-MarTech input, junk/closed IDs.
- Gates & limits (anon 1 free check → signup; members 5/month → limit message).
- State: save → reload remembers → replace → delete (page and Settings).
- Cold cache / first request timing (< ~5s; Render kills requests at 30s).
- Security: HTML/script in user input must not execute.
- Mobile 390px: `document.documentElement.scrollWidth <= 390`.
- Tracking: expected `window.dataLayer` events fire.
- Zero `pageerror` JS errors. Screenshot key screens and LOOK at them.
- Any element toggled with the `hidden` attribute must not have a CSS `display` that overrides it
  (add `[hidden]{display:none!important}`) — this bug shipped twice in Sept 2026.

## 4. Report
Give the founder: tests N/N, scenario list with PASS/FAIL, anything skipped and why. Then ask
for "push and deploy". Never push without that approval.

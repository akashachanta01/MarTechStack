---
name: deploy
description: Ship approved changes to martechjobs.io (GitHub PR squash-merge + Render deploy + log verification). Use ONLY after the founder explicitly says "push and deploy"/"push and merge".
---

# Deploy martechjobs.io

Precondition: the `e2e-test` skill has passed AND the founder said "push and deploy". Otherwise stop and ask.

1. Sync with main, keep branch versions, re-run tests:
   ```bash
   git fetch -q origin main && git merge -X ours origin/main -m "Merge main (keep branch)"
   git diff origin/main --stat | tail -1     # sanity: only intended files
   DEBUG=True SECRET_KEY=x python manage.py test
   git push -u origin claude/vibrant-bell-g4cbjo
   ```
2. GitHub MCP: `create_pull_request` (owner akashachanta01, repo martechstack, head claude/vibrant-bell-g4cbjo,
   base main), then `merge_pull_request` merge_method=squash. If "merge conflicts" right after a push, wait a few
   seconds and retry (GitHub recomputes mergeability).
3. Render MCP: `trigger_deploy` service `srv-d4t3hkeuk2gs73ehrpl0`, workspace `tea-d4qusbbuibrs739obvl0`
   (autoDeploy is OFF). Env-var updates also trigger a deploy. The cron `crn-d55jjn75r7bs73f34og0` auto-deploys.
4. Wait ~3 min (background `sleep`, not foreground), then `list_logs` from deploy start with text filters
   `*Applying*`, `*rror*`, `*Traceback*`, `*Listening*`. Confirm migrations "OK" and gunicorn "Listening".
   Harmless on every boot: `NOTE: If you see 'no such table: django_site' error...`.
5. After deploy, ask the founder to try the feature; watch logs for 500s on the touched endpoints
   (`path` filter, e.g. `/tools/api/ats-match/`). A 500 with gunicorn `handle_abort` = worker timeout (30s).
6. Commit attribution lines per session instructions; never put model names in commits.

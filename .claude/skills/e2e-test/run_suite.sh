#!/bin/bash
# usage: mtj_run_suite.sh <suite.py>   fresh DB + fresh server + run suite
cd /home/user/MarTechStack
H=$PWD/.claude/skills/e2e-test
pgrep -f "[m]anage.py runserver 8765" | xargs -r kill 2>/dev/null; sleep 1
export DEBUG=True SECRET_KEY=x POSTHOG_KEY=${POSTHOG_KEY:-} PYTHONPATH=$H:. DJANGO_SETTINGS_MODULE=test_settings MTJ_FAKE_AI=1
rm -f /tmp/mtj_e2e.db && python manage.py migrate --run-syncdb -v0 && python $H/seed.py >/dev/null
setsid nohup timeout 900 python manage.py runserver 8765 --noreload > /tmp/mtj_srv.log 2>&1 < /dev/null &
sleep 5
mkdir -p /tmp/mtj_e2e_run && cd /tmp/mtj_e2e_run && timeout 500 python $H/$1 2>&1 | grep -E "FAIL|passed"
pgrep -f "[m]anage.py runserver 8765" | xargs -r kill 2>/dev/null
exit 0

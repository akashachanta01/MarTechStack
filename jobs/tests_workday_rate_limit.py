"""Nov 17 2026: Workday answered HTTP 429 on some mornings. Boards we could not read
were counted as empty and auto-disabled, and still-open jobs were hidden as stale."""
from unittest import mock

from django.test import TestCase, override_settings

from jobs.models import CompanySource, Job


class WorkdayRateLimitTests(TestCase):

    def _source(self, **kw):
        fields = dict(name="Acme", ats_type="workday", token="acme/Careers",
                      board_url="https://acme.wd3.myworkdayjobs.com/Careers", consecutive_empty=4)
        fields.update(kw)
        return CompanySource.objects.create(**fields)

    def _poll(self, post):
        from collections import Counter
        from jobs.management.commands.fetch_jobs import Command
        c = Command()
        c.processed_tokens, c.stats, c.total_added = set(), Counter(), 0
        c.get_headers = lambda: {}
        c.stdout = mock.Mock()
        c.style = mock.Mock()
        c.screener = mock.Mock()
        with mock.patch("jobs.management.commands.fetch_jobs.requests.post", side_effect=post), \
             mock.patch("jobs.management.commands.fetch_jobs.time.sleep") as sleep:
            c.poll_company_sources()
        return c, sleep

    def test_rate_limited_board_is_not_counted_as_empty_or_disabled(self):
        s = self._source()
        c, _ = self._poll(lambda *a, **k: mock.Mock(status_code=429, headers={}))
        s.refresh_from_db()
        self.assertTrue(s.enabled)
        self.assertEqual(s.consecutive_empty, 4)
        self.assertEqual(c.stats["source:poll_failed"], 1)
        self.assertEqual(c.stats["source:auto_disabled"], 0)
        self.assertEqual(c.stats["Workday:http_429"], 1)

    def test_truly_empty_board_is_still_disabled_after_five_polls(self):
        s = self._source()
        ok = mock.Mock(status_code=200)
        ok.json.return_value = {"total": 0, "jobPostings": []}
        c, _ = self._poll(lambda *a, **k: ok)
        s.refresh_from_db()
        self.assertFalse(s.enabled)
        self.assertEqual(c.stats["source:auto_disabled"], 1)

    def test_429_waits_for_retry_after_then_succeeds(self):
        self._source(consecutive_empty=0)
        calls = []
        ok = mock.Mock(status_code=200)
        ok.json.return_value = {"total": 0, "jobPostings": []}

        def post(*a, **k):
            calls.append(1)
            return mock.Mock(status_code=429, headers={"Retry-After": "12"}) if len(calls) == 1 else ok
        c, sleep = self._poll(post)
        self.assertEqual(len(calls), 2)
        self.assertIn(mock.call(12), sleep.call_args_list)
        self.assertEqual(c.stats["Workday:error"], 0)
        self.assertEqual(c.stats["Workday:throttle_waits"], 1)

    def test_429_waiting_is_capped_for_the_whole_run(self):
        from jobs.management.commands.fetch_jobs import Command
        for i in range(30):
            self._source(name=f"Co{i}", token=f"co{i}/Careers", consecutive_empty=0,
                         board_url=f"https://co{i}.wd3.myworkdayjobs.com/Careers")
        c, sleep = self._poll(lambda *a, **k: mock.Mock(status_code=429, headers={"Retry-After": "600"}))
        waited = sum(call.args[0] for call in sleep.call_args_list if call.args[0] >= 5)
        self.assertLessEqual(waited, Command._throttle_wait_left)
        self.assertEqual(c.stats["source:poll_failed"], 30)

    def test_daily_run_polls_boards_before_asking_about_single_jobs(self):
        from django.core.management import call_command
        calls = []
        with mock.patch("jobs.management.commands.run_daily_tasks.call_command",
                        side_effect=lambda *a, **k: calls.append(a[0])):
            call_command("run_daily_tasks", stdout=mock.Mock())
        for later in ("check_dead_links", "clean_stale_jobs", "recheck_pending"):
            self.assertLess(calls.index("fetch_jobs"), calls.index(later), later)
        self.assertLess(calls.index("recheck_pending"), calls.index("clean_job_data"))

    def test_single_job_checks_run_three_at_a_time(self):
        from jobs.management.commands import check_dead_links, recheck_pending
        for mod in (check_dead_links, recheck_pending):
            src = open(mod.__file__).read()
            self.assertIn("max_workers=3", src)
            self.assertNotIn("max_workers=8", src)

    def test_old_job_seen_five_days_ago_is_not_hidden_as_stale(self):
        from datetime import timedelta
        from django.core.management import call_command
        from django.utils import timezone
        now = timezone.now()

        def make(seen_days, n):
            j = Job.objects.create(title=f"Marketo Manager {n}", company="Acme", location="Remote",
                                   apply_url=f"https://boards.greenhouse.io/acme/jobs/{n}",
                                   description="Marketo", screening_status="approved", is_active=True)
            Job.objects.filter(pk=j.pk).update(went_live_at=now - timedelta(days=90),
                                               created_at=now - timedelta(days=90),
                                               last_seen_at=now - timedelta(days=seen_days))
            return j
        recent, old = make(5, 1), make(9, 2)
        call_command("clean_stale_jobs", stdout=mock.Mock())
        recent.refresh_from_db()
        old.refresh_from_db()
        self.assertTrue(recent.is_active)
        self.assertEqual(recent.screening_status, "approved")
        self.assertFalse(old.is_active)
        self.assertEqual(old.screening_status, "pending")


class ReenableWorkdayBoardsMigrationTests(TestCase):
    """Migration 0035 puts back Workday boards auto-disabled during the 429 days."""
    MIG = "jobs.migrations.0035_reenable_rate_limited_workday_boards"

    def _run(self):
        # Run with the HISTORICAL models, exactly as `migrate` does in production.
        import importlib
        from django.db.migrations.loader import MigrationLoader
        with override_settings(MIGRATION_MODULES={}):
            state = MigrationLoader(None, ignore_no_migrations=True).project_state(
                ("jobs", "0034_approve_kalsec_submission"))
        model = state.apps.get_model("jobs", "CompanySource")
        mod = importlib.import_module(self.MIG)
        for f in mod.FIELDS_USED:
            model._meta.get_field(f)      # every field used exists in the historical model
        mod.forwards(state.apps, None)

    def test_only_recently_disabled_workday_boards_come_back(self):
        import datetime as dt
        utc = dt.timezone.utc

        def src(name, ats, enabled, polled, empty):
            return CompanySource.objects.create(name=name, ats_type=ats, token=name.lower(), enabled=enabled,
                                                last_polled_at=polled, consecutive_empty=empty)
        nasdaq = src("Nasdaq", "workday", False, dt.datetime(2026, 11, 17, 9, tzinfo=utc), 5)
        old = src("OldCo", "workday", False, dt.datetime(2026, 10, 1, 9, tzinfo=utc), 5)
        asos = src("ASOS", "smartrecruiters", False, dt.datetime(2026, 11, 14, 9, tzinfo=utc), 5)
        adobe = src("Adobe", "workday", True, dt.datetime(2026, 11, 17, 9, tzinfo=utc), 2)
        self._run()
        self._run()   # safe to run twice
        for s in (nasdaq, old, asos, adobe):
            s.refresh_from_db()
        self.assertTrue(nasdaq.enabled)
        self.assertEqual(nasdaq.consecutive_empty, 0)
        self.assertFalse(old.enabled)
        self.assertFalse(asos.enabled)
        self.assertEqual(asos.consecutive_empty, 5)
        self.assertTrue(adobe.enabled)
        self.assertEqual(adobe.consecutive_empty, 0)


class WorkdayBlockGraceTests(TestCase):
    """Nov 21 2026: Workday refuses our server, so its jobs get 14 days, others 7."""

    def _make(self, url, seen_days, n):
        from datetime import timedelta
        from django.utils import timezone
        now = timezone.now()
        j = Job.objects.create(title=f"Marketo Manager {n}", company="Acme", location="Remote",
                               apply_url=url, description="Marketo",
                               screening_status="approved", is_active=True)
        Job.objects.filter(pk=j.pk).update(went_live_at=now - timedelta(days=90),
                                           created_at=now - timedelta(days=90),
                                           last_seen_at=now - timedelta(days=seen_days))
        return j

    def test_workday_job_unseen_ten_days_stays_live_other_ats_does_not(self):
        from django.core.management import call_command
        wd = self._make("https://acme.wd3.myworkdayjobs.com/Careers/job/x_1", 10, 1)
        wd_old = self._make("https://acme.wd3.myworkdayjobs.com/Careers/job/x_2", 15, 2)
        gh = self._make("https://boards.greenhouse.io/acme/jobs/3", 10, 3)
        call_command("clean_stale_jobs", stdout=mock.Mock())
        for j in (wd, wd_old, gh):
            j.refresh_from_db()
        self.assertTrue(wd.is_active)
        self.assertFalse(wd_old.is_active)
        self.assertFalse(gh.is_active)

    def test_first_429_logs_what_workday_said_once(self):
        from collections import Counter
        from jobs.management.commands.fetch_jobs import Command
        c = Command()
        c.processed_tokens, c.stats = set(), Counter()
        c.get_headers = lambda: {}
        c._company_name = lambda *a, **k: "Acme"
        resp = mock.Mock(status_code=429, headers={"Retry-After": "3600", "Server": "cloudflare"}, text="blocked")
        with mock.patch("jobs.management.commands.fetch_jobs.requests.post", return_value=resp), \
             mock.patch("jobs.management.commands.fetch_jobs.time.sleep"), \
             self.assertLogs("jobs.fetch", level="WARNING") as logs:
            c.fetch_workday_api("https://acme.wd3.myworkdayjobs.com/Careers")
            c.fetch_workday_api("https://beta.wd3.myworkdayjobs.com/Careers")
        detail = [l for l in logs.output if "429 detail" in l]
        self.assertEqual(len(detail), 1)
        self.assertIn("retry-after=3600", detail[0])
        self.assertIn("cloudflare", detail[0])

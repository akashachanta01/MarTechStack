"""
MarTechJobs test suite. Run before EVERY push:  python manage.py test

Covers: page smoke tests, the MarTech ATS Match feature, staff-page security,
and regression tests for bugs fixed in past audits.
"""
import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from jobs.ats_match import extract_terms, match
from jobs.models import BlogPost, Category, Job, Subscriber, Tool

JD_HTML = (
    "<p>Marketing Operations Manager. Own our <b>Marketo Engage</b> instance and "
    "Salesforce Marketing Cloud. Build lead scoring and lead routing, manage nurture "
    "streams. Track MQL-to-SQL conversion. Experience with Segment or a customer data "
    "platform. Marketo Certified Expert preferred. Community outreach and GTM alignment.</p>"
)
RESUME = (
    "Senior Marketing Ops Specialist\n"
    "- Administered Marketo; built lead score model lifting MQL-to-SQL conversion 22%\n"
    "- Ran Pardot nurture campaigns for 40k contacts across three regions\n"
    "- Managed SFMC email sends and journeys for the global team\n"
    "- Partnered with sales on routing rules and pipeline reporting"
)

TEST_SETTINGS = dict(SECURE_SSL_REDIRECT=False, ALLOWED_HOSTS=["*"])


def make_job(**kw):
    defaults = dict(
        title="Marketing Operations Manager", company="Acme", location="Remote",
        description=JD_HTML, apply_url="https://acme.test/apply",
        screening_status="approved", is_active=True, work_arrangement="remote",
    )
    defaults.update(kw)
    return Job.objects.create(**defaults)


# ---------------------------------------------------------------------------
# ATS engine (pure functions)
# ---------------------------------------------------------------------------
class ATSEngineTests(TestCase):
    def test_ignores_non_tool_words_in_jd(self):
        terms = extract_terms("Community outreach and GTM strategy alignment.", for_jd=True)
        self.assertNotIn("Outreach", terms)
        self.assertNotIn("Google Tag Manager", terms)

    def test_capitalized_product_name_counts(self):
        self.assertIn("Outreach", extract_terms("Experience with Outreach and Salesloft.", for_jd=True))

    def test_sales_qualified_leads_are_not_sql_language(self):
        self.assertNotIn("SQL", extract_terms("Track MQL-to-SQL conversion and SQLs by source.", for_jd=True))
        self.assertIn("SQL", extract_terms("Strong SQL and Python skills.", for_jd=True))

    def test_longest_match_wins(self):
        terms = extract_terms("Salesforce Marketing Cloud journeys", for_jd=True)
        self.assertIn("Salesforce Marketing Cloud", terms)
        self.assertNotIn("Salesforce", terms)

    def test_rebrand_wording_fix(self):
        r = match("Ran Pardot programs for years across many regions and teams.",
                  "Must know Marketing Cloud Account Engagement deeply.")
        fixes = {(f["you_wrote"], f["jd_says"]) for f in r["alias_fixes"]}
        self.assertIn(("Pardot", "Marketing Cloud Account Engagement"), fixes)

    def test_possessive_is_not_a_wording_difference(self):
        r = match("Administered Marketo's instance for a large B2B team.", "Own our Marketo instance.")
        self.assertEqual(r["alias_fixes"], [])

    def test_full_match_counts(self):
        r = match(RESUME, JD_HTML)
        self.assertEqual(r["required_count"], 8)
        self.assertEqual(r["matched_count"], 4)
        self.assertEqual({m["term"] for m in r["missing"]},
                         {"Marketo Certified Expert", "Segment", "Customer Data Platform", "Lead Routing"})


# ---------------------------------------------------------------------------
# ATS Match API + page
# ---------------------------------------------------------------------------
@override_settings(**TEST_SETTINGS)
class ATSMatchAPITests(TestCase):
    API = "/tools/api/ats-match/"

    def setUp(self):
        cache.clear()
        self.job = make_job()

    def post(self, client, body):
        r = client.post(self.API, data=json.dumps(body), content_type="application/json")
        return r.status_code, r.json()

    def test_page_renders_with_job(self):
        r = self.client.get(f"/tools/resume-keyword-scanner/?job={self.job.id}")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Marketing Operations Manager")
        self.assertContains(r, "FAQPage")

    def test_anonymous_gets_one_run_then_signup_gate(self):
        s, d = self.post(self.client, {"resume_text": RESUME, "job_id": self.job.id})
        self.assertEqual(s, 200)
        self.assertEqual((d["matched_count"], d["required_count"]), (4, 8))
        self.assertNotIn("alias_fixes", d)          # locked for anonymous
        self.assertEqual(d["locked_alias_fixes"], 2)
        s, d = self.post(self.client, {"resume_text": RESUME, "job_id": self.job.id})
        self.assertEqual((s, d.get("gate")), (403, "signup"))

    def test_validation(self):
        s, _ = self.post(self.client, {"resume_text": "too short", "job_id": self.job.id})
        self.assertEqual(s, 400)
        s, _ = self.post(self.client, {"resume_text": RESUME, "jd_text": "x"})
        self.assertEqual(s, 400)
        s, _ = self.post(self.client, {"resume_text": RESUME, "jd_text": "We need a friendly cashier for our downtown sandwich store on weekends and some evenings. " * 2})
        self.assertEqual(s, 422)

    def test_invalid_json(self):
        r = self.client.post(self.API, data="not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_account_full_report_tips_and_monthly_cap(self):
        user = get_user_model().objects.create_user("u", "u@x.test", "pw12345!")
        self.client.force_login(user)
        fake = mock.MagicMock()
        fake.chat.completions.create.return_value.choices = [
            mock.MagicMock(message=mock.MagicMock(content=json.dumps({"tips": ["a", "b", "c"]})))
        ]
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test"}), \
             mock.patch("tools.views.OpenAI", return_value=fake):
            s, d = self.post(self.client, {"resume_text": RESUME, "job_id": self.job.id})
        self.assertEqual(s, 200)
        self.assertEqual(d["tips"], ["a", "b", "c"])
        self.assertEqual(d["runs_left"], 4)
        self.assertIn(("Marketo", "Marketo Engage"), {(f["you_wrote"], f["jd_says"]) for f in d["alias_fixes"]})
        for _ in range(4):
            s, d = self.post(self.client, {"resume_text": RESUME, "job_id": self.job.id})
        self.assertEqual(s, 200)
        s, d = self.post(self.client, {"resume_text": RESUME, "job_id": self.job.id})
        self.assertEqual((s, d.get("gate")), (429, "limit"))

    def test_tips_failure_does_not_break_report(self):
        user = get_user_model().objects.create_user("v", "v@x.test", "pw12345!")
        self.client.force_login(user)
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test"}), \
             mock.patch("tools.views.OpenAI", side_effect=RuntimeError("boom")):
            s, d = self.post(self.client, {"resume_text": RESUME, "job_id": self.job.id})
        self.assertEqual(s, 200)
        self.assertEqual(d["tips"], [])

    def test_inactive_job_is_not_usable(self):
        closed = make_job(title="Closed role", is_active=False, screening_status="rejected")
        s, _ = self.post(self.client, {"resume_text": RESUME, "job_id": closed.id})
        self.assertEqual(s, 400)  # falls back to "paste the job description"

    def test_job_page_has_nofollow_cta(self):
        r = self.client.get(f"/job/{self.job.id}/{self.job.slug}/")
        self.assertContains(r, "Check my resume")
        self.assertContains(r, f'?job={self.job.id}" rel="nofollow"')

    # --- Tracking: GA4 events (via GTM dataLayer) + Founder HQ "who" log ---
    def test_job_page_tracks_check_resume_clicks(self):
        r = self.client.get(f"/job/{self.job.id}/{self.job.slug}/")
        self.assertContains(r, "window.mtjTrack")          # helper in base.html
        self.assertContains(r, "check_resume_click")
        self.assertContains(r, 'data-placement="top"')
        self.assertContains(r, 'data-placement="bottom"')  # top + bottom CTAs

    def test_posthog_off_without_key(self):
        with self.settings(POSTHOG_KEY=""):
            r = self.client.get(f"/job/{self.job.id}/{self.job.slug}/")
        self.assertNotContains(r, "posthog.init")

    def test_posthog_loads_and_identifies_signed_in_user(self):
        from django.contrib.auth.models import User
        u = User.objects.create_user("ph", "ph@example.com", "pw12345!x")
        with self.settings(POSTHOG_KEY="phc_test123"):
            r = self.client.get(f"/job/{self.job.id}/{self.job.slug}/")
            self.assertContains(r, 'posthog.init("phc_test123"')
            self.assertNotContains(r, "posthog.identify")   # anonymous
            self.client.force_login(u)
            r = self.client.get(f"/job/{self.job.id}/{self.job.slug}/")
            self.assertContains(r, "ph@example.com")
            self.assertContains(r, "posthog.identify")
            u.is_staff = True; u.save()
            r = self.client.get(f"/job/{self.job.id}/{self.job.slug}/")
            self.assertNotContains(r, "posthog.init")       # founder excluded

    def test_tool_page_tracks_funnel_events(self):
        r = self.client.get(f"/tools/resume-keyword-scanner/?job={self.job.id}")
        for event in ["ats_check_submit", "ats_check_result", "ats_gate_shown", "ats_signup_click"]:
            self.assertContains(r, event)

    def test_checks_are_logged_without_resume_text(self):
        from jobs.models import AtsCheck
        self.post(self.client, {"resume_text": RESUME, "job_id": self.job.id})
        anon = AtsCheck.objects.get()
        self.assertIsNone(anon.user)
        self.assertEqual((anon.job_id, anon.matched, anon.required, anon.source), (self.job.id, 4, 8, "job"))
        # No field anywhere on the log can hold resume text.
        self.assertFalse(any(f.name in ("resume", "resume_text", "text", "ip") for f in AtsCheck._meta.fields))

        user = get_user_model().objects.create_user("w", "w@x.test", "pw12345!")
        c = self.client_class(); c.force_login(user)
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": ""}):
            self.post(c, {"resume_text": RESUME, "jd_text": JD_HTML})
        logged = AtsCheck.objects.filter(user=user).get()
        self.assertEqual((logged.job_id, logged.source), (None, "pasted"))

    def test_founder_hq_shows_resume_checker_activity(self):
        from jobs.models import AtsCheck
        checker = get_user_model().objects.create_user("c", "checker@x.test", "pw12345!")
        AtsCheck.objects.create(user=checker, job=self.job, matched=3, required=8)
        AtsCheck.objects.create(user=None, job=self.job, matched=5, required=8)
        admin = get_user_model().objects.create_user("a", "a@x.test", "pw12345!", is_staff=True)
        self.client.force_login(admin)
        r = self.client.get("/staff/")
        self.assertContains(r, "Resume checker activity")
        self.assertContains(r, "checker@x.test")
        self.assertContains(r, "3 / 8")
        self.assertContains(r, "anonymous")


# ---------------------------------------------------------------------------
# Page smoke tests — every major page must render
# ---------------------------------------------------------------------------
@override_settings(**TEST_SETTINGS)
class PageSmokeTests(TestCase):
    def setUp(self):
        cache.clear()
        cat = Category.objects.create(name="MarTech", slug="martech")
        self.tool = Tool.objects.create(name="Marketo", slug="marketo", category=cat)
        self.job = make_job()
        self.job.tools.add(self.tool)
        BlogPost.objects.create(title="AI in MOps", slug="ai-in-mops", excerpt="x",
                                content="<p>Body</p>", category="AI in MarTech", is_published=True)

    def assert_ok(self, url, status=200):
        r = self.client.get(url)
        self.assertEqual(r.status_code, status, f"{url} returned {r.status_code}")
        return r

    def test_core_pages(self):
        for url in [
            "/", "/jobs/", f"/job/{self.job.id}/{self.job.slug}/", "/jobs/marketo/",
            "/blog/", "/blog/ai-in-mops/", "/blog/ai-in-martech/", "/blog/salary-guides/",
            "/salary-guide/", "/martech-job-market-statistics/", "/companies/",
            "/category/engineering/", "/category/operations/", "/category/data/",
            "/category/ai-automation/", "/remote/jobs/", "/about/", "/for-employers/",
            "/marketing-operations-manager-jobs/",
        ]:
            with self.subTest(url=url):
                self.assert_ok(url)

    def test_tools_pages(self):
        for url in [
            "/tools/", "/tools/resume-keyword-scanner/", "/tools/job-description-generator/",
            "/tools/salary-calculator/", "/tools/interview-questions-generator/",
            "/tools/utm-link-builder/", "/tools/email-subject-line-tester/",
        ]:
            with self.subTest(url=url):
                self.assert_ok(url)

    def test_seo_files(self):
        for url in ["/robots.txt", "/llms.txt", "/sitemap.xml", "/blog/feed/"]:
            with self.subTest(url=url):
                self.assert_ok(url)

    def test_closed_job_returns_410(self):
        closed = make_job(title="Old role", is_active=False, screening_status="rejected")
        self.assert_ok(f"/job/{closed.id}/{closed.slug}/", status=410)
        self.assert_ok("/job/999999/nope/", status=410)

    def test_mixed_case_seo_url_redirects_to_lowercase(self):
        r = self.client.get("/Chicago/Marketo-jobs/")
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r["Location"], "/chicago/marketo-jobs/")


# ---------------------------------------------------------------------------
# Security & past-bug regressions
# ---------------------------------------------------------------------------
@override_settings(**TEST_SETTINGS)
class SecurityRegressionTests(TestCase):
    def test_staff_pages_require_staff(self):
        # Regression: /staff/review/ once lost its staff guard in a merge.
        for url in ["/staff/", "/staff/review/"]:
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 302, f"{url} must redirect anonymous users")
        user = get_user_model().objects.create_user("n", "n@x.test", "pw12345!")
        self.client.force_login(user)
        for url in ["/staff/", "/staff/review/"]:
            with self.subTest(url=url, as_="non-staff"):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_staff_can_open_founder_hq(self):
        admin = get_user_model().objects.create_user("s", "s@x.test", "pw12345!", is_staff=True)
        self.client.force_login(admin)
        self.assertEqual(self.client.get("/staff/").status_code, 200)

    def test_unsubscribe_is_soft_delete(self):
        from django.core import signing
        Subscriber.objects.create(email="a@x.test")
        token = signing.dumps("a@x.test", salt="unsubscribe")
        self.client.post(f"/u/{token}/")
        sub = Subscriber.objects.get(email="a@x.test")
        self.assertFalse(sub.is_active)            # row kept as suppression record

    def test_digest_recipients_include_accounts_and_exclude_unsubscribed(self):
        from jobs.emails import get_digest_recipients
        Subscriber.objects.create(email="sub@x.test")
        Subscriber.objects.create(email="gone@x.test", is_active=False)
        get_user_model().objects.create_user("acct", "acct@x.test", "pw12345!")
        get_user_model().objects.create_user("gone", "gone@x.test", "pw12345!")
        recipients = set(get_digest_recipients())
        self.assertIn("sub@x.test", recipients)
        self.assertIn("acct@x.test", recipients)
        self.assertNotIn("gone@x.test", recipients)

    def test_email_defaults_never_fall_back_to_gmail(self):
        from django.conf import settings
        self.assertNotIn("gmail", settings.EMAIL_HOST)

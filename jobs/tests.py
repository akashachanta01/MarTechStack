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

    def test_job_page_tracks_apply_and_save(self):
        r = self.client.get(f"/job/{self.job.id}/{self.job.slug}/")
        self.assertContains(r, "apply_click")
        self.assertContains(r, 'js-apply" data-placement="top"')
        self.assertContains(r, 'js-apply" data-placement="bottom"')
        self.assertContains(r, "job_saved")
        self.assertContains(r, 'window.mtjPageType = "job_detail"')

    def test_search_is_tracked_only_when_searching(self):
        r = self.client.get("/jobs/?q=Marketo")
        self.assertContains(r, "window.mtjTrack('job_search'")
        self.assertContains(r, 'query: "marketo"')
        r = self.client.get("/jobs/")
        self.assertNotContains(r, "window.mtjTrack('job_search'")

    def test_signup_completed_fires_once(self):
        from django.contrib.auth.models import User
        u = User.objects.create_user("sg", "sg@example.com", "pw12345!x")
        self.client.force_login(u)
        session = self.client.session
        session["mtj_signed_up"] = "google"; session.save()
        r = self.client.get("/")
        self.assertContains(r, "window.mtjTrack('signup_completed', { method: \"google\" })")
        r = self.client.get("/")
        self.assertNotContains(r, "signup_completed")

    def test_subscribe_success_is_tracked(self):
        r = self.client.get("/")
        self.assertContains(r, "window.mtjTrack('newsletter_subscribe'")
        self.assertContains(r, "window.mtjTrack('signup_click'")

    def test_email_links_get_utm_tags_but_unsubscribe_does_not(self):
        from jobs.emails import _add_utm
        html = ('<a href="https://martechjobs.io/job/1/x/">a</a>'
                '<a href="https://martechjobs.io/jobs/?q=Marketo#top">b</a>'
                '<a href="https://martechjobs.io/u/abc/">c</a>'
                '<a href="https://other.com/">d</a>')
        out = _add_utm(html, "daily_digest")
        self.assertIn('/job/1/x/?utm_source=email&amp;utm_medium=email&amp;utm_campaign=daily_digest"', out)
        self.assertIn('?q=Marketo&amp;utm_source=email&amp;utm_medium=email&amp;utm_campaign=daily_digest#top"', out)
        self.assertIn('href="https://martechjobs.io/u/abc/"', out)
        self.assertIn('href="https://other.com/"', out)

    def test_recruiter_funnel_is_tracked(self):
        r = self.client.get("/post-job/")
        self.assertContains(r, "post_job_start")
        self.assertContains(r, "post_job_submit")
        r = self.client.get("/post-job/success/?plan=free")
        self.assertContains(r, "window.mtjTrack('post_job_completed', { plan: \"free\" })")

    def test_sitewide_click_tracking_present(self):
        r = self.client.get("/")
        for ev in ["employer_cta_click", "content_to_jobs_click", "tool_used"]:
            self.assertContains(r, ev)

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


# ---------------------------------------------------------------------------
# Resume Match phase 1: saved resume, upload, ranking, more matches
# ---------------------------------------------------------------------------
def _docx_upload(lines, name="resume.docx"):
    import io
    import docx
    from django.core.files.uploadedfile import SimpleUploadedFile
    d = docx.Document()
    for l in lines:
        d.add_paragraph(l)
    buf = io.BytesIO(); d.save(buf)
    return SimpleUploadedFile(name, buf.getvalue(),
                              content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@override_settings(**TEST_SETTINGS)
class ResumeMatchTests(TestCase):
    UPLOAD = "/tools/api/resume/upload/"
    API = "/tools/api/ats-match/"

    def setUp(self):
        cache.clear()
        self.job = make_job()
        make_job(title="Marketo Administrator", company="Globex")
        make_job(title="Lifecycle Manager", company="Initech",
                 description="<p>Own Braze and Iterable programs. SQL and Looker reporting required.</p>")
        self.user = get_user_model().objects.create_user("rm", "rm@x.test", "pw12345!")

    def test_parse_docx_and_reject_bad_files(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from jobs.resume_match import extract_resume_text, ResumeParseError
        text = extract_resume_text(_docx_upload(RESUME.splitlines()))
        self.assertIn("Marketo", text)
        with self.assertRaises(ResumeParseError):
            extract_resume_text(SimpleUploadedFile("cv.txt", b"hello" * 100))
        with self.assertRaises(ResumeParseError):
            extract_resume_text(_docx_upload(["Too short"]))

    def test_anonymous_upload_returns_text_and_saves_nothing(self):
        from accounts.models import UserResume
        r = self.client.post(self.UPLOAD, {"resume": _docx_upload(RESUME.splitlines())})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["saved"])
        self.assertIn("Marketo", r.json()["text"])
        self.assertEqual(UserResume.objects.count(), 0)

    def test_member_upload_saves_text_then_checks_use_it(self):
        from accounts.models import UserResume
        self.client.force_login(self.user)
        r = self.client.post(self.UPLOAD, {"resume": _docx_upload(RESUME.splitlines())})
        self.assertTrue(r.json()["saved"])
        saved = UserResume.objects.get(user=self.user)
        self.assertIn("Marketo", saved.text)
        self.assertEqual(saved.filename, "resume.docx")
        # No resume in the request: the saved one is used.
        r = self.client.post(self.API, data=json.dumps({"job_id": self.job.id}), content_type="application/json")
        d = r.json()
        self.assertEqual(r.status_code, 200)
        self.assertEqual((d["matched_count"], d["required_count"]), (4, 8))
        self.assertTrue(d["resume_saved"])
        self.assertIn(d["label"], ("strong", "good", "stretch"))
        # Missing skills carry real demand % and are sorted most-requested first.
        pcts = [m["demand_pct"] for m in d["missing"]]
        self.assertEqual(pcts, sorted(pcts, reverse=True))
        self.assertTrue(all(0 <= p <= 100 for p in pcts))
        # More matches exclude the current job and include the others.
        ids = [j["id"] for j in d["more_matches"]]
        self.assertNotIn(self.job.id, ids)
        self.assertTrue(ids)

    def test_pasted_resume_saved_only_when_asked(self):
        from accounts.models import UserResume
        self.client.force_login(self.user)
        self.client.post(self.API, data=json.dumps({"resume_text": RESUME, "job_id": self.job.id}), content_type="application/json")
        self.assertFalse(UserResume.objects.filter(user=self.user).exists())
        self.client.post(self.API, data=json.dumps({"resume_text": RESUME, "job_id": self.job.id, "save": True}), content_type="application/json")
        self.assertTrue(UserResume.objects.filter(user=self.user).exists())

    def test_delete_resume(self):
        from accounts.models import UserResume
        UserResume.objects.create(user=self.user, text=RESUME, filename="cv.pdf")
        self.assertEqual(self.client.post("/tools/api/resume/delete/").status_code, 401)
        self.client.force_login(self.user)
        r = self.client.get("/accounts/settings/")
        self.assertContains(r, "cv.pdf")
        self.assertContains(r, "Delete resume")
        self.assertEqual(self.client.post("/tools/api/resume/delete/").status_code, 200)
        self.assertFalse(UserResume.objects.filter(user=self.user).exists())

    def test_page_shows_real_stats_and_saved_state(self):
        from accounts.models import UserResume
        r = self.client.get("/tools/resume-keyword-scanner/")
        self.assertContains(r, "3</b> live MarTech jobs")
        self.assertContains(r, "3</b> companies hiring")
        UserResume.objects.create(user=self.user, text=RESUME, filename="cv.pdf")
        self.client.force_login(self.user)
        r = self.client.get(f"/tools/resume-keyword-scanner/?job={self.job.id}")
        self.assertContains(r, "Using your saved resume")
        self.assertContains(r, "cv.pdf")

    def test_nav_links_resume_scanner_and_privacy_mentions_resume(self):
        r = self.client.get("/")
        self.assertContains(r, 'href="/tools/resume-keyword-scanner/" class="tools-link"')
        self.assertContains(self.client.get("/privacy/"), "never the file")


@override_settings(**TEST_SETTINGS)
class ResumeMatchColdStartTests(TestCase):
    """Regression: on prod the first check analysed every live job inside the
    request and hit the 30s worker timeout -> 'Something went wrong' forever."""

    def setUp(self):
        cache.clear()
        self.job = make_job()
        for i in range(5):
            make_job(title=f"Ops role {i}", company=f"Co{i}")

    def test_check_succeeds_without_waiting_when_demand_not_ready(self):
        with mock.patch("jobs.resume_match.term_demand", return_value=({}, 0)):
            r = self.client.post("/tools/api/ats-match/", data=json.dumps({"resume_text": RESUME, "job_id": self.job.id}),
                                 content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(all(m["demand_pct"] is None for m in r.json()["missing"]))

    def test_budget_limits_work_and_progress_persists(self):
        from jobs.resume_match import job_requirements
        reqs, complete = job_requirements(budget_s=-1)   # no time: nothing computed
        self.assertFalse(complete)
        reqs, complete = job_requirements(budget_s=None)  # cron path: everything
        self.assertTrue(complete)
        self.assertEqual(len(reqs), 6)

    def test_ranking_failure_never_breaks_a_check(self):
        with mock.patch("jobs.resume_match.rank_missing", side_effect=RuntimeError("boom")):
            r = self.client.post("/tools/api/ats-match/", data=json.dumps({"resume_text": RESUME, "job_id": self.job.id}),
                                 content_type="application/json")
        self.assertEqual(r.status_code, 200)

    def test_warm_command_fills_demand(self):
        from django.core.management import call_command
        from jobs.resume_match import term_demand
        call_command("warm_resume_match")
        demand, n = term_demand(budget_s=-1)  # must be served from the warm cache
        self.assertEqual(n, 6)
        self.assertEqual(demand.get("Marketo"), 100)


@override_settings(**TEST_SETTINGS)
class ResultsPageImprovementTests(TestCase):
    JD = ("About the role. You will own Adobe Journey Optimizer programs end to end.\n"
          "• Hands-on experience with Adobe Experience Platform and a customer data platform.\n"
          "• Marketo Certified Expert is a plus.")

    def setUp(self):
        cache.clear()

    def test_missing_items_quote_the_job_and_split_required_vs_nice_to_have(self):
        from jobs.resume_match import annotate_missing
        r = match("Administered office schedules and vendor contracts for a 40-person team.", self.JD)
        by = {m["term"]: m for m in annotate_missing(r["missing"], self.JD)}
        self.assertFalse(by["Marketo Certified Expert"]["required"])
        self.assertTrue(by["Adobe Journey Optimizer"]["required"])
        self.assertIn("Adobe Journey Optimizer", by["Adobe Journey Optimizer"]["quote"])
        self.assertEqual(by["Customer Data Platform"]["quote_term"].lower(), "customer data platform")

    def test_lines_needing_numbers_picks_real_unquantified_achievements(self):
        from jobs.resume_match import lines_needing_numbers
        picks = lines_needing_numbers("Managed email campaigns for the global team\n"
                                      "Built lead scoring in Marketo lifting conversion 22%\n"
                                      "Partnered with sales on routing rules and reporting\nhello")
        self.assertEqual(picks, ["Managed email campaigns for the global team",
                                 "Partnered with sales on routing rules and reporting"])

    def test_stretch_result_suggests_only_better_fitting_jobs_even_for_anonymous(self):
        hard = make_job(title="Adobe consultant", company="Adobe", description="<p>" + self.JD + "</p>")
        make_job(title="Marketing Operations Manager", company="Acme")      # ~4/8 for RESUME
        make_job(title="Pure Marketo admin", company="Globex",
                 description="<p>Own our Marketo instance, lead scoring and nurture programs.</p>")
        r = self.client.post("/tools/api/ats-match/", data=json.dumps({"resume_text": RESUME, "job_id": hard.id}),
                             content_type="application/json")
        d = r.json()
        self.assertEqual(d["label"], "stretch")
        self.assertTrue(d["more_matches"])
        cur = d["matched_count"] / d["required_count"]
        self.assertTrue(all(j["matched"] / j["required"] > cur for j in d["more_matches"]))
        self.assertNotIn(hard.id, [j["id"] for j in d["more_matches"]])
        self.assertIn("lines_to_quantify", d)
        self.assertTrue(all("quote" in m for m in d["missing"]))


@override_settings(**TEST_SETTINGS)
class JobHtmlBulletsTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_bullets_from_job_html_are_not_merged_into_one_sentence(self):
        job = make_job(description="<p>We are hiring a senior consultant to lead customer journey programs for enterprise clients.</p>"
                                   "<ul><li>Hands-on Adobe Experience Platform experience.</li>"
                                   "<li>Adobe Journey Optimizer ownership.</li><li>Marketo Certified Expert is a plus.</li></ul>")
        d = self.client.post("/tools/api/ats-match/", data=json.dumps({"resume_text": RESUME, "job_id": job.id}),
                             content_type="application/json").json()
        by = {m["term"]: m for m in d["missing"]}
        self.assertTrue(by["Adobe Experience Platform"]["required"])
        self.assertTrue(by["Adobe Journey Optimizer"]["required"])
        self.assertFalse(by["Marketo Certified Expert"]["required"])


class TaxonomyFalsePositiveTests(TestCase):
    def test_customer_journeys_phrase_is_not_a_skill(self):
        self.assertNotIn("Journey Orchestration", extract_terms("Senior Technical Consultant, Customer Journeys", for_jd=True))
        self.assertIn("Journey Orchestration", extract_terms("Build flows in Journey Builder.", for_jd=True))

"""Founder, Nov 21 2026: "don't spend more than $5 on open AI"."""
from decimal import Decimal
from unittest import mock

from django.test import TestCase, override_settings

from jobs import ai_budget
from jobs.models import AIUsage


def _completion(tin=1500, tout=150, content='{"decision": "APPROVE", "score": 90, "reason": "ok", "signals": {}}'):
    c = mock.Mock()
    c.usage.prompt_tokens, c.usage.completion_tokens = tin, tout
    c.choices = [mock.Mock()]
    c.choices[0].message.content = content
    return c


class AIBudgetTests(TestCase):

    def test_cost_uses_model_prices(self):
        self.assertEqual(ai_budget.cost("gpt-4o-mini", 1_000_000, 0), Decimal("0.15"))
        self.assertEqual(ai_budget.cost("gpt-4o-mini", 0, 1_000_000), Decimal("0.60"))
        self.assertEqual(ai_budget.cost("gpt-4o", 1_000_000, 1_000_000), Decimal("12.50"))
        self.assertEqual(ai_budget.cost("some-new-model", 1_000_000, 0), Decimal("2.50"))  # dearer default

    def test_record_adds_up_this_month(self):
        ai_budget.record("gpt-4o-mini", _completion(1_000_000, 0))
        ai_budget.record("gpt-4o-mini", _completion(1_000_000, 0))
        row = AIUsage.objects.get(month=ai_budget._month())
        self.assertEqual(row.calls, 2)
        self.assertEqual(row.input_tokens, 2_000_000)
        self.assertEqual(row.est_cost_usd, Decimal("0.3000"))

    def test_default_budget_is_under_five_dollars(self):
        self.assertLess(ai_budget.budget_usd(), Decimal("5"))

    @override_settings(OPENAI_MONTHLY_BUDGET_USD="1.00")
    def test_blocks_once_budget_reached_and_counts_blocked(self):
        self.assertTrue(ai_budget.allowed())
        AIUsage.objects.update_or_create(month=ai_budget._month(), defaults={"est_cost_usd": Decimal("1.00")})
        self.assertFalse(ai_budget.allowed())
        self.assertEqual(AIUsage.objects.get(month=ai_budget._month()).blocked_calls, 1)

    @override_settings(OPENAI_MONTHLY_BUDGET_USD="1.00")
    def test_new_month_starts_from_zero(self):
        AIUsage.objects.create(month="2020-01", est_cost_usd=Decimal("99"))
        self.assertTrue(ai_budget.allowed())

    def test_fails_closed_if_counter_unreadable(self):
        with mock.patch("jobs.ai_budget._row", side_effect=RuntimeError("db down")):
            self.assertFalse(ai_budget.allowed())


@override_settings(OPENAI_MONTHLY_BUDGET_USD="1.00")
class AIBudgetCallSiteTests(TestCase):
    """Every place that calls OpenAI checks the budget first and records usage after."""

    def _spend_all(self):
        AIUsage.objects.update_or_create(month=ai_budget._month(), defaults={"est_cost_usd": Decimal("1.00")})

    def _screener(self):
        from jobs.screener import MarTechScreener
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}):
            s = MarTechScreener()
        s.client = mock.Mock()
        s.client.chat.completions.create.return_value = _completion()
        return s

    # A generic title + a JD naming two specialist tools: the screener must ask the AI.
    ARGS = ("Marketing Manager", "Acme", "Remote",
            "You will own Marketo and Salesforce Marketing Cloud and our Braze journeys. " * 5,
            "https://acme.com/jobs/1")

    def test_screener_records_usage_when_under_budget(self):
        s = self._screener()
        s.screen(*self.ARGS)
        self.assertEqual(s.client.chat.completions.create.call_count, 1)
        self.assertEqual(AIUsage.objects.get(month=ai_budget._month()).calls, 1)

    def test_screener_holds_job_for_review_when_over_budget(self):
        self._spend_all()
        s = self._screener()
        result = s.screen(*self.ARGS)
        s.client.chat.completions.create.assert_not_called()
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["details"]["stage"], "ai_budget")

    def test_screener_fast_approve_needs_no_budget(self):
        self._spend_all()
        s = self._screener()
        result = s.screen("Marketo Administrator", "Acme", "Remote", "Marketo", "https://acme.com/jobs/2")
        self.assertEqual(result["status"], "approved")
        s.client.chat.completions.create.assert_not_called()

    def test_tailor_refuses_politely_when_over_budget(self):
        from jobs import resume_tailor
        self._spend_all()
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}), \
             mock.patch("openai.OpenAI") as client_cls:
            with self.assertRaises(resume_tailor.TailorError) as err:
                resume_tailor.tailor("Marketo admin resume", "Marketo job", [])
        client_cls.assert_not_called()
        self.assertIn("temporarily unavailable", str(err.exception))

    def test_tailor_records_usage(self):
        from jobs import resume_tailor
        fake = mock.Mock()
        fake.chat.completions.create.return_value = _completion(content='{"summary": "", "changes": []}')
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}), \
             mock.patch("openai.OpenAI", return_value=fake):
            with self.assertRaises(resume_tailor.TailorError):   # no safe changes in this fake answer
                resume_tailor.tailor("Marketo admin resume", "Marketo job", [])
        self.assertEqual(AIUsage.objects.get(month=ai_budget._month()).calls, 1)

    def test_blog_writer_skips_when_over_budget(self):
        from django.core.management import call_command
        self._spend_all()
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}), \
             mock.patch("jobs.management.commands.generate_blog.OpenAI") as client_cls:
            call_command("generate_blog", stdout=mock.Mock())
        client_cls.assert_not_called()

    def test_every_openai_call_site_is_budgeted(self):
        import pathlib
        root = pathlib.Path(__file__).resolve().parent
        for path in root.rglob("*.py"):
            if path.name.startswith("tests"):
                continue
            src = path.read_text()
            n_calls = src.count("chat.completions.create(")
            if n_calls:
                self.assertGreaterEqual(src.count("ai_budget.allowed("), 1, path)
                self.assertGreaterEqual(src.count("ai_budget.record("), n_calls, path)


class AIUsageMigrationTests(TestCase):
    def test_migration_creates_only_the_new_table(self):
        import importlib
        mod = importlib.import_module("jobs.migrations.0036_ai_usage")
        ops = mod.Migration.operations
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0].name, "AIUsage")

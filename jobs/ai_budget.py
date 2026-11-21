"""Monthly cap on OpenAI spend (founder, Nov 21 2026: "don't spend more than $5 on open AI").

Every OpenAI call in the site goes through `allowed()` first and `record()` after.
The estimate uses the token counts OpenAI returns with each answer and OpenAI's list
prices, and stops new calls at OPENAI_MONTHLY_BUDGET_USD (default $4.50, leaving
headroom under $5 for estimation error). When the cap is reached:
  - the job screener holds jobs as "pending" instead of asking the AI,
  - "Tailor my resume" says it is temporarily unavailable,
  - the blog writer and AI page reader skip their run.
The count resets on the 1st of each month (UTC).

If the budget table can't be read or written (database hiccup), we fail CLOSED:
no AI call is made, so a broken counter can never let spending run away."""
import logging
from decimal import Decimal

from django.conf import settings
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger("jobs.ai_budget")

# US$ per 1M tokens (input, output), OpenAI list prices.
PRICES = {
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "gpt-4o": (Decimal("2.50"), Decimal("10.00")),
}
DEFAULT_PRICE = PRICES["gpt-4o"]  # unknown model: assume the dearer price


def _month():
    return timezone.now().strftime("%Y-%m")


def budget_usd():
    return Decimal(str(getattr(settings, "OPENAI_MONTHLY_BUDGET_USD", "4.50")))


def _row():
    from jobs.models import AIUsage
    row, _ = AIUsage.objects.get_or_create(month=_month())
    return row


def spent_usd():
    try:
        return _row().est_cost_usd
    except Exception:
        logger.exception("AI budget: could not read usage")
        return None


def allowed(model="gpt-4o-mini"):
    """True if this month's estimated spend is still under the budget."""
    try:
        row = _row()
    except Exception:
        logger.exception("AI budget: could not read usage, blocking AI call")
        return False
    if row.est_cost_usd >= budget_usd():
        try:
            type(row).objects.filter(pk=row.pk).update(blocked_calls=F("blocked_calls") + 1)
        except Exception:
            pass
        logger.warning("AI budget reached ($%s of $%s this month): skipping %s call",
                       row.est_cost_usd, budget_usd(), model)
        return False
    return True


def cost(model, input_tokens, output_tokens):
    p_in, p_out = PRICES.get(model, DEFAULT_PRICE)
    return (Decimal(input_tokens) * p_in + Decimal(output_tokens) * p_out) / Decimal(1_000_000)


def record(model, completion):
    """Add one finished call's tokens and estimated cost to this month's total."""
    usage = getattr(completion, "usage", None)
    tin = int(getattr(usage, "prompt_tokens", 0) or 0)
    tout = int(getattr(usage, "completion_tokens", 0) or 0)
    try:
        row = _row()
        type(row).objects.filter(pk=row.pk).update(
            calls=F("calls") + 1, input_tokens=F("input_tokens") + tin,
            output_tokens=F("output_tokens") + tout,
            est_cost_usd=F("est_cost_usd") + cost(model, tin, tout))
    except Exception:
        logger.exception("AI budget: could not record usage")

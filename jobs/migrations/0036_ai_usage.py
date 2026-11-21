"""Monthly OpenAI spend counter (jobs/ai_budget.py). Hand-written: only creates the
new table, because prod's migration history lags its real schema and an
auto-generated migration would try to re-apply unrelated old changes."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("jobs", "0035_reenable_rate_limited_workday_boards")]
    operations = [
        migrations.CreateModel(
            name="AIUsage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("month", models.CharField(max_length=7, unique=True)),
                ("calls", models.IntegerField(default=0)),
                ("blocked_calls", models.IntegerField(default=0)),
                ("input_tokens", models.BigIntegerField(default=0)),
                ("output_tokens", models.BigIntegerField(default=0)),
                ("est_cost_usd", models.DecimalField(decimal_places=4, default=0, max_digits=8)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name_plural": "AI usage"},
        ),
    ]

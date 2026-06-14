"""
Measure the MarTechScreener against a labeled eval set so we can tune for
precision/recall instead of guessing.

  python manage.py score_screener            # full run (calls GPT)
  python manage.py score_screener --no-ai    # free: only the deterministic
                                             # stages (blocklist + quick_kill + title gate)

Labels: "martech" = a genuine MarTech/Ops/RevOps/engineering/analytics role we
WANT; "reject" = noise we don't. Add real failing examples here as you find them
to lock in regressions.
"""

from django.core.management.base import BaseCommand

from jobs.screener import MarTechScreener

# (title, company, label)  — keep descriptions minimal; the title gate + prompt
# are what we're testing. Expand this set with real misclassifications over time.
EVAL_SET = [
    # --- should KEEP (in scope: Marketing Ops + Automation + Campaign Ops, Eng, Data) ---
    ("Marketing Operations Manager", "Acme SaaS", "martech"),
    ("Senior Marketing Ops Specialist", "Acme SaaS", "martech"),
    ("Salesforce Administrator", "Acme SaaS", "martech"),
    ("Marketo Specialist", "Acme SaaS", "martech"),
    ("HubSpot Developer", "Acme SaaS", "martech"),
    ("Marketing Automation Manager", "Acme SaaS", "martech"),
    ("Campaign Operations Manager", "Acme SaaS", "martech"),
    ("Marketing Analytics Manager", "Acme SaaS", "martech"),
    ("Marketing Technologist", "Acme SaaS", "martech"),
    ("MarTech Engineer", "Acme SaaS", "martech"),
    ("CDP Engineer", "Acme SaaS", "martech"),
    ("Salesforce Marketing Cloud Developer", "Acme SaaS", "martech"),
    ("Analytics Engineer", "Acme SaaS", "martech"),
    ("Web Analyst", "Acme SaaS", "martech"),
    ("Tag Management Specialist", "Acme SaaS", "martech"),
    # --- should REJECT: explicitly out-of-scope marketing-adjacent roles ---
    ("Revenue Operations Manager", "Acme SaaS", "reject"),
    ("RevOps Analyst", "Acme SaaS", "reject"),
    ("Lifecycle Marketing Manager", "Acme SaaS", "reject"),
    ("CRM Marketing Manager", "Acme SaaS", "reject"),
    ("Demand Generation Manager", "Acme SaaS", "reject"),
    ("Email Marketing Manager", "Acme SaaS", "reject"),
    ("Growth Marketing Manager", "Acme SaaS", "reject"),
    # --- should REJECT (noise) ---
    ("Senior Software Engineer", "Acme SaaS", "reject"),
    ("Backend Engineer", "Acme SaaS", "reject"),
    ("Graphic Designer", "Acme SaaS", "reject"),
    ("Content Writer", "Acme SaaS", "reject"),
    ("Social Media Manager", "Acme SaaS", "reject"),
    ("SEO Specialist", "Acme SaaS", "reject"),
    ("Brand Manager", "Acme SaaS", "reject"),
    ("Account Executive", "Acme SaaS", "reject"),
    ("Customer Success Manager", "Acme SaaS", "reject"),
    ("Sales Development Representative", "Acme SaaS", "reject"),
    ("Technical Recruiter", "Acme SaaS", "reject"),
    ("Product Manager", "Acme SaaS", "reject"),
    ("Events Coordinator", "Acme SaaS", "reject"),
    ("Paid Media Buyer", "Acme SaaS", "reject"),
    # --- tool-name-but-wrong-role (vendor traps) ---
    ("Salesforce Account Executive", "Salesforce", "reject"),
    ("Adobe Photoshop Designer", "Adobe", "reject"),
    ("HubSpot Sales Representative", "HubSpot", "reject"),
    # --- generic title, in-scope JD (description-signal gate) -------------
    # 4-tuples carry an explicit description so we exercise the desc_signal
    # fallback (title alone would fail the gate).
    ("Technical Consultant", "Acme SaaS",
     "Own our Marketo instance and Tealium tag management. Build campaign "
     "automation, lead routing, and analytics dashboards across the marketing stack.",
     "martech"),
    ("Senior Analyst", "Acme SaaS",
     "Implement and maintain Adobe Experience Platform and Google Tag Manager "
     "data collection for the marketing team; build attribution reporting.",
     "martech"),
    # generic title whose JD only name-drops one ubiquitous tool in passing -> reject
    ("Marketing Manager", "Acme SaaS",
     "Lead brand campaigns and PR. Manage agencies and events. We use Salesforce.",
     "reject"),
]


class Command(BaseCommand):
    help = "Score the screener against a labeled eval set (precision/recall)"

    def add_arguments(self, parser):
        parser.add_argument("--no-ai", action="store_true", help="Only deterministic stages (no GPT calls)")

    def _deterministic_verdict(self, s, title, company, description=""):
        if s._is_blocked(title, company, ""):
            return "rejected"
        if s._quick_kill(title, company):
            return "rejected"
        has_title = any(kw in s._normalize(title) for kw in s.gate_terms)
        desc_norm = s._normalize(description)
        desc_signal = len({t for t in s.desc_signal_tools if t in desc_norm}) >= 2
        if not has_title and not desc_signal:
            return "rejected"
        return "kept"  # would go to GPT — treated as kept in --no-ai mode

    def handle(self, *args, **options):
        s = MarTechScreener()
        no_ai = options["no_ai"]
        self.stdout.write(f"Scoring {len(EVAL_SET)} examples ({'deterministic only' if no_ai else 'full + GPT'})...\n")

        # Confusion counts (positive class = 'martech' = kept)
        tp = fp = tn = fn = 0
        errors = []
        for row in EVAL_SET:
            if len(row) == 4:
                title, company, description, label = row
            else:
                title, company, label = row
                description = f"{title} role at {company}."
            if no_ai:
                verdict = self._deterministic_verdict(s, title, company, description)
                kept = verdict != "rejected"
            else:
                res = s.screen(title, company, "", description, "")
                kept = res.get("status") != "rejected"

            if label == "martech" and kept:
                tp += 1
            elif label == "martech" and not kept:
                fn += 1; errors.append(f"  ❌ DROPPED a MarTech role: {title}")
            elif label == "reject" and not kept:
                tn += 1
            else:  # reject but kept
                fp += 1; errors.append(f"  ⚠️ KEPT noise: {title} @ {company}")

        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        acc = (tp + tn) / len(EVAL_SET)

        self.stdout.write(f"Precision (kept that are MarTech): {precision:.0%}")
        self.stdout.write(f"Recall (MarTech that we keep):     {recall:.0%}")
        self.stdout.write(f"Accuracy:                          {acc:.0%}")
        self.stdout.write(f"TP={tp} FP={fp} TN={tn} FN={fn}\n")
        if errors:
            self.stdout.write("Misclassifications:")
            for e in errors:
                self.stdout.write(e)
        else:
            self.stdout.write(self.style.SUCCESS("✅ No misclassifications."))

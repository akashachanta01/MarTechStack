"""Add a 'MarTech job title taxonomy' table to the job-titles guide.

Search Console (Sept 18 - Oct 16 2026): the guide ranks around position 8-9 for a
cluster of taxonomy searches with zero clicks — 'marketing roles job taxonomy
categories' (133 impressions), 'marketing leadership job title taxonomy' (56),
'job title taxonomy for tech roles in ecommerce' (47). The page has no plain
taxonomy table answering them. Idempotent; inserted after the classification box
added in 0025 (or after the hero figure if that box is missing)."""
from django.db import migrations

SLUG = "martech-job-titles-career-paths"
MARKER = 'id="martech-title-taxonomy"'
ROWS = [
    ("Marketing Operations", "Marketing Operations Specialist, Marketing Operations Manager, Director of Marketing Operations, VP Marketing Operations"),
    ("Marketing Automation", "Marketing Automation Specialist, Marketo / HubSpot / Pardot Administrator, Marketing Automation Manager"),
    ("Marketing Technology (MarTech)", "Marketing Technologist, Marketing Technology Analyst, MarTech Manager, Director of Marketing Technology and Systems"),
    ("CRM & Lifecycle", "CRM Specialist, Lifecycle Marketing Manager, Email Marketing Manager, Salesforce Marketing Cloud / Braze Developer"),
    ("Marketing Analytics & Data", "Marketing Analyst, Marketing Analytics Manager, Digital Analytics / Web Analytics Lead, CDP Specialist"),
    ("Campaign & Demand Operations", "Campaign Operations Manager, Demand Generation Manager, Revenue / Growth Operations"),
]
LEVELS = "Specialist / Analyst &rarr; Senior &rarr; Manager / Lead &rarr; Senior Manager &rarr; Director / Head of &rarr; VP &rarr; CMO or CRO"


def _box():
    rows = "".join(f"<tr><td>{fam}</td><td>{titles}</td></tr>" for fam, titles in ROWS)
    return (
        f'<section {MARKER} class="title-classify">'
        "<h2>MarTech job title taxonomy</h2>"
        "<p>Most companies file these roles under the Marketing department, in one of six job families:</p>"
        "<table><thead><tr><th>Job family</th><th>Typical titles</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
        f"<p><strong>Seniority levels (same in every family):</strong> {LEVELS}.</p>"
        "<p>In ecommerce and tech companies the same families appear, with CRM &amp; Lifecycle and "
        "Marketing Analytics usually the largest. Browse live roles by title: "
        '<a href="/marketing-operations-manager-jobs/">marketing operations</a>, '
        '<a href="/marketing-automation-specialist-jobs/">marketing automation</a>, '
        '<a href="/marketing-technology-analyst-jobs/">marketing technology analyst</a>.</p>'
        "</section>"
    )


def forwards(apps, schema_editor):
    BlogPost = apps.get_model("jobs", "BlogPost")
    post = BlogPost.objects.filter(slug=SLUG).first()
    if not post or MARKER in (post.content or ""):
        return
    c = post.content or ""
    anchor = c.find('id="classify-director-martech"')
    if anchor != -1:
        i = c.find("</section>", anchor) + len("</section>")
    else:
        i = c.find("</figure>")
        i = i + len("</figure>") if i != -1 else 0
    post.content = c[:i] + _box() + c[i:]
    post.save(update_fields=["content"])


class Migration(migrations.Migration):
    dependencies = [("jobs", "0025_job_titles_classification_answer")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]

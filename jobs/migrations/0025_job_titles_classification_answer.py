"""Add a short, direct answer box to the job-titles guide.

Search Console (Sept 12 - Oct 9 2026): Google showed this guide ~3,700 times
for 'director of marketing technology and systems seniority level' and
'how to classify department for director of marketing technology and systems'
(position 8-10) with zero clicks — the page never answered that question
directly. Idempotent: skipped if the box is already there."""
from django.db import migrations

SLUG = "martech-job-titles-career-paths"
MARKER = 'id="classify-director-martech"'
BOX = (
    '<section ' + MARKER + ' class="title-classify">'
    '<h2>How to classify "Director of Marketing Technology and Systems"</h2>'
    '<table><thead><tr><th>Field</th><th>Classification</th></tr></thead><tbody>'
    '<tr><td>Department</td><td>Marketing, in the Marketing Operations / Marketing Technology function '
    '(some companies place it under Revenue Operations or IT, but the budget and goals sit with Marketing)</td></tr>'
    '<tr><td>Seniority level</td><td>Director: senior leadership, above Senior Manager and below VP. '
    'Usually reports to the VP of Marketing, VP Marketing Operations or CMO</td></tr>'
    '<tr><td>Job family</td><td>Marketing Operations &amp; Technology (MarTech)</td></tr>'
    '<tr><td>What the role owns</td><td>The marketing tech stack and its systems: marketing automation, CRM integration, '
    'customer data, analytics tooling, vendor selection and the team that runs them</td></tr>'
    '</tbody></table>'
    '<p>The same logic applies to related titles: "Head of Marketing Technology" is usually Director level, '
    '"Marketing Technology Manager" is Manager level, and "VP, Marketing Technology" is VP level, all in the '
    'Marketing Operations &amp; Technology family. See live '
    '<a href="/marketing-technologist-jobs/">marketing technologist jobs</a> and '
    '<a href="/marketing-operations-manager-jobs/">marketing operations manager jobs</a>.</p>'
    '</section>'
)


def forwards(apps, schema_editor):
    BlogPost = apps.get_model("jobs", "BlogPost")
    post = BlogPost.objects.filter(slug=SLUG).first()
    if not post or MARKER in (post.content or ""):
        return
    c = post.content or ""
    i = c.find("</figure>")
    i = i + len("</figure>") if i != -1 else 0
    post.content = c[:i] + BOX + c[i:]
    post.save(update_fields=["content"])


class Migration(migrations.Migration):
    dependencies = [("jobs", "0024_blog_meta_ctr")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]

"""Blog post: MarTech surveys vs. live job postings (Nov 2026).

Original analysis: pairs a few headline findings from MarTech.org's 2025 State of Your
Stack and 2025 Replacement Survey (briefly cited, credited and linked) with our own
counts from live job postings on Nov 1 2026. Idempotent: skipped if the slug exists."""
from datetime import date

from django.db import migrations

SLUG = "martech-surveys-vs-job-postings-2026"
TITLE = "MarTech Surveys vs. Real Job Postings: What Employers Are Actually Hiring For"
META_TITLE = "MarTech Surveys vs. 477 Real Job Postings (Nov 2026)"
META_DESC = ("Surveys say teams swap fewer tools and struggle with data integration. We checked 477 live "
             "MarTech job postings to see what employers really hire for.")
EXCERPT = ("Industry surveys tell you what marketing teams say about their stack. Job postings tell you "
           "what they pay people to run. We compared the two using 477 live MarTech roles.")

CONTENT = """
<p>Every year the big MarTech surveys tell us what marketing teams <em>say</em> about their technology stack: what they use, what they replace and what keeps them up at night. Job postings show something different: what companies are actually willing to pay people to run.</p>

<p>We compared two recent surveys from MarTech.org with the 477 live MarTech and Marketing Ops jobs on MarTechJobs.io on November 1, 2026. The surveys and the hiring data mostly agree, but there are a couple of gaps worth knowing about if you're planning your next career move.</p>

<p><strong>Where our numbers come from:</strong> every job on MarTechJobs.io is pulled directly from a company's own hiring system and removed once it closes. The percentages below are the share of those 477 live postings that name a platform or skill. A posting can name several, so shares add up to more than 100%. You can see the full, daily-updated breakdown in our <a href="/martech-job-market-statistics/">MarTech Hiring Report</a>.</p>

<h2>1. Teams are swapping marketing automation platforms less. Employers still hire for the big suites.</h2>

<p>MarTech.org's <a href="https://martech.org/is-the-era-of-rip-and-replace-over-for-martech-stacks/" rel="noopener" target="_blank">2025 Replacement Survey</a> found that marketing automation replacements dropped sharply: from 31.1% of replacements in 2024 to 19.4% in 2025. In other words, teams are keeping the platform they have and trying to get more out of it.</p>

<p>The hiring data points the same way, and shows which platforms that "getting more out of it" work is happening on:</p>

<table>
<thead><tr><th>Platform named in the job posting</th><th>Share of 477 live MarTech jobs</th></tr></thead>
<tbody>
<tr><td><a href="/jobs/salesforce/">Salesforce</a></td><td>53%</td></tr>
<tr><td><a href="/jobs/salesforce-marketing-cloud/">Salesforce Marketing Cloud</a></td><td>27%</td></tr>
<tr><td><a href="/jobs/adobe-experience-platform/">Adobe Experience Platform</a></td><td>17%</td></tr>
<tr><td><a href="/jobs/marketo/">Marketo</a></td><td>11%</td></tr>
<tr><td><a href="/jobs/braze/">Braze</a></td><td>11%</td></tr>
<tr><td><a href="/jobs/hubspot/">HubSpot</a></td><td>8%</td></tr>
</tbody>
</table>

<p>Our read: when companies stop switching platforms, they hire specialists who can go deep on the one they already pay for. Right now that demand is concentrated on the Salesforce and Adobe enterprise suites. If you are a Marketo or HubSpot specialist, adding Salesforce CRM depth is the most common combination employers ask for.</p>

<h2>2. Data integration is the top complaint, and the most common skill in job posts</h2>

<p>In MarTech.org's <a href="https://martech.org/these-are-the-challenges-and-barriers-impacting-your-martech-stack/" rel="noopener" target="_blank">2025 State of Your Stack Survey</a>, run with chiefmartec (Scott Brinker) and MarketingOps.com, 65.7% of respondents named data integration as one of their biggest stack management challenges, more than budget or tool complexity.</p>

<p>Employers are clearly trying to hire their way out of that problem:</p>
<ul>
<li><strong>59%</strong> of live MarTech postings mention integrations, APIs, ETL or data pipelines.</li>
<li><strong>27%</strong> mention a customer data platform (CDP), Data Cloud or real-time customer profiles.</li>
<li><strong>28%</strong> ask for SQL.</li>
</ul>

<p>The same survey listed "lack of skilled resources" as a top challenge for 45% of teams. Put the two together and the career signal is simple: a Marketing Ops person who can connect systems and work with data is solving the problem their manager complains about most.</p>

<h2>3. AI is in the stack, and it's starting to show up in job descriptions</h2>

<p>The State of Your Stack survey found that 68.6% of organizations already use generative AI tools, which put AI among the most common categories in the stack after only a couple of years. The Replacement Survey found that 37.1% of teams now treat AI capabilities as an important factor when choosing a replacement tool.</p>

<p>In hiring, AI is moving from "nice to have" into the job description itself: <strong>39%</strong> of live MarTech postings mention generative AI, large language models, AI agents or Agentforce. Most of these roles are still about running the core platforms well, with AI as one of the tools you're expected to use. Very few are dedicated "AI" jobs: only 20 of the 477 have AI in the job title.</p>

<h2>4. What this means if you're job hunting</h2>
<ul>
<li><strong>Go deep on one enterprise suite.</strong> Salesforce (and Salesforce Marketing Cloud) or Adobe Experience Platform cover most of the demand.</li>
<li><strong>Show you can connect things.</strong> Integrations, APIs, CDPs and SQL appear in more postings than any single platform except Salesforce.</li>
<li><strong>Put AI on your resume the way employers write it:</strong> as something you used to get a result, not as a separate skill list.</li>
<li><strong>Use the job's own words.</strong> Our free <a href="/tools/resume-keyword-scanner/">Resume Scanner</a> checks your resume against a real live job and shows which of its required skills you're missing.</li>
</ul>

<h2>About the sources</h2>
<p>Survey figures are from MarTech.org (Third Door Media, a Semrush company): the 2025 State of Your Stack Survey and the 2025 MarTech Replacement Survey. They're quoted here briefly for comparison, so read the original reports at <a href="https://martech.org/topic/state-of-your-stack-survey/" rel="noopener" target="_blank">martech.org</a> for the full findings and methodology. Job figures are our own counts of live postings on MarTechJobs.io on November 1, 2026, and the current numbers are always in the <a href="/martech-job-market-statistics/">MarTech Hiring Report</a>.</p>
"""


def forwards(apps, schema_editor):
    BlogPost = apps.get_model("jobs", "BlogPost")
    if BlogPost.objects.filter(slug=SLUG).exists():
        return
    BlogPost.objects.create(
        slug=SLUG, title=TITLE, excerpt=EXCERPT, content=CONTENT.strip(),
        meta_title=META_TITLE, meta_description=META_DESC,
        category="Tech Stacks", read_time="5 min read",
        published_at=date(2026, 11, 1), is_published=True,
    )


class Migration(migrations.Migration):
    dependencies = [("jobs", "0030_hiringsnapshot")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]

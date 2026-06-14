from django.core.management.base import BaseCommand
from django.utils.text import slugify

from jobs.models import Tool, Category, InterviewGuide


# ---------------------------------------------------------------------------
# Curated, expert-authored interview content. The page also renders a LIVE data
# spine (open roles, co-required tools, companies) from the job corpus, so the
# combination is original and refreshable. Add tools here over time.
# ---------------------------------------------------------------------------

GUIDES = {
    "HubSpot": {
        "intro": (
            "<p>HubSpot interviews for Marketing Operations and HubSpot Admin roles are "
            "rarely about memorising menus. Hiring managers want to see that you can model "
            "data cleanly, automate without creating chaos, and tie activity back to revenue. "
            "Expect a mix of hands-on platform questions and scenario questions where you "
            "have to reason out loud.</p>"
            "<p>The guide below groups the questions the way a strong interviewer actually "
            "structures them &mdash; fundamentals first, then automation, data, reporting, and "
            "finally judgement-based scenarios. For each one we&rsquo;ve noted what a strong "
            "answer demonstrates, not just a textbook definition.</p>"
        ),
        "meta_title": "HubSpot Interview Questions ({year}) — 18 Real Questions + Answers | MarTechJobs",
        "meta_description": (
            "18 real HubSpot interview questions for Marketing Ops & Admin roles, with what "
            "hiring managers look for in each answer. Built from live HubSpot job data. "
            "Updated {year}."
        ),
        "questions": [
            {"category": "Platform Fundamentals", "items": [
                {"q": "Walk me through the difference between a HubSpot list, a workflow, and a campaign.",
                 "a": "<p>A strong answer separates <strong>segmentation</strong> (lists &mdash; static vs active/dynamic), <strong>automation</strong> (workflows that act on records), and <strong>measurement/attribution</strong> (campaigns that group assets to report on influence). Bonus points for noting that active lists re-evaluate membership continuously while static lists are a snapshot, and for knowing when each is the right tool.</p>"},
                {"q": "When would you use a static list vs an active list?",
                 "a": "<p>Use a <strong>static list</strong> for a one-time snapshot (e.g. an event export, a suppression set you don't want changing). Use an <strong>active list</strong> when membership should update automatically as contacts meet/stop meeting criteria. Good candidates mention performance and the fact that active lists can quietly grow/shrink under reporting if you're not careful.</p>"},
                {"q": "What are HubSpot's standard objects, and how do associations work?",
                 "a": "<p>Contacts, Companies, Deals, Tickets (and custom objects on higher tiers). The signal you're looking for: they understand <strong>associations</strong> (and association labels), the difference between primary company and secondary associations, and why a clean association model matters for reporting and automation.</p>"},
            ]},
            {"category": "Workflows & Automation", "items": [
                {"q": "How do you prevent a contact from being enrolled in the same workflow repeatedly?",
                 "a": "<p>Look for: re-enrollment settings (off by default), enrollment triggers vs criteria, and using <strong>suppression lists</strong> or a 'has been enrolled' property to gate. The best answers talk about designing enrollment so you don't accidentally re-trigger emails on a property edit.</p>"},
                {"q": "Describe how you'd build a lead-nurture workflow that adapts to behaviour.",
                 "a": "<p>Strong candidates describe branching (if/then on email engagement or page views), delays, goal criteria to exit the nurture when the lead converts, and internal notifications/handoffs to sales. They mention measuring with goals and not just 'sending five emails'.</p>"},
                {"q": "A workflow is sending duplicate emails. How do you debug it?",
                 "a": "<p>Check enrollment history on a sample contact, re-enrollment triggers, overlapping workflows acting on the same list, and whether a property update is re-triggering enrollment. The reasoning process matters more than the single 'right' cause.</p>"},
                {"q": "How would you sync HubSpot lifecycle stages with sales activity?",
                 "a": "<p>Look for an understanding that lifecycle stage should move forward (not backward) automatically via workflows, that it should reflect real sales/marketing definitions agreed with the RevOps/sales team, and that deal stages and lifecycle stages are related but distinct.</p>"},
            ]},
            {"category": "Data, Properties & Lifecycle", "items": [
                {"q": "How do you handle data hygiene and deduplication in HubSpot?",
                 "a": "<p>Good answers cover: dedupe by email/record ID, using required properties and validation, standardising picklists, scheduled cleaning workflows, and limiting free-text fields. Mentioning the trade-off between strict validation and form conversion is a senior signal.</p>"},
                {"q": "What's the difference between a contact property and a company property, and when do you roll data up?",
                 "a": "<p>Contact properties live on the person, company properties on the account. Roll-ups matter for account-based reporting. Strong candidates mention that some data (industry, region) belongs at the company level to avoid inconsistency across contacts.</p>"},
                {"q": "How would you design lead scoring in HubSpot?",
                 "a": "<p>Look for: positive and negative attributes, behavioural vs demographic scoring, decay over time, and &mdash; crucially &mdash; validating the model against actual conversion data rather than guessing weights. Bonus for knowing the difference between HubSpot score and a predictive/AI score on higher tiers.</p>"},
            ]},
            {"category": "Reporting & Attribution", "items": [
                {"q": "How do you measure marketing's contribution to pipeline in HubSpot?",
                 "a": "<p>Strong answers reference campaign attribution, multi-touch attribution reports (on Pro/Enterprise), the difference between first-touch and multi-touch, and the need to define what counts as 'influence' with sales. Watch for candidates who only cite vanity metrics.</p>"},
                {"q": "A stakeholder says 'our open rates dropped'. How do you respond?",
                 "a": "<p>The best answers immediately flag Apple Mail Privacy Protection inflating/distorting opens, pivot the conversation to clicks/conversions/replies as more reliable signals, and then investigate deliverability, list quality, and send-time changes.</p>"},
            ]},
            {"category": "Scenario & Judgement", "items": [
                {"q": "You inherit a messy HubSpot portal with 200 workflows. Where do you start?",
                 "a": "<p>Look for a methodical audit: identify active vs unused workflows, map enrollment overlaps, document business-critical automations before changing anything, and prioritise by risk/impact. Senior candidates talk about stakeholder comms and a staging approach rather than ripping things out.</p>"},
                {"q": "Marketing and Sales disagree on what an MQL is. How do you resolve it in HubSpot?",
                 "a": "<p>This is a process question disguised as a tool question. The strong answer: facilitate a shared definition, encode it as scoring + lifecycle criteria, set up a feedback loop (sales marks why leads are rejected), and iterate on the data. The platform is the easy part.</p>"},
                {"q": "How do you roll out a change to a live workflow without breaking things?",
                 "a": "<p>Clone and test, use a small test list, check re-enrollment impact, communicate to stakeholders, and have a rollback plan. Demonstrates operational maturity.</p>"},
            ]},
        ],
        "prep_tips": (
            "<p><strong>Get hands-on first.</strong> Spin up a free HubSpot portal and build a real "
            "nurture workflow, a lifecycle automation, and an attribution report. Interviewers can "
            "tell within two questions whether you've actually used the tool.</p>"
            "<p><strong>Bring a story.</strong> Have one concrete example of an automation or data "
            "model you fixed, with the before/after numbers. Tie everything back to revenue or "
            "efficiency, not activity.</p>"
            "<p><strong>Know the limits.</strong> Knowing what HubSpot <em>can't</em> do cleanly "
            "(or what's gated behind Enterprise) signals real experience.</p>"
        ),
    },
    "Salesforce Marketing Cloud": {
        "intro": (
            "<p>Salesforce Marketing Cloud (SFMC) interviews go deep fast. Because SFMC is really a "
            "collection of studios and builders sitting on a relational data layer, hiring managers "
            "probe whether you understand the architecture &mdash; not just how to drag a box in "
            "Journey Builder. Expect AMPscript, SQL on Data Extensions, and deliverability scenarios.</p>"
            "<p>The questions below are grouped from fundamentals through hands-on technical work to "
            "judgement scenarios. For each, we&rsquo;ve noted what a strong answer demonstrates.</p>"
        ),
        "meta_title": "Salesforce Marketing Cloud Interview Questions ({year}) — SFMC Guide | MarTechJobs",
        "meta_description": (
            "Real Salesforce Marketing Cloud (SFMC) interview questions for Email Specialist & "
            "Developer roles — AMPscript, Journey Builder, Data Extensions & SQL, with what "
            "interviewers look for. Updated {year}."
        ),
        "questions": [
            {"category": "Platform & Architecture", "items": [
                {"q": "Explain the main SFMC studios and builders and how they fit together.",
                 "a": "<p>Look for a clear mental model: <strong>Email Studio</strong> (email creation/sending), <strong>Journey Builder</strong> (orchestration), <strong>Automation Studio</strong> (scheduled/triggered backend automation), <strong>Contact Builder</strong> (the data model &mdash; data extensions, contacts, attributes), <strong>Mobile/Advertising/Web studios</strong> for channels. The signal is understanding that the data layer underpins everything.</p>"},
                {"q": "What is a Data Extension, and how does it differ from a List?",
                 "a": "<p>A Data Extension is a <strong>relational table</strong> (typed columns, primary keys, can be related to others); Lists are the older, flat subscriber model. Strong candidates explain why DEs are preferred for scale and segmentation, sendable vs non-sendable DEs, and the role of the Subscriber Key.</p>"},
                {"q": "What is the Subscriber Key and why does it matter?",
                 "a": "<p>It's the unique identifier for a subscriber across the account. Getting this wrong causes duplicate contacts and broken suppression. Senior candidates discuss choosing a stable key (often a CRM ID rather than email) and the consequences of changing it later.</p>"},
            ]},
            {"category": "Email & AMPscript", "items": [
                {"q": "How do you personalise an email beyond a first name?",
                 "a": "<p>Look for AMPscript and dynamic content: <code>%%=Lookup()=%%</code> / <code>LookupRows()</code> to pull related data, conditional blocks, and dynamic content rules. The strongest answers mention falling back gracefully when data is missing and testing with multiple subscriber profiles.</p>"},
                {"q": "What's the difference between AMPscript, SSJS, and GTL?",
                 "a": "<p>AMPscript is the primary inline scripting language for email/landing pages; SSJS (server-side JavaScript) handles more complex logic and API calls; GTL (Guide Template Language) is used for content blocks/handlebars-style templating. Knowing <em>when</em> to reach for SSJS vs AMPscript is the senior signal.</p>"},
                {"q": "How would you build a dynamic product-recommendation block in an email?",
                 "a": "<p>Strong answers: store recommendations in a Data Extension keyed by subscriber, use <code>LookupRows()</code> + a loop in AMPscript to render them, and handle the empty case. Bonus for mentioning Einstein recommendations as an alternative and the trade-offs.</p>"},
            ]},
            {"category": "Data & SQL", "items": [
                {"q": "Write the logic for a SQL query that finds subscribers who opened but didn't click in the last 30 days.",
                 "a": "<p>You're looking for comfort with SFMC's <strong>system data views</strong> (_Open, _Click, _Sent, _Subscribers) and a join/anti-join: opens in the window, excluded where a click exists for the same job/subscriber. Exact syntax matters less than knowing the data views exist and how tracking data is structured.</p>"},
                {"q": "How do you use Automation Studio to keep a sendable Data Extension fresh?",
                 "a": "<p>A SQL Query Activity writing to a target DE on a schedule, chained with import/file-drop or filter activities. Strong candidates mention overwrite vs update vs append, primary keys to avoid duplicates, and error handling/notifications.</p>"},
                {"q": "What's the difference between a filtered Data Extension and a SQL Query Activity?",
                 "a": "<p>Filtered DEs are a UI-based subset that auto-refreshes from a source DE; SQL Query Activities are more powerful (joins, aggregation, multiple sources) but run on a schedule via Automation Studio. Knowing when the simpler filtered DE is enough shows good judgement.</p>"},
            ]},
            {"category": "Journey Builder & Automation", "items": [
                {"q": "Entry source vs entry criteria in Journey Builder — what's the difference and why does it matter?",
                 "a": "<p>The entry source defines <em>how</em> contacts enter (DE, API event, etc.); criteria/filters refine <em>who</em> proceeds. Re-entry settings determine whether a contact can re-enter. Mistakes here cause contacts to get stuck or double-messaged &mdash; a great candidate raises that risk unprompted.</p>"},
                {"q": "How do you prevent a contact from receiving conflicting messages across multiple journeys?",
                 "a": "<p>Look for: suppression logic, a central send-frequency/contact-fatigue strategy, Einstein Engagement Frequency, and journey entry exclusions. The mature answer treats cross-journey governance as a design problem, not a per-journey fix.</p>"},
            ]},
            {"category": "Deliverability & Scenarios", "items": [
                {"q": "Sends to one domain are landing in spam. How do you investigate?",
                 "a": "<p>Strong answers walk through authentication (SPF/DKIM/DMARC, dedicated IP/SAP warming), list quality and engagement, content/spam-trigger checks, and using Return Path/seed tests. They separate reputation issues from content issues methodically.</p>"},
                {"q": "How do you approach IP warming for a new SFMC account?",
                 "a": "<p>Gradual volume ramp starting with the most engaged subscribers, monitoring bounces/complaints, and not blasting the full list day one. Demonstrates that they've actually launched a sending program.</p>"},
                {"q": "You're handed an SFMC account with no documentation. How do you get oriented?",
                 "a": "<p>Audit the data model in Contact Builder, map active automations and journeys, review sending domains/IPs and deliverability, and identify business-critical sends before changing anything. Methodical discovery over heroics.</p>"},
            ]},
        ],
        "prep_tips": (
            "<p><strong>Practise AMPscript and SQL by hand.</strong> Be ready to talk through a "
            "<code>LookupRows()</code> loop and an anti-join against the system data views &mdash; "
            "these come up constantly for developer/specialist roles.</p>"
            "<p><strong>Lead with the data model.</strong> When you frame answers around Data "
            "Extensions, Subscriber Key, and contact governance, you signal that you understand SFMC "
            "as an architecture, not a set of buttons.</p>"
            "<p><strong>Have a deliverability story.</strong> One concrete example of diagnosing or "
            "improving inbox placement separates specialists from button-pushers.</p>"
        ),
    },
}


class Command(BaseCommand):
    help = "Create/refresh per-tool InterviewGuide content for the flagship tools (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument('--overwrite', action='store_true',
                            help="Overwrite existing guide content (otherwise only fills blanks).")

    def handle(self, *args, **options):
        overwrite = options['overwrite']
        martech_cat, _ = Category.objects.get_or_create(name="MarTech", defaults={"slug": "martech"})

        for tool_name, data in GUIDES.items():
            tool = (Tool.objects.filter(name__iexact=tool_name).first()
                    or Tool.objects.filter(slug=slugify(tool_name)).first())
            if not tool:
                tool = Tool.objects.create(name=tool_name, slug=slugify(tool_name), category=martech_cat)
                self.stdout.write(self.style.WARNING(f"  created missing Tool: {tool_name}"))

            year = "2026"
            defaults = {
                "slug": tool.slug,
                "intro": data["intro"],
                "prep_tips": data["prep_tips"],
                "questions": data["questions"],
                "meta_title": data["meta_title"].replace("{year}", year),
                "meta_description": data["meta_description"].replace("{year}", year),
                "is_published": True,
            }
            guide, created = InterviewGuide.objects.get_or_create(tool=tool, defaults=defaults)
            if created:
                self.stdout.write(self.style.SUCCESS(
                    f"  + {tool.name} guide ({guide.question_count()} Qs)  /{tool.slug}-interview-questions/"))
            elif overwrite:
                for k, v in defaults.items():
                    setattr(guide, k, v)
                guide.save()
                self.stdout.write(self.style.SUCCESS(f"  ~ {tool.name} guide refreshed"))
            else:
                self.stdout.write(f"  = {tool.name} guide exists (use --overwrite to refresh)")

        self.stdout.write(self.style.SUCCESS("Done."))

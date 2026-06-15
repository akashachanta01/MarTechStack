from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from jobs.models import BlogPost


# ---------------------------------------------------------------------------
# Batch 2 of hand-authored evergreen MarTech blog content. Same conventions as
# seed_blog_posts.py: practitioner-focused, multiple <h2> headings so the post
# template's auto-Table-of-Contents populates, idempotent get_or_create keyed by
# slug, --overwrite to refresh on deploy. None of these slugs overlap batch 1.
#
# Editorial rules honoured: no fabricated statistics or invented salary
# datasets; salary bands are qualitative / approximate; public sources are named
# (BLS, Trailhead, HubSpot Academy) without inventing numbers. Every post ends
# with a real internal CTA to /jobs/ or /tools/.
# ---------------------------------------------------------------------------

AUTHOR = "MarTechJobs Team"

POSTS = [
    # 1 -------------------------------------------------------------------
    {
        "slug": "what-is-marketing-automation",
        "title": "What Is Marketing Automation and How Does It Actually Work?",
        "category": "Tech Stacks",
        "read_time": "9 min read",
        "published_offset": 1,
        "excerpt": "Marketing automation gets described as 'sending emails automatically' — which badly undersells it. Here's what it really is, the mechanics underneath, and where it breaks.",
        "meta_title": "What Is Marketing Automation & How It Works",
        "meta_description": "Marketing automation explained for practitioners: triggers, conditions, journeys, and the data model underneath — plus the common pitfalls that quietly break it.",
        "content": (
            "<p>Ask five people to define marketing automation and you'll get five fuzzy answers, "
            "most of which boil down to \"sending emails automatically.\" That's a small slice of it. "
            "Marketing automation is really a way of encoding marketing decisions into software so "
            "they run consistently, at scale, without a human pressing send each time. Here's how it "
            "actually works underneath.</p>"

            "<h2>The core idea</h2>"
            "<p>At its heart, marketing automation is <strong>if-this-then-that</strong> logic applied "
            "to customer data. You define a starting condition (someone fills in a form, a deal stage "
            "changes, a date passes), and the platform reacts by doing something (sending a message, "
            "updating a field, notifying a rep, adding the contact to a list). String enough of these "
            "together and you've described an entire customer journey in rules a machine can execute.</p>"
            "<p>The reason it matters isn't just efficiency. It's <em>consistency</em>. A human nurture "
            "process depends on someone remembering to follow up; an automated one runs the same way "
            "for the ten-thousandth contact as it did for the first.</p>"

            "<h2>The three building blocks</h2>"
            "<h3>Triggers</h3>"
            "<p>The event that starts a flow. Common triggers include a form submission, a list "
            "membership change, a page visit, a property update, or simply a scheduled date. Every "
            "automation begins with the question \"what should kick this off?\"</p>"
            "<h3>Conditions and branching</h3>"
            "<p>Once a contact enters a flow, conditions decide their path. Has this person opened the "
            "first email? Are they in a target industry? Is their lead score above a threshold? "
            "Branching is where automation stops being a blunt blast and starts feeling personalised.</p>"
            "<h3>Actions</h3>"
            "<p>What the system actually does: send an email, set a field, create a task, enrol the "
            "contact in another workflow, or push data to the CRM. Actions are where the logic touches "
            "the real world.</p>"

            "<h2>What lives underneath: the data model</h2>"
            "<p>Here's the part beginners miss. Automation is only as good as the data it reads. Every "
            "trigger and condition queries a contact record — their properties, their activity "
            "history, their list memberships. If that data is dirty (duplicate contacts, blank fields, "
            "inconsistent values), the automation makes wrong decisions confidently. The best "
            "automation practitioners spend as much time on data hygiene as on building flows, because "
            "they know the flow inherits the quality of the data beneath it.</p>"

            "<h2>A concrete example</h2>"
            "<p>Imagine a B2B software company. A visitor downloads a whitepaper (trigger). The "
            "automation checks their job title and company size (conditions). If they look like a good "
            "fit, they enter a five-email nurture sequence spaced over two weeks, and their lead score "
            "ticks up with each open and click (actions). The moment their score crosses a threshold, "
            "the system notifies a sales rep and creates a task (action). If they go cold for thirty "
            "days, they exit the nurture and drop into a re-engagement track. No human touched any of "
            "that — but a human <em>designed</em> every rule.</p>"

            "<h2>Where marketing automation breaks</h2>"
            "<h3>Over-engineering</h3>"
            "<p>The most common failure mode is building byzantine flows with dozens of branches nobody "
            "can debug. Complexity feels sophisticated; it's actually a liability. Simple, observable "
            "automation beats clever automation you can't troubleshoot.</p>"
            "<h3>No exit criteria</h3>"
            "<p>Contacts get stuck in loops, receive duplicate or contradictory messages, or never "
            "leave a sequence. Every flow needs clear exit conditions — it's the difference between "
            "automation that runs and automation that runs amok.</p>"
            "<h3>Set and forget</h3>"
            "<p>Automation isn't a slow cooker. Markets shift, content goes stale, links break, and a "
            "flow that worked a year ago may now be quietly emailing people the wrong thing. Good teams "
            "audit their automations on a schedule.</p>"

            "<h2>Marketing automation vs CRM vs email tool</h2>"
            "<p>People conflate these. A <strong>CRM</strong> stores who your contacts are. An "
            "<strong>email tool</strong> sends messages. <strong>Marketing automation</strong> is the "
            "decision layer that sits across both — it reads CRM data, decides what should happen, "
            "and orchestrates the email tool (and other channels) accordingly. Many platforms bundle "
            "all three, which is why the lines blur, but conceptually they're distinct jobs.</p>"

            "<h2>How to learn it for real</h2>"
            "<p>Reading about automation teaches you the vocabulary; building teaches you the craft. "
            "Spin up a free portal — HubSpot Academy offers free training and a free CRM you can "
            "actually build in — and construct a complete nurture flow for an imaginary company, "
            "with branching, scoring, and exit criteria. The act of debugging your own flow when it "
            "misbehaves will teach you more than any course. The concepts transfer across every "
            "platform, so what you learn in one tool carries over.</p>"
            "<p>Want to see which automation platforms employers actually hire for? "
            "<a href=\"/jobs/\">Browse current marketing automation and MarTech roles</a> and watch "
            "which tools recur in the requirements.</p>"
        ),
    },
    # 2 -------------------------------------------------------------------
    {
        "slug": "hubspot-vs-salesforce-which-to-learn",
        "title": "HubSpot vs Salesforce: Which CRM Should You Learn First?",
        "category": "Tech Stacks",
        "read_time": "9 min read",
        "published_offset": 4,
        "excerpt": "Both are excellent first CRMs to learn — but they lead to different careers. Here's an honest comparison to help you pick the one that fits where you want to go.",
        "meta_title": "HubSpot vs Salesforce: Which to Learn First",
        "meta_description": "HubSpot vs Salesforce for your first CRM skill — learning curve, job market, the kind of work each leads to, and how to choose based on your goals.",
        "content": (
            "<p>If you're breaking into MarTech and want to anchor your learning on a CRM, the two "
            "obvious candidates are HubSpot and Salesforce. Both have huge job markets, free learning "
            "resources, and free environments you can practise in. But they're not interchangeable — "
            "they reward different temperaments and lead to different careers. Here's how to choose.</p>"

            "<h2>The honest one-line summary</h2>"
            "<p><strong>HubSpot</strong> is faster to learn, friendlier, and gets you productive "
            "quickly. <strong>Salesforce</strong> is deeper, more technical, more configurable, and "
            "sits at the centre of a much larger enterprise ecosystem. Neither is \"better\" — they're "
            "optimised for different things and different company sizes.</p>"

            "<h2>HubSpot: the gentle on-ramp</h2>"
            "<h3>The learning curve</h3>"
            "<p>HubSpot is genuinely beginner-friendly. The interface is clean, the concepts are "
            "approachable, and HubSpot Academy offers free, well-structured courses plus a free CRM you "
            "can build in. You can become useful in weeks, not months.</p>"
            "<h3>The work it leads to</h3>"
            "<p>HubSpot skills lean toward generalist Marketing Ops — building workflows, managing "
            "the CRM, running campaigns, and reporting, mostly through configuration rather than code. "
            "It's common in SMBs and mid-market companies.</p>"
            "<h3>The trade-off</h3>"
            "<p>Because it's accessible, HubSpot skills are also common. Differentiation comes from "
            "depth in strategy, integrations, and measurement rather than from the tool alone.</p>"

            "<h2>Salesforce: the deeper, larger ecosystem</h2>"
            "<h3>The learning curve</h3>"
            "<p>Salesforce is steeper. It's enormously configurable, which means more power but more "
            "complexity. The upside is that Salesforce's free Trailhead learning platform is one of the "
            "best vendor education resources in existence, with guided paths for admins and developers "
            "alike, plus free developer orgs to practise in.</p>"
            "<h3>The work it leads to</h3>"
            "<p>Salesforce skills branch into distinct careers — administration (declarative "
            "configuration), development (Apex and Lightning Web Components), and platform "
            "architecture. It dominates the enterprise, so the roles tend to be larger-company, "
            "deeper, and more specialised.</p>"
            "<h3>The trade-off</h3>"
            "<p>It takes longer to become genuinely competent, but that depth is precisely what makes "
            "skilled Salesforce people hard to replace.</p>"

            "<h2>The decisive questions</h2>"
            "<h3>What size company do you want to work for?</h3>"
            "<p>If you're drawn to startups and mid-market, HubSpot is more common. If you want to work "
            "in the enterprise, Salesforce is closer to mandatory.</p>"
            "<h3>How technical do you want to get?</h3>"
            "<p>If you'd rather configure and stay close to marketing strategy, HubSpot fits. If you "
            "enjoy deep technical configuration — or even code — Salesforce rewards that appetite.</p>"
            "<h3>How fast do you need to be employable?</h3>"
            "<p>HubSpot gets you to demonstrable competence faster, which matters if you're "
            "career-changing and need traction quickly.</p>"

            "<h2>The both-and reality</h2>"
            "<p>Here's the thing nobody tells beginners: the concepts transfer. Objects, fields, "
            "relationships, automation logic, reporting — these are the same ideas in both platforms, "
            "wearing different clothes. Learning one deeply makes the second dramatically faster to "
            "pick up. Many strong MarTech professionals end up fluent in both, because a real stack "
            "often includes HubSpot for marketing and Salesforce as the system of record, with data "
            "syncing between them. You're not making a permanent choice; you're choosing where to "
            "start.</p>"

            "<h2>A practical recommendation</h2>"
            "<p>If you have no strong pull either way, start with HubSpot. It gets you producing real "
            "work fastest, gives you a portfolio project quickly, and teaches you the foundational "
            "concepts gently. Then, once you're comfortable, learn Salesforce's data model and "
            "administration — that combination (marketing fluency in HubSpot plus CRM depth in "
            "Salesforce) is highly employable and reflects how real stacks are actually built. If you "
            "already know you want enterprise or technical work, start with Salesforce and Trailhead "
            "directly.</p>"
            "<p>To ground this in reality, "
            "<a href=\"/jobs/\">browse current MarTech and CRM roles</a> and note which platform shows "
            "up in the postings for the kind of company you want to work for — let the market guide "
            "your first investment.</p>"
        ),
    },
    # 3 -------------------------------------------------------------------
    {
        "slug": "how-to-become-a-hubspot-admin",
        "title": "How to Become a HubSpot Admin",
        "category": "Career Advice",
        "read_time": "9 min read",
        "published_offset": 7,
        "excerpt": "HubSpot Admin is one of the most accessible MarTech roles to break into — if you build real skills instead of just collecting certificates. Here's the practical path.",
        "meta_title": "How to Become a HubSpot Admin",
        "meta_description": "A practical path to becoming a HubSpot Admin: the skills that matter, certifications worth doing, a portfolio project that proves you can do the job, and how to land it.",
        "content": (
            "<p>HubSpot Admin is one of the better entry points into MarTech. The platform is "
            "beginner-friendly, the learning is free, and demand is broad because so many companies "
            "run on HubSpot and need someone to actually operate it well. Here's a realistic path from "
            "zero to hireable.</p>"

            "<h2>What a HubSpot Admin actually does</h2>"
            "<p>A HubSpot Admin is the person who keeps the platform running and useful: managing "
            "users and permissions, building and maintaining workflows, keeping the CRM data clean, "
            "creating reports and dashboards, setting up integrations, and translating what the "
            "marketing and sales teams want into how the platform is configured. They're the in-house "
            "expert everyone goes to when something in HubSpot needs to change or breaks.</p>"

            "<h2>Step 1: Learn the platform properly</h2>"
            "<p>Start with HubSpot Academy. It's free, well-structured, and the obvious first move. But "
            "don't just binge videos — open a free HubSpot portal alongside and build everything you "
            "learn. The difference between someone who watched the courses and someone who can do the "
            "job is whether they've actually configured the thing with their own hands.</p>"
            "<h3>The core areas to master</h3>"
            "<ul>"
            "<li>The CRM: contacts, companies, deals, and how the objects relate.</li>"
            "<li>Properties: default and custom, and why field design matters.</li>"
            "<li>Workflows: triggers, branching, delays, exit criteria.</li>"
            "<li>Lists: active vs static, and the segmentation logic behind them.</li>"
            "<li>Reporting and dashboards: answering real business questions.</li>"
            "<li>Forms, landing pages, and email tools.</li>"
            "</ul>"

            "<h2>Step 2: Get the certifications that matter</h2>"
            "<p>HubSpot's free certifications are worth doing — not because a badge gets you hired, "
            "but because they pass keyword filters and prove baseline competence. The most relevant for "
            "an admin path are the foundational platform and marketing certifications. Earn a couple of "
            "relevant ones; don't collect all of them. A wall of badges with nothing built behind it "
            "reads as theory, not skill.</p>"

            "<h2>Step 3: Build a portfolio project</h2>"
            "<p>This is what separates you from the pile. Invent a fictional company and build out its "
            "HubSpot instance: a clean data model with thoughtful custom properties, a complete "
            "lead-nurture workflow with branching and exit criteria, a lead-scoring model with "
            "documented reasoning, and a dashboard that answers a specific business question. Then "
            "write up the <em>decisions</em> you made and why. Being able to walk an interviewer "
            "through your reasoning is the single strongest signal you can give.</p>"

            "<h2>Step 4: Develop the skills certifications don't teach</h2>"
            "<h3>Data hygiene discipline</h3>"
            "<p>Real admins fight entropy. Deduplication, standardised field values, validation, and "
            "the unglamorous habit of not letting the database rot — this is foundational, and it's "
            "rarely covered well in courses.</p>"
            "<h3>Stakeholder translation</h3>"
            "<p>Much of the job is turning vague requests (\"can we email people who went cold?\") into "
            "concrete, well-built automation. Practise asking clarifying questions before building.</p>"
            "<h3>Debugging</h3>"
            "<p>When a workflow misbehaves, can you methodically figure out why? This skill only comes "
            "from breaking and fixing things in your own portal.</p>"

            "<h2>Step 5: Target the right roles</h2>"
            "<p>You probably won't land a senior admin role first. Look for titles like Marketing Ops "
            "Coordinator, Marketing Automation Specialist, CRM Administrator, or a HubSpot-focused role "
            "on a small team where you'll touch everything. Smaller companies are often the best entry "
            "point because less specialisation means more surface area to learn on.</p>"

            "<h2>Step 6: Frame your existing experience</h2>"
            "<p>Most people aren't truly starting from zero. Spreadsheet-heavy work means you "
            "understand data. Any process or coordination experience means you understand operations. "
            "If you've used a CRM in a sales or support role, you're already ahead. Translate that "
            "experience into HubSpot terms on your resume rather than presenting yourself as a blank "
            "slate.</p>"

            "<h2>What growth looks like from here</h2>"
            "<p>HubSpot Admin is a launchpad, not a ceiling. From here, common paths include deepening "
            "into Marketing Operations Manager, specialising in integrations and the wider stack, "
            "broadening into RevOps, or growing into a HubSpot architect role at a larger company or "
            "agency. The foundational skills — data, automation, process, reporting — are exactly "
            "what qualifies you for the next level, so the work you do as an admin compounds directly "
            "into your next role.</p>"
            "<p>Ready to see what employers want? "
            "<a href=\"/jobs/\">Browse current HubSpot and Marketing Ops roles</a> and read a few "
            "descriptions back to back — the overlap tells you exactly what to build toward.</p>"
        ),
    },
    # 4 -------------------------------------------------------------------
    {
        "slug": "lead-scoring-explained",
        "title": "Lead Scoring Explained: How to Set It Up Without Overcomplicating It",
        "category": "Tech Stacks",
        "read_time": "9 min read",
        "published_offset": 10,
        "excerpt": "Most lead-scoring models are too complicated to trust and too brittle to maintain. Here's how lead scoring actually works and how to build a model that sales will use.",
        "meta_title": "Lead Scoring Explained (Without the Complexity)",
        "meta_description": "Lead scoring explained for practitioners: fit vs behaviour, how to design a simple model sales actually trusts, and the common pitfalls that make scoring useless.",
        "content": (
            "<p>Lead scoring is one of those things every marketing team thinks it needs and very few "
            "implement well. The usual outcome is an elaborate model nobody trusts, sales ignores, and "
            "marketing quietly stops maintaining. The fix isn't a better algorithm — it's "
            "restraint. Here's how lead scoring really works and how to build one that survives "
            "contact with reality.</p>"

            "<h2>What lead scoring is for</h2>"
            "<p>Lead scoring is a system for ranking leads by how likely they are to become customers, "
            "so that sales spends time on the right people and marketing knows who's ready for a "
            "handoff. That's it. It's a prioritisation tool, not a crystal ball. Keeping that purpose "
            "front of mind is what stops a model from ballooning into something unusable.</p>"

            "<h2>The two dimensions: fit and behaviour</h2>"
            "<h3>Fit (who they are)</h3>"
            "<p>Does this person match your ideal customer? Job title, seniority, company size, "
            "industry, geography. A senior decision-maker at a target-size company in your core "
            "industry scores high on fit regardless of what they've done.</p>"
            "<h3>Behaviour (what they do)</h3>"
            "<p>How engaged are they? Email opens and clicks, page visits (especially pricing and "
            "product pages), content downloads, demo requests, webinar attendance. Behaviour signals "
            "intent and timing.</p>"
            "<p>The crucial insight is that <strong>these two dimensions are different questions</strong>. "
            "A perfect-fit lead who's done nothing isn't ready for sales. A highly active lead who's a "
            "terrible fit isn't worth a rep's time. Mature models keep fit and behaviour somewhat "
            "separate rather than blending them into one meaningless number.</p>"

            "<h2>How to actually build one</h2>"
            "<h3>Start by defining 'qualified' with sales</h3>"
            "<p>Before assigning a single point, sit with sales and agree what a sales-ready lead looks "
            "like. If marketing and sales don't share that definition, no scoring model will fix the "
            "handoff — it'll just automate the disagreement.</p>"
            "<h3>Keep the model small</h3>"
            "<p>Resist the urge to score everything. Pick a handful of high-signal fit criteria and a "
            "handful of high-intent behaviours. A model with ten well-chosen rules beats one with "
            "fifty rules nobody can explain. You should be able to look at any lead's score and say "
            "<em>why</em> it's that number.</p>"
            "<h3>Add negative scoring</h3>"
            "<p>Just as important as adding points is removing them. Students, competitors, job "
            "seekers, free-email-domain signups, and people who've gone inactive for months should "
            "lose points. Negative scoring keeps the top of your list clean.</p>"
            "<h3>Decay over time</h3>"
            "<p>Behaviour scores should fade. Someone who downloaded a guide six months ago and "
            "vanished isn't as hot as someone who did it yesterday. Without decay, your model "
            "accumulates stale points and slowly loses meaning.</p>"

            "<h2>The pitfalls that make scoring useless</h2>"
            "<h3>Over-complication</h3>"
            "<p>The number-one killer. The more elaborate the model, the less anyone understands it, "
            "the less they trust it, and the faster it rots. Complexity is not sophistication.</p>"
            "<h3>Building it in a vacuum</h3>"
            "<p>If marketing builds scoring without sales, sales won't use it. Co-ownership isn't "
            "optional — it's the whole point of the exercise.</p>"
            "<h3>Set and forget</h3>"
            "<p>A scoring model needs periodic review. Are the high scorers actually converting? If "
            "your best leads aren't closing, the model is wrong and needs recalibrating against real "
            "outcomes.</p>"

            "<h2>A simple model that works</h2>"
            "<p>Here's a sane starting point. Assign fit points for a handful of ideal-customer "
            "attributes. Assign behaviour points for a few high-intent actions, with the biggest "
            "weights on the strongest signals (pricing-page visits, demo requests). Apply negative "
            "points for clear disqualifiers. Set a threshold that, when crossed, notifies sales and "
            "creates a task. Then watch what converts and adjust. Start simple, prove it works, and "
            "only add complexity when a real gap demands it.</p>"

            "<h2>When you might not need scoring at all</h2>"
            "<p>One honest caveat: not every team needs a scoring model. If your lead volume is low "
            "enough that sales can review every lead by hand, a formal model may be premature overhead. "
            "Lead scoring earns its keep when volume exceeds what humans can triage manually. Don't "
            "build sophisticated machinery to solve a problem you don't yet have.</p>"
            "<p>Want to see which platforms list lead scoring as a required skill? "
            "<a href=\"/jobs/\">Browse current Marketing Ops and automation roles</a> — it shows up "
            "constantly, and knowing how to do it simply is a genuine differentiator.</p>"
        ),
    },
    # 5 -------------------------------------------------------------------
    {
        "slug": "marketing-attribution-models-explained",
        "title": "Marketing Attribution Models, Explained for Practitioners",
        "category": "Tech Stacks",
        "read_time": "10 min read",
        "published_offset": 13,
        "excerpt": "Attribution is where marketers get into the most arguments and the most trouble. Here's a clear, honest explanation of the models, their trade-offs, and how to pick one.",
        "meta_title": "Marketing Attribution Models Explained",
        "meta_description": "Marketing attribution models explained for practitioners — first-touch, last-touch, linear, time-decay, and multi-touch — with the trade-offs and how to choose.",
        "content": (
            "<p>Attribution is the question \"what actually drove this conversion?\" — and it's "
            "deceptively hard. Customers touch many channels before they buy, and deciding how to give "
            "credit across those touches shapes budgets, careers, and the occasional heated meeting. "
            "Here's a practitioner's guide to the models, what each gets right and wrong, and how to "
            "choose without pretending any of them is perfect.</p>"

            "<h2>Why attribution is hard</h2>"
            "<p>A real customer journey might involve a blog post found via search, an ad seen weeks "
            "later, an email, a webinar, and finally a direct visit to buy. Which one gets the credit? "
            "All of them contributed; none of them alone closed the deal. Attribution models are just "
            "different rules for splitting that credit — and crucially, <strong>every model is a "
            "simplification</strong>. None of them is truth. The goal is a model that's useful, not "
            "one that's correct, because correct isn't on the menu.</p>"

            "<h2>Single-touch models</h2>"
            "<h3>First-touch attribution</h3>"
            "<p>All credit goes to the very first interaction. This answers \"what creates "
            "awareness?\" and is useful for evaluating top-of-funnel and demand-creation efforts. Its "
            "blind spot: it ignores everything that happened between first touch and the sale, so it "
            "over-credits awareness channels and under-credits anything that closes.</p>"
            "<h3>Last-touch attribution</h3>"
            "<p>All credit goes to the final interaction before conversion. It's the simplest and most "
            "common model, and it answers \"what closes?\" — but it badly under-credits everything "
            "that built the relationship earlier. Last-touch makes brand and awareness work look "
            "worthless even when they're essential.</p>"

            "<h2>Multi-touch models</h2>"
            "<h3>Linear attribution</h3>"
            "<p>Credit is split evenly across every touchpoint. It acknowledges that the whole journey "
            "matters, which is more honest than single-touch — but treating a throwaway email open "
            "as equal to a demo request is obviously too blunt.</p>"
            "<h3>Time-decay attribution</h3>"
            "<p>Touchpoints closer to conversion get more credit, earlier ones get less. This is "
            "intuitively appealing for businesses with longer sales cycles, where recent interactions "
            "plausibly matter more. The weakness: it systematically discounts the awareness touches "
            "that started the journey.</p>"
            "<h3>Position-based (U-shaped)</h3>"
            "<p>Gives extra weight to the first and last touches (often around 40% each) and splits the "
            "rest across the middle. The logic: the first touch (got them in) and the converting touch "
            "(closed them) are the most important, with the middle nurturing the relationship. It's a "
            "reasonable compromise for many B2B funnels.</p>"

            "<h2>Data-driven attribution</h2>"
            "<p>The most sophisticated approach uses statistical models to assign credit based on what "
            "actually correlates with conversion across your real data, rather than a fixed rule. It "
            "can be powerful, but it requires significant data volume to be reliable and it's a black "
            "box — harder to explain and defend in a meeting. It's a fit for high-volume businesses, "
            "overkill for smaller ones.</p>"

            "<h2>How to actually choose</h2>"
            "<h3>Match the model to the question</h3>"
            "<p>If you're evaluating awareness investment, lean first-touch. If you're optimising "
            "closing tactics, last-touch tells you more. If you want a balanced view of a full B2B "
            "journey, a position-based or time-decay model is usually the pragmatic pick. The right "
            "model depends on the decision you're trying to make.</p>"
            "<h3>Don't marry one model</h3>"
            "<p>Sophisticated teams look at multiple models side by side. If a channel looks great "
            "under first-touch but invisible under last-touch, that's not contradiction — it's "
            "insight about where in the funnel that channel works. Comparing models often reveals more "
            "than any single one.</p>"
            "<h3>Be honest about the limits</h3>"
            "<p>Attribution can't capture offline conversations, word of mouth, or the brand impression "
            "that made someone click in the first place. Treat your numbers as directional evidence, "
            "not gospel. The marketer who says \"this is our best estimate and here's why\" is more "
            "credible than the one who defends a single number to the death.</p>"

            "<h2>The practitioner's takeaway</h2>"
            "<p>The goal of attribution isn't perfect accounting — it's better decisions. A simple, "
            "well-understood model that your team trusts and acts on beats a sophisticated one nobody "
            "believes. Start with something explainable, use multiple lenses, and keep reminding "
            "everyone that the map is not the territory. The teams that get this right argue less about "
            "credit and spend more time acting on what the models broadly agree on.</p>"
            "<p>Attribution and measurement skills are in constant demand. "
            "<a href=\"/jobs/\">Browse current MarTech and analytics roles</a> to see how often "
            "attribution shows up in the requirements.</p>"
        ),
    },
    # 6 -------------------------------------------------------------------
    {
        "slug": "what-does-a-martech-engineer-do",
        "title": "What Does a Marketing / MarTech Engineer Actually Do?",
        "category": "Career Advice",
        "read_time": "9 min read",
        "published_offset": 16,
        "excerpt": "MarTech Engineer is a newer title that confuses a lot of people. Here's what the role actually involves, how it differs from Marketing Ops, and who thrives in it.",
        "meta_title": "What Does a MarTech Engineer Actually Do?",
        "meta_description": "What a MarTech / Marketing Engineer actually does — integrations, APIs, data pipelines, and the line between this role and Marketing Ops, explained for practitioners.",
        "content": (
            "<p>\"MarTech Engineer\" and \"Marketing Engineer\" are relatively new titles, and they "
            "trip people up. Is it a marketer who codes? A software engineer who does marketing? The "
            "honest answer is that it sits deliberately in between — and that's exactly what makes "
            "the role valuable. Here's what it actually involves.</p>"

            "<h2>The core of the role</h2>"
            "<p>A MarTech Engineer is the person who makes the marketing technology stack work at a "
            "<strong>technical, systems level</strong>. Where a Marketing Ops generalist might "
            "configure tools and manage campaigns, a MarTech Engineer goes deeper: building "
            "integrations between systems, writing scripts and queries, designing data pipelines, and "
            "solving the technical problems that off-the-shelf configuration can't reach. They're the "
            "engineering brain inside the marketing function.</p>"

            "<h2>What the day-to-day looks like</h2>"
            "<h3>Integrations and APIs</h3>"
            "<p>Much of the job is making systems that weren't designed to talk to each other "
            "communicate cleanly. That means working with APIs, webhooks, and middleware — pushing "
            "data from a CRM to a warehouse, syncing an automation platform with a product database, "
            "or wiring up an event stream so behaviour triggers the right messaging.</p>"
            "<h3>Data pipelines and modelling</h3>"
            "<p>MarTech Engineers often own how marketing data flows and is structured. They build and "
            "maintain pipelines, write SQL, and make sure the data feeding campaigns and reporting is "
            "clean, timely, and trustworthy. When marketing wants to act on product usage data, the "
            "engineer is the one who makes that data usable.</p>"
            "<h3>Scripting and custom logic</h3>"
            "<p>When a platform's native features can't do what's needed — complex personalisation, "
            "a custom calculation, an unusual automation — the engineer writes the code. That might "
            "be AMPscript in Salesforce Marketing Cloud, JavaScript in a tag manager, Python for a "
            "data job, or platform-specific scripting.</p>"
            "<h3>Reliability and debugging</h3>"
            "<p>When a sync silently fails or data goes missing between two systems, the MarTech "
            "Engineer is who tracks it down. Most painful MarTech bugs live <em>between</em> tools, not "
            "inside them, and diagnosing those requires someone who can reason across system "
            "boundaries.</p>"

            "<h2>How it differs from Marketing Ops</h2>"
            "<p>The line is fuzzy and varies by company, but a useful heuristic: <strong>Marketing Ops "
            "is broader and more process-oriented; MarTech Engineering is deeper and more technical</strong>. "
            "Ops owns the campaign infrastructure, lead routing, reporting, and the day-to-day plumbing "
            "— often through configuration and stakeholder work. Engineering owns the harder "
            "technical layer beneath that: the integrations, pipelines, and custom code. At a small "
            "company, one person does both. At a larger one, they're distinct roles, and the engineer "
            "is the one Ops escalates to when something needs real code.</p>"

            "<h2>How it differs from a software engineer</h2>"
            "<p>A MarTech Engineer isn't usually building product software. They live in the marketing "
            "and data tools, and their work is judged by marketing outcomes — better data, working "
            "integrations, automation that runs reliably. The technical skills overlap with software "
            "engineering (APIs, SQL, scripting, debugging), but the context, the tools, and the "
            "success metrics are marketing's. The best ones are bilingual: technical enough to build, "
            "commercially fluent enough to know <em>why</em> they're building it.</p>"

            "<h2>The skills that matter</h2>"
            "<ul>"
            "<li>SQL and data fluency — the single most useful technical skill.</li>"
            "<li>API and integration literacy — webhooks, REST, how syncs actually work.</li>"
            "<li>Scripting — Python, JavaScript, or platform-specific languages.</li>"
            "<li>Data modelling — structuring data so systems and reports stay sane.</li>"
            "<li>Deep knowledge of at least one core platform.</li>"
            "<li>Debugging discipline and a systems mindset.</li>"
            "</ul>"

            "<h2>Who thrives in this role</h2>"
            "<p>You'll likely enjoy MarTech Engineering if you find debugging satisfying, you like "
            "building systems rather than just operating them, and you get a quiet thrill from making "
            "two stubborn tools finally sync cleanly. It suits people who are technical by temperament "
            "but want their work to connect visibly to business outcomes rather than disappearing into "
            "a product backlog. If you came from Marketing Ops and kept reaching for code, or from "
            "engineering and found you liked the marketing context, this role is often the natural "
            "home.</p>"

            "<h2>Why the role is growing</h2>"
            "<p>Stacks keep getting more complex, data lives in more places, and the gap between what "
            "marketers want to do and what tools do out of the box keeps widening. Someone has to "
            "bridge that gap technically — and that someone is increasingly a dedicated MarTech "
            "Engineer rather than an overstretched Ops generalist. It's a role with real leverage and "
            "a durable future.</p>"
            "<p>Curious what employers expect? "
            "<a href=\"/jobs/\">Browse current MarTech Engineer and technical Marketing Ops roles</a> "
            "and note the recurring skills — they map closely to the list above.</p>"
        ),
    },
    # 7 -------------------------------------------------------------------
    {
        "slug": "how-to-build-a-martech-resume",
        "title": "How to Build a MarTech Resume That Gets Interviews",
        "category": "Career Advice",
        "read_time": "9 min read",
        "published_offset": 19,
        "excerpt": "Most MarTech resumes die in an automated screen before a human reads them. Here's how to write one that passes the filter and makes a hiring manager want to talk to you.",
        "meta_title": "How to Build a MarTech Resume That Lands Interviews",
        "meta_description": "How to build a MarTech resume that gets interviews — passing automated screens, leading with outcomes, listing tools right, and turning projects into proof.",
        "content": (
            "<p>A strong MarTech resume does two jobs: it survives the automated screen, and it makes a "
            "human want to talk to you. Most resumes fail the first and bore the second. Here's how to "
            "write one that does both — without exaggeration or fluff.</p>"

            "<h2>First, understand what it's up against</h2>"
            "<p>Many applications never reach a human. They're filtered by keyword-matching systems "
            "first. That doesn't mean you should stuff keywords — it means the real, relevant skills "
            "you have should actually appear, in the language the posting uses. If a job asks for "
            "\"marketing automation\" and \"lead scoring,\" and you've done both, those exact phrases "
            "should be on your resume where they're true. Mirror the role's vocabulary honestly.</p>"

            "<h2>Lead with outcomes, not duties</h2>"
            "<p>The biggest difference between a forgettable resume and a compelling one is "
            "outcome-orientation. \"Responsible for managing HubSpot\" tells a hiring manager nothing. "
            "\"Rebuilt lead routing in HubSpot, cutting response time and eliminating manual "
            "assignment\" tells a story. MarTech work produces clean before-and-after narratives — a "
            "routing fix, an automation that killed manual work, a reporting overhaul that changed a "
            "budget decision. Those are your gold. Lead with them.</p>"
            "<h3>The shape of a good bullet</h3>"
            "<p>Action you took, the system or tool involved, and the result. Quantify where you "
            "honestly can (time saved, error reduced, process accelerated) — but never invent "
            "numbers. A real qualitative outcome beats a fabricated metric every time.</p>"

            "<h2>List your tools the right way</h2>"
            "<p>A clear tools section helps both the automated screen and the human. List the "
            "platforms you've genuinely used — CRM, marketing automation, analytics, BI, integration "
            "tools — and be honest about depth. Don't pad with tools you opened once. A hiring "
            "manager who asks you about a tool you barely know will see through it fast, and that "
            "single moment can sink an interview.</p>"

            "<h2>Turn projects into proof</h2>"
            "<p>If you're early in your career or career-changing, a portfolio project is your "
            "strongest asset. Built a complete nurture workflow with branching and scoring for a "
            "fictional company? That's real, demonstrable work — describe it as such, and be ready "
            "to walk through the decisions you made. \"Built a lead-nurture workflow I can walk you "
            "through\" beats \"familiar with HubSpot\" by a mile. Projects signal that you can actually "
            "do the job, not just talk about it.</p>"

            "<h2>Translate non-obvious experience</h2>"
            "<p>Most people breaking into MarTech aren't starting from zero, and the resume is where "
            "you make that case. Spreadsheet-heavy work means you understand data. Process or "
            "coordination experience means you understand operations. CRM exposure in a sales or "
            "support job is directly relevant. Frame that prior experience in MarTech terms instead of "
            "burying it under its old job title.</p>"

            "<h2>Certifications: use them, don't lean on them</h2>"
            "<p>Relevant free certifications — HubSpot's, foundational Salesforce credentials via "
            "Trailhead — are worth listing because they pass filters and signal baseline competence. "
            "But a wall of badges with nothing built behind it reads as theory. A couple of relevant "
            "certs plus a real project is far more persuasive than a long list of certifications "
            "alone.</p>"

            "<h2>Structure and hygiene</h2>"
            "<h3>Keep it scannable</h3>"
            "<p>A hiring manager spends seconds on the first pass. A short, sharp summary line, then "
            "outcome-led bullets, a clear tools section, and certifications. No dense paragraphs, no "
            "recruiter-speak, no \"results-driven team player.\"</p>"
            "<h3>Tailor for the role</h3>"
            "<p>A generic resume blasted everywhere underperforms a tailored one sent to fewer roles. "
            "Adjust the emphasis and vocabulary to match each posting's priorities. It's more work per "
            "application, but the response rate difference is real.</p>"
            "<h3>Make it technically credible</h3>"
            "<p>Use the correct terminology. Saying \"workflows\" when the platform calls them "
            "\"programs,\" or misusing \"attribution\" and \"lead scoring,\" quietly signals you "
            "haven't really done the work. Precision builds trust.</p>"

            "<h2>The mindset that makes it easy</h2>"
            "<p>Stop thinking of your resume as a list of jobs and start thinking of it as a case for "
            "why you'll make a team's marketing engine run better. Every line should answer a hiring "
            "manager's real question: \"will this person solve problems I have?\" Keep a running log "
            "of every problem you solve at work or in your projects — those become your bullets and "
            "your interview stories. Do that, and writing the resume becomes assembly rather than "
            "invention.</p>"
            "<p>Before you tailor, read the market. "
            "<a href=\"/jobs/\">Browse current MarTech and Marketing Ops roles</a> and note the exact "
            "language and skills that recur — that's the vocabulary your resume should speak.</p>"
        ),
    },
    # 8 -------------------------------------------------------------------
    {
        "slug": "cdp-vs-crm-vs-dmp",
        "title": "CDP vs CRM vs DMP: What's the Difference?",
        "category": "Tech Stacks",
        "read_time": "9 min read",
        "published_offset": 22,
        "excerpt": "CDP, CRM, and DMP get used interchangeably and they shouldn't be. Here's a clear, practitioner-level explanation of what each one is, what it's for, and when you need it.",
        "meta_title": "CDP vs CRM vs DMP: What's the Difference?",
        "meta_description": "CDP vs CRM vs DMP explained clearly — what each system does, the data it handles, how they overlap, and which one you actually need for your use case.",
        "content": (
            "<p>CDP, CRM, DMP. Three acronyms, often used as if they're interchangeable, that describe "
            "genuinely different systems with different jobs. Getting them straight matters — both "
            "for choosing tools and for sounding credible in an interview. Here's a clean, practical "
            "breakdown.</p>"

            "<h2>The one-line distinction</h2>"
            "<p>A <strong>CRM</strong> manages your relationships with known individuals, mostly for "
            "sales and service. A <strong>CDP</strong> unifies customer data from every source into a "
            "single profile, mostly for marketing activation. A <strong>DMP</strong> handles "
            "anonymous, often third-party audience data, mostly for advertising. Different data, "
            "different owners, different purposes.</p>"

            "<h2>CRM: the system of record for relationships</h2>"
            "<h3>What it does</h3>"
            "<p>A CRM (Salesforce, HubSpot CRM, Microsoft Dynamics) stores known contacts and accounts "
            "and the history of your interactions with them — deals, emails, calls, support tickets. "
            "It's built around <em>managing relationships</em>, primarily for sales and customer "
            "service teams.</p>"
            "<h3>The data it holds</h3>"
            "<p>First-party, identified data: named people and companies you have a relationship with. "
            "The CRM is usually the authoritative system of record for who your customers and prospects "
            "are.</p>"

            "<h2>CDP: the unified customer profile</h2>"
            "<h3>What it does</h3>"
            "<p>A Customer Data Platform (Segment, mParticle, and others) pulls customer data from "
            "everywhere — website, app, CRM, support tool, product — and stitches it into a single, "
            "unified profile per person. Its purpose is to give marketing a complete, real-time view of "
            "each customer that can then be <em>activated</em> across channels.</p>"
            "<h3>The data it holds</h3>"
            "<p>First-party data, unified across sources. The CDP's superpower is identity resolution: "
            "recognising that the anonymous web visitor, the app user, and the CRM contact are the same "
            "person, and building one profile from all three. It's owned by marketing and built for "
            "segmentation and activation, not relationship management.</p>"
            "<h3>How it differs from a CRM</h3>"
            "<p>People conflate these constantly. A CRM is relationship-centric and sales-owned; a CDP "
            "is data-unification-centric and marketing-owned. A CDP often <em>reads from</em> the CRM "
            "as one of its sources. They complement each other rather than compete — though small "
            "companies frequently get by with just a CRM until their data fragmentation justifies a "
            "CDP.</p>"

            "<h2>DMP: the audience and advertising engine</h2>"
            "<h3>What it does</h3>"
            "<p>A Data Management Platform deals primarily in <em>anonymous</em> audience data, often "
            "including third-party data, to power digital advertising — building and targeting "
            "audience segments for ad campaigns.</p>"
            "<h3>The data it holds</h3>"
            "<p>Largely anonymous, cookie-based, often third-party data, typically with a short shelf "
            "life. DMPs were built for the programmatic advertising world and the audience-targeting "
            "use case.</p>"
            "<h3>Why DMPs are fading</h3>"
            "<p>It's worth being honest: the DMP's relevance has declined as the industry shifts away "
            "from third-party cookies and toward privacy-conscious, first-party data strategies. Much "
            "of what DMPs did is being absorbed into CDPs and first-party approaches. If you're "
            "learning today, prioritise CDP and CRM understanding over DMP.</p>"

            "<h2>How they fit together</h2>"
            "<p>In a mature stack, these aren't rivals — they're layers. The CRM holds your known "
            "relationships and acts as a source of truth for identified contacts. The CDP unifies data "
            "from the CRM and every other source into rich, activatable profiles and pushes segments "
            "out to your marketing tools. Where a DMP exists, it handles the anonymous advertising "
            "audience layer. The data flows between them; the trick is being clear about which system "
            "owns which job.</p>"

            "<h2>Which do you actually need?</h2>"
            "<h3>Almost everyone needs a CRM</h3>"
            "<p>If you have customers and a sales or service motion, you need a system of record. Start "
            "here.</p>"
            "<h3>You need a CDP when data fragmentation hurts</h3>"
            "<p>When customer data is scattered across many tools and you can't get a unified view to "
            "act on, that's the signal for a CDP. Before that point, it's expensive infrastructure "
            "solving a problem you don't yet have.</p>"
            "<h3>You rarely need a standalone DMP today</h3>"
            "<p>For most companies in a first-party, post-cookie world, a standalone DMP is no longer "
            "the priority it once was. Focus your energy and learning on CRM and CDP.</p>"

            "<h2>The interview-ready summary</h2>"
            "<p>If someone asks you to distinguish these in thirty seconds: CRM manages known "
            "relationships for sales and service; CDP unifies first-party customer data into profiles "
            "for marketing activation; DMP handles anonymous audience data for advertising and is on "
            "the decline. Nail that, and you'll sound like you actually understand the data layer — "
            "which is exactly the foundation everything else in MarTech is built on.</p>"
            "<p>Data-layer fluency is in demand. "
            "<a href=\"/jobs/\">Browse current MarTech roles</a> and watch how often CRM and CDP "
            "knowledge appears in the requirements.</p>"
        ),
    },
    # 9 -------------------------------------------------------------------
    {
        "slug": "marketing-ops-career-progression",
        "title": "Marketing Ops Career Progression: From IC to Director",
        "category": "Career Advice",
        "read_time": "9 min read",
        "published_offset": 25,
        "excerpt": "Marketing Ops is one of the better-positioned roles for advancement — but the path isn't automatic. Here's how progression actually works, rung by rung, and what unlocks each step.",
        "meta_title": "Marketing Ops Career Progression: IC to Director",
        "meta_description": "Marketing Ops career progression from IC to Director — the ladder, what unlocks each step, the IC-to-manager shift, and how to grow scope deliberately.",
        "content": (
            "<p>Marketing Operations is one of the better-positioned roles for advancement, precisely "
            "because it touches everything — data, systems, process, reporting, and the seam between "
            "marketing and sales. But progression isn't automatic. Each rung unlocks for a different "
            "reason, and the move that gets you from coordinator to manager is not the move that gets "
            "you from manager to director. Here's how the ladder actually works.</p>"

            "<h2>The shape of the ladder</h2>"
            "<p>A typical progression runs: coordinator or specialist at the entry level, then manager, "
            "then senior manager, then director, and ultimately VP or head-of-Ops leadership. Titles "
            "vary by company, and at smaller organisations the rungs compress, but the underlying "
            "progression of <strong>scope and accountability</strong> is consistent. You're not just "
            "climbing titles; you're expanding what you own.</p>"

            "<h2>The entry level: coordinator / specialist</h2>"
            "<p>At this stage you're executing. You build the workflows, manage the lists, run the "
            "campaigns, fix the data, and handle requests that come to you. The skill you're building "
            "is <strong>competence with the tools and the fundamentals</strong> — and the way you "
            "stand out is by being reliable, curious about why things break, and starting to suggest "
            "improvements rather than just fulfilling tickets.</p>"
            "<h3>What unlocks the next step</h3>"
            "<p>Moving up means shifting from executing requests to <em>designing the process behind "
            "them</em>. The coordinator who notices that lead routing is fundamentally broken and "
            "proposes a fix — rather than just processing the leads — is showing manager-level "
            "thinking.</p>"

            "<h2>The manager level</h2>"
            "<p>Here the job changes from execution to <strong>ownership</strong>. You own systems and "
            "processes end to end: the lead lifecycle, the reporting that leadership relies on, the "
            "automation platform itself. You may start managing people or vendors. The valuable skill "
            "is process thinking — designing how things should work and encoding it — rather than "
            "just being fast at the tools.</p>"
            "<h3>What unlocks the next step</h3>"
            "<p>Senior and director roles open up when you demonstrate <em>strategic</em> impact and "
            "the ability to operate cross-functionally. That means owning the MarTech strategy, making "
            "tooling decisions, negotiating shared definitions with sales and finance, and tying your "
            "work clearly to revenue.</p>"

            "<h2>The senior manager and director level</h2>"
            "<p>At this altitude you're less in the tools and more in the strategy, the budget, and the "
            "people. You set the direction for the Ops function, own the stack as a portfolio, build "
            "and lead a team, and represent Ops in leadership conversations. The job becomes about "
            "<strong>leverage</strong> — getting outcomes through systems and people rather than "
            "personal execution.</p>"
            "<h3>What unlocks the next step</h3>"
            "<p>The move toward VP and head-of-Ops scope comes from broadening beyond marketing — "
            "often into RevOps, owning the full revenue process across marketing, sales, and customer "
            "success — and from demonstrating genuine business leadership, not just functional "
            "excellence.</p>"

            "<h2>The hardest transition: IC to manager</h2>"
            "<p>The single most difficult step is the first leadership jump, because it requires "
            "<em>letting go of the work that made you good</em>. The best individual contributor isn't "
            "automatically a good manager; the skills are different. Your value shifts from \"I built "
            "this\" to \"I enabled my team and my systems to build this.\" People who cling to "
            "hands-on execution stall here. Those who learn to delegate, document, and lead through "
            "process keep climbing.</p>"

            "<h2>How to progress deliberately</h2>"
            "<h3>Acquire scope before you ask for the title</h3>"
            "<p>Promotions in Ops follow scope, not tenure. Volunteer for ownership — take the "
            "tooling decisions, the cross-functional definitions, the reporting leadership — and the "
            "title tends to follow the responsibility you've already demonstrated.</p>"
            "<h3>Build scarce, transferable skills</h3>"
            "<p>Depth in a high-demand platform plus SQL, data modelling, and measurement makes you "
            "harder to replace and easier to promote. These skills travel across employers, so they "
            "compound over a whole career.</p>"
            "<h3>Quantify your impact relentlessly</h3>"
            "<p>Keep a running record of outcomes — time saved, processes fixed, decisions changed by "
            "your reporting. That record is what justifies each promotion and what you negotiate from.</p>"
            "<h3>Get comfortable cross-functionally</h3>"
            "<p>The higher you go, the more the job is diplomacy — aligning marketing, sales, and "
            "finance. Building those relationships early prepares you for senior scope.</p>"

            "<h2>The RevOps fork</h2>"
            "<p>One important branch: at the senior level, many ambitious Ops people move toward RevOps "
            "rather than continuing in pure marketing leadership. RevOps carries the broadest scope and "
            "the clearest path to senior leadership, and deep Marketing Ops experience is a credible "
            "route in. It's worth knowing this fork exists, because the choice between deepening in "
            "marketing and broadening into revenue shapes the back half of your career.</p>"
            "<p>Want to see how companies define these levels? "
            "<a href=\"/jobs/\">Browse current Marketing Ops and RevOps roles</a> across seniority "
            "levels and compare the responsibilities — the ladder becomes concrete fast.</p>"
        ),
    },
    # 10 ------------------------------------------------------------------
    {
        "slug": "email-deliverability-fundamentals",
        "title": "Email Deliverability Fundamentals Every Marketer Should Know",
        "category": "Tech Stacks",
        "read_time": "9 min read",
        "published_offset": 28,
        "excerpt": "You can build the perfect email and still have it land in spam. Deliverability is the invisible layer that decides whether your messages are even seen. Here are the fundamentals.",
        "meta_title": "Email Deliverability Fundamentals for Marketers",
        "meta_description": "Email deliverability fundamentals every marketer should know — authentication (SPF, DKIM, DMARC), sender reputation, engagement, and how to keep mail out of spam.",
        "content": (
            "<p>You can write the perfect email, design it beautifully, and target it precisely — and "
            "still have it silently land in spam, unseen. Deliverability is the invisible layer that "
            "decides whether your message even reaches the inbox. Most marketers never learn it, which "
            "is exactly why knowing it makes you more valuable. Here are the fundamentals.</p>"

            "<h2>What deliverability actually means</h2>"
            "<p>Deliverability is the share of your emails that reach the inbox rather than the spam "
            "folder or oblivion. It's distinct from \"delivery\" — an email can be accepted by the "
            "receiving server (delivered) and still be filed in spam (not <em>delivered to the "
            "inbox</em>). Mailbox providers like Gmail and Outlook make that placement decision based "
            "on a mix of technical signals and recipient behaviour. Your job is to send signals that "
            "say \"this is wanted mail.\"</p>"

            "<h2>Authentication: proving you're really you</h2>"
            "<p>The foundation of deliverability is proving your emails genuinely come from you and "
            "aren't spoofed. Three standards do this, and you should at least understand what each "
            "is.</p>"
            "<h3>SPF (Sender Policy Framework)</h3>"
            "<p>A DNS record listing which servers are allowed to send email on behalf of your domain. "
            "It lets receivers check that mail claiming to be from your domain actually came from an "
            "authorised source.</p>"
            "<h3>DKIM (DomainKeys Identified Mail)</h3>"
            "<p>A cryptographic signature added to your emails that the receiver can verify, confirming "
            "the message wasn't tampered with in transit and genuinely came from your domain.</p>"
            "<h3>DMARC</h3>"
            "<p>A policy that ties SPF and DKIM together and tells receivers what to do with mail that "
            "fails authentication — and gives you reporting on who's sending as your domain. Modern "
            "mailbox providers increasingly expect proper DMARC, so this has moved from nice-to-have "
            "to near-essential for serious senders.</p>"
            "<p>You don't have to configure these alone — it's usually a job done with IT — but you "
            "should understand what they are, because authentication problems are a leading cause of "
            "deliverability failure.</p>"

            "<h2>Sender reputation: your inbox credit score</h2>"
            "<p>Mailbox providers track the reputation of your sending domain and IP over time. Send "
            "wanted, engaging mail and your reputation rises; send to bad addresses, generate "
            "complaints, or trigger spam traps and it falls. A poor reputation means even your good "
            "emails struggle to land. Reputation is earned slowly and damaged quickly, which is why "
            "deliverability rewards consistency and punishes blasting.</p>"

            "<h2>Engagement is the modern signal</h2>"
            "<p>Here's the shift every marketer should internalise: mailbox providers heavily weight "
            "<strong>engagement</strong>. If recipients open, click, and reply, providers conclude your "
            "mail is wanted and keep delivering it to the inbox. If recipients ignore or delete it, "
            "providers start routing it to spam — even for subscribers who once opted in. This is why "
            "<em>sending less to more engaged people</em> often beats blasting your whole list. "
            "Engagement-based sending isn't just good manners; it's how you protect deliverability.</p>"

            "<h2>List hygiene: the unglamorous essential</h2>"
            "<p>Your list quality directly drives deliverability. Repeatedly emailing dead addresses, "
            "spam traps, and disengaged contacts erodes reputation. Good practice includes confirming "
            "opt-ins, removing hard bounces promptly, suppressing long-term non-openers, and never "
            "buying lists (a fast route to spam traps and complaints). A smaller, clean, engaged list "
            "outperforms a large, rotting one — every time.</p>"

            "<h2>Content and structure signals</h2>"
            "<p>Content matters less than authentication and engagement, but it still counts. Spammy "
            "subject lines, broken or sketchy links, image-only emails with no text, and missing "
            "unsubscribe links can all hurt. The defensive move is simple: send mail that looks and "
            "reads like legitimate, wanted communication, with an easy unsubscribe. Making it easy to "
            "leave actually protects you — people who can't unsubscribe hit \"spam\" instead, which is "
            "far more damaging.</p>"

            "<h2>How to think about deliverability as a marketer</h2>"
            "<p>You don't need to become a deliverability engineer. You need to understand the levers "
            "well enough to make good decisions: keep authentication in order, protect sender "
            "reputation, prioritise engagement over reach, and keep your list clean. These "
            "fundamentals don't change when you switch email platforms, which makes them a "
            "high-return skill to invest in. The marketer who understands why messages land — or "
            "don't — is the one whose campaigns actually get seen.</p>"
            "<p>Deliverability knowledge sets you apart. "
            "<a href=\"/jobs/\">Browse current email and lifecycle marketing roles</a> and you'll see "
            "how often deliverability fluency is implicitly required.</p>"
        ),
    },
    # 11 ------------------------------------------------------------------
    {
        "slug": "how-to-run-a-martech-audit",
        "title": "How to Run a MarTech Stack Audit",
        "category": "Tech Stacks",
        "read_time": "10 min read",
        "published_offset": 31,
        "excerpt": "Most stacks accumulate waste quietly — unused tools, overlapping capabilities, broken integrations. A structured audit is how you find it. Here's a repeatable process.",
        "meta_title": "How to Run a MarTech Stack Audit",
        "meta_description": "A repeatable process to run a MarTech stack audit — inventory tools, map data flow, find overlap and waste, and turn findings into a clear action plan.",
        "content": (
            "<p>MarTech stacks rot quietly. A tool gets bought to solve one problem, the person who "
            "championed it leaves, and nobody cancels it. Multiply that by a few years and most teams "
            "are paying for software no one has opened in months, with overlapping capabilities and "
            "integrations silently failing in the background. A structured audit is how you find and "
            "fix it. Here's a process you can actually run.</p>"

            "<h2>Why audit at all</h2>"
            "<p>The point isn't just to cut cost (though you usually will). It's to restore "
            "<strong>velocity and trust</strong>. A bloated, tangled stack means every campaign starts "
            "with a fight over which number is right and which tool to use. A lean, well-integrated one "
            "lets the team move fast. The best argument for auditing isn't savings — it's that a "
            "clean stack makes everyone faster.</p>"

            "<h2>Step 1: Build the inventory</h2>"
            "<p>Start with a complete list of every tool. This is harder than it sounds — shadow "
            "tools bought on someone's credit card rarely show up on the official list. Pull from "
            "finance (what are we paying for?), from the team (what do you actually use?), and from "
            "your integrations (what's connected to what?). For each tool capture:</p>"
            "<ul>"
            "<li>Name and category (CRM, automation, analytics, etc.)</li>"
            "<li>Annual cost</li>"
            "<li>The owner — the single person accountable for it</li>"
            "<li>What it's actually used for</li>"
            "<li>When it was last meaningfully used</li>"
            "<li>What it's integrated with</li>"
            "</ul>"

            "<h2>Step 2: Map the data flow</h2>"
            "<p>An inventory is a list; the real insight is in the connections. Diagram how data moves "
            "between tools — where contacts originate, how they sync to the CRM, how they reach the "
            "automation platform and reporting. This map reveals the things that quietly cause pain: "
            "redundant syncs, manual CSV exports holding the stack together, and the points where data "
            "gets dropped or duplicated. Most painful MarTech problems live <em>between</em> tools, and "
            "this is where you'll see them.</p>"

            "<h2>Step 3: Find the waste</h2>"
            "<h3>Unused tools</h3>"
            "<p>Anything with no meaningful use in months is a cancellation candidate. Be ruthless — "
            "\"we might need it someday\" is how stacks bloat.</p>"
            "<h3>Overlapping capabilities</h3>"
            "<p>Look for multiple tools doing the same job — two email senders, three analytics "
            "tools, overlapping form builders. Overlap fragments data and multiplies cost. Consolidate "
            "where you can.</p>"
            "<h3>Shelfware</h3>"
            "<p>Enterprise tiers bought for advanced features the team never operationalised. If you're "
            "paying a premium for capability you don't use, downgrade or cut it.</p>"
            "<h3>Broken or fragile integrations</h3>"
            "<p>Syncs that fail silently, or that exist only as someone's manual weekly export. These "
            "are reliability risks hiding in plain sight.</p>"

            "<h2>Step 4: Assess each tool honestly</h2>"
            "<p>For every tool, ask three plain questions: What workflow does this serve that isn't "
            "served elsewhere? Who owns it, and do they still need it? And is the data it reads and "
            "writes clean? A tool that fails any of these is either a fix-it or a cut-it. This is also "
            "where you catch tools whose job is already covered by a platform you <em>already</em> pay "
            "for — a common and easy consolidation win.</p>"

            "<h2>Step 5: Turn findings into an action plan</h2>"
            "<p>An audit that ends in a spreadsheet nobody acts on is wasted effort. Sort your findings "
            "into clear buckets: <strong>cut</strong> (cancel unused or redundant tools), "
            "<strong>consolidate</strong> (move a capability into a platform you already own), "
            "<strong>fix</strong> (repair broken integrations and data issues), and <strong>keep</strong> "
            "(tools earning their place). Then prioritise — usually the quick, low-risk cuts first "
            "for an immediate win, then the harder consolidations. Assign an owner and a date to each "
            "action.</p>"

            "<h2>Step 6: Make it recurring</h2>"
            "<p>The single highest-leverage habit is to make this routine. A stack audited once and "
            "then ignored re-bloats within a year or two. Run a lighter version of this twice a year: "
            "list every tool, its cost, its owner, and the last time it drove a decision or workflow, "
            "and cut anything that fails the test. The recurring discipline is what keeps the stack "
            "lean permanently, rather than swinging between bloat and cleanup.</p>"

            "<h2>The judgement that makes an auditor good</h2>"
            "<p>The mechanical part of an audit is easy; the judgement is what's valuable. Knowing when "
            "an overlap is genuine redundancy versus a deliberate specialised choice, when "
            "consolidation will actually work versus create a worse single point of failure, and when "
            "a 'barely used' tool is quietly critical to one important workflow — that's the skill. "
            "A good audit isn't about cutting the most; it's about leaving a stack that's leaner, more "
            "reliable, and faster to work in. That outcome is exactly the kind of concrete, "
            "before-and-after story that gets MarTech people hired and promoted.</p>"
            "<p>Stack audit and rationalisation skills are increasingly sought after. "
            "<a href=\"/jobs/\">Browse current MarTech and Ops roles</a> to see how often stack "
            "ownership and optimisation appear in the requirements.</p>"
        ),
    },
    # 12 ------------------------------------------------------------------
    {
        "slug": "how-to-land-remote-martech-jobs",
        "title": "How to Find and Land Remote MarTech Jobs",
        "category": "Career Advice",
        "read_time": "9 min read",
        "published_offset": 34,
        "excerpt": "MarTech is unusually well-suited to remote work — the job is systems, data, and process. Here's how to find genuinely remote roles and stand out in a wider applicant pool.",
        "meta_title": "How to Find and Land Remote MarTech Jobs",
        "meta_description": "How to find and land remote MarTech jobs — why the field suits remote work, where to look, how to stand out in a global pool, and what employers screen for.",
        "content": (
            "<p>MarTech is unusually well-suited to remote work. The job is fundamentally about "
            "systems, data, and process — work that lives in software and can be done from anywhere "
            "with a good connection. That's the good news. The catch is that remote roles attract a "
            "wider, more competitive applicant pool, so standing out takes more than just applying. "
            "Here's how to find genuinely remote MarTech roles and actually land one.</p>"

            "<h2>Why MarTech suits remote so well</h2>"
            "<p>Unlike roles that depend on a physical presence, MarTech work is conducted entirely "
            "through tools: the CRM, the automation platform, the analytics stack, the integration "
            "layer. Collaboration happens in shared documents, tickets, and calls. And critically, the "
            "work produces <strong>measurable, demonstrable outcomes</strong> — a routing fix, an "
            "automation that eliminated manual work, a reporting overhaul — which makes it easy for "
            "remote employers to evaluate performance without watching you. That measurability is part "
            "of why so many MarTech roles went remote and stayed there.</p>"

            "<h2>Find the genuinely remote roles</h2>"
            "<h3>Read the fine print on 'remote'</h3>"
            "<p>\"Remote\" means different things. Some roles are fully remote anywhere; some are "
            "remote within a country or region; some are \"remote\" but expect occasional or frequent "
            "office time. Before investing in an application, confirm the actual policy, time-zone "
            "expectations, and whether pay is benchmarked nationally or by location — it changes the "
            "math significantly.</p>"
            "<h3>Use niche over generic</h3>"
            "<p>Specialised job boards focused on MarTech and Marketing Ops surface relevant remote "
            "roles far more efficiently than giant generalist sites, where you'll wade through noise. "
            "A focused board where every listing is in your field is worth more than a thousand "
            "irrelevant results.</p>"

            "<h2>Stand out in a wider pool</h2>"
            "<h3>Demonstrable proof beats claims</h3>"
            "<p>In a competitive remote pool, the candidate who can <em>show</em> the work wins. A "
            "portfolio project — a complete nurture workflow with branching and scoring, a clean data "
            "model with documented decisions, a dashboard answering a real question — is concrete "
            "evidence you can do the job. Remote employers especially value proof, because they can't "
            "rely on watching you ramp up in an office.</p>"
            "<h3>Write outcome-led applications</h3>"
            "<p>Lead with results, not duties. \"Rebuilt lead routing, cutting response time\" beats "
            "\"managed HubSpot.\" MarTech produces clean before-and-after stories — use them.</p>"
            "<h3>Mirror the posting's language</h3>"
            "<p>Many applications are filtered by keyword-matching before a human reads them. Make sure "
            "the real, relevant skills you have appear in the language the posting uses — honestly, "
            "where they're true.</p>"

            "<h2>The remote-specific skills employers screen for</h2>"
            "<p>Beyond technical competence, remote employers look for traits that predict success "
            "without supervision.</p>"
            "<h3>Async communication and documentation</h3>"
            "<p>The ability to write clearly, document what you build, and communicate without needing "
            "a real-time conversation is genuinely a remote skill — and it happens to be a core "
            "MarTech skill too. Systems you document are systems a distributed team can trust. "
            "Highlight it.</p>"
            "<h3>Self-direction</h3>"
            "<p>Remote work rewards people who can prioritise, unblock themselves, and make progress "
            "without someone standing over them. Examples of times you owned something end to end are "
            "exactly what reassures a remote hiring manager.</p>"
            "<h3>Tool fluency</h3>"
            "<p>Comfort with collaboration and project tools is assumed in remote settings. It rarely "
            "needs spelling out, but visible fluency removes a small doubt.</p>"

            "<h2>Nail the remote interview</h2>"
            "<p>Remote interviews lean on scenario questions — \"how would you debug a workflow "
            "sending duplicate emails?\" or \"how would you set up lead scoring?\" — because they "
            "reveal how you think without a whiteboard in the room. Reason out loud, walk through a "
            "methodical process, and lean on your portfolio project for concrete material. Treat the "
            "interview itself as a demonstration of remote communication: be clear, structured, and "
            "easy to follow on a call.</p>"

            "<h2>The honest reality of remote competition</h2>"
            "<p>Remote roles have widened access for candidates everywhere — which also means more "
            "competition for each one. Don't let that discourage you; let it sharpen your approach. "
            "The way you win a wider pool is the same way you'd win a local one, just executed better: "
            "demonstrable proof of skill, outcome-led materials, precise and credible communication, "
            "and applications tailored to roles that genuinely fit. Quality of application beats volume "
            "of applications, especially when the pool is large.</p>"
            "<p>Ready to start? "
            "<a href=\"/jobs/\">Browse current remote MarTech and Marketing Ops roles</a> and filter "
            "for the setups that actually fit how and where you want to work.</p>"
        ),
    },
]


class Command(BaseCommand):
    help = "Create/refresh batch 2 of hand-authored evergreen MarTech blog posts (idempotent, keyed by slug)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite', action='store_true',
            help="Update existing posts' fields (otherwise existing slugs are skipped).",
        )

    def handle(self, *args, **options):
        overwrite = options['overwrite']
        today = timezone.now().date()
        created_count = 0
        skipped_count = 0
        updated_count = 0

        for post in POSTS:
            published_at = today - timedelta(days=post.get("published_offset", 0))
            defaults = {
                "title": post["title"],
                "excerpt": post["excerpt"],
                "content": post["content"],
                "meta_title": post["meta_title"],
                "meta_description": post["meta_description"],
                "author": post.get("author", AUTHOR),
                "category": post["category"],
                "read_time": post["read_time"],
                "published_at": published_at,
                "is_published": True,
            }

            obj, created = BlogPost.objects.get_or_create(
                slug=post["slug"], defaults=defaults,
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  + {post['slug']}  ({post['category']})"))
            elif overwrite:
                for k, v in defaults.items():
                    setattr(obj, k, v)
                obj.save()
                updated_count += 1
                self.stdout.write(self.style.SUCCESS(f"  ~ {post['slug']} refreshed"))
            else:
                skipped_count += 1
                self.stdout.write(f"  = {post['slug']} exists (use --overwrite to refresh)")

        self.stdout.write(self.style.SUCCESS(
            f"Done. {created_count} created, {updated_count} updated, "
            f"{skipped_count} skipped (of {len(POSTS)} posts)."))

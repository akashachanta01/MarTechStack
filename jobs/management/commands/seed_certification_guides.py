from django.core.management.base import BaseCommand
from django.utils.text import slugify

from jobs.models import Tool, Category, CertificationGuide


# ---------------------------------------------------------------------------
# Expert-authored certification guide content for flagship MarTech certs.
# The page also renders a LIVE data spine (open roles, companies, paired tools)
# from the job corpus, so the combination stays fresh and original.
# ---------------------------------------------------------------------------

GUIDES = {
    "HubSpot": {
        "cert_name": "HubSpot Marketing Hub Certification",
        "provider": "HubSpot Academy",
        "cost": "Free",
        "exam_format": "75 questions, 3 hours, 80% pass mark",
        "validity": "2 years",
        "difficulty": "Beginner–Intermediate",
        "intro": (
            "<p>The HubSpot Marketing Hub Certification is the entry-level credential for anyone "
            "working professionally on HubSpot. It validates that you can run campaigns, build "
            "workflows, manage contacts, and report on performance inside HubSpot — the skills "
            "hiring managers expect even for junior Marketing Ops roles.</p>"
            "<p>Because HubSpot Academy makes all preparation materials free and the exam itself "
            "costs nothing, this certification has unusually high ROI: low time cost, immediate "
            "credibility signal on your CV, and a direct link to a credential employers can verify "
            "on your HubSpot Academy profile.</p>"
        ),
        "who_should_get": (
            "Marketing Operations professionals early in their careers who use HubSpot daily, "
            "demand generation specialists running campaigns on HubSpot Marketing Hub, anyone "
            "transitioning into MarTech who wants a verified, employer-recognised proof point, "
            "and HubSpot admins who want to formalise their knowledge."
        ),
        "study_path": [
            {
                "step": 1,
                "title": "HubSpot Marketing Software Fundamentals",
                "desc": "Complete the HubSpot Academy Marketing Software course. Covers the core product, contact lifecycle, and campaign basics.",
                "hours": 2,
            },
            {
                "step": 2,
                "title": "Email Marketing Course",
                "desc": "HubSpot Academy's email marketing course. Covers list management, deliverability, A/B testing, and reporting.",
                "hours": 1.5,
            },
            {
                "step": 3,
                "title": "Content Marketing Foundations",
                "desc": "The content marketing certification course. Useful for understanding how HubSpot connects blog, landing pages, and CTAs.",
                "hours": 2,
            },
            {
                "step": 4,
                "title": "HubSpot CRM Essentials",
                "desc": "Short course on contacts, companies, deals, and how the CRM ties to marketing activities.",
                "hours": 1,
            },
            {
                "step": 5,
                "title": "Practice Tests",
                "desc": "Use HubSpot Academy sample questions and any third-party practice sets. Focus on workflows, lifecycle stages, and reporting.",
                "hours": 3,
            },
            {
                "step": 6,
                "title": "Schedule and Take the Exam",
                "desc": "Book via HubSpot Academy. You have 3 hours for 75 questions; 80% is required to pass. Retakes are free after 12 hours.",
                "hours": 3,
            },
        ],
        "exam_topics": [
            {"topic": "Contact management & segmentation", "weight": "~20%", "desc": "Lists (static vs active), lifecycle stages, properties, deduplication."},
            {"topic": "Email marketing", "weight": "~25%", "desc": "Campaign creation, deliverability, A/B testing, open and click reporting."},
            {"topic": "Landing pages & forms", "weight": "~20%", "desc": "Building landing pages, progressive profiling, thank-you pages, conversion tracking."},
            {"topic": "Campaigns & reporting", "weight": "~20%", "desc": "Campaign grouping, attribution, dashboards, and interpreting results."},
            {"topic": "Automation & workflows", "weight": "~15%", "desc": "Workflow triggers, delays, branching, re-enrollment, and suppression logic."},
        ],
        "prep_tips": (
            "<p><strong>Use a free HubSpot portal.</strong> Sign up for a free HubSpot account and "
            "build at least one live workflow and one automated email sequence. The exam tests "
            "practical knowledge — hands-on time matters more than re-reading slides.</p>"
            "<p><strong>Know the lifecycle stage model cold.</strong> Questions about when a contact "
            "moves from Subscriber → Lead → MQL → SQL appear frequently. Understand "
            "both the default stages and how workflows interact with them.</p>"
            "<p><strong>Focus on active vs static lists.</strong> This distinction comes up in "
            "multiple question formats. Know when each is appropriate and how re-evaluation timing "
            "affects workflow enrollment.</p>"
            "<p><strong>Don’t skip reporting.</strong> Campaign attribution and multi-touch "
            "reporting are tested more than most candidates expect. Build a sample dashboard before "
            "the exam so the UI is familiar.</p>"
        ),
        "meta_title": "HubSpot Marketing Hub Certification Guide ({year}) | MarTechJobs",
        "meta_description": (
            "Complete study guide for the HubSpot Marketing Hub Certification: exam format, "
            "6-step study path, topic breakdown, and prep tips. Free cert, big career impact. "
            "Updated {year}."
        ),
    },
    "Marketo": {
        "cert_name": "Adobe Marketo Certified Expert",
        "provider": "Adobe",
        "cost": "$180 per attempt",
        "exam_format": "60 questions, 2 hours, 70% pass mark",
        "validity": "2 years",
        "difficulty": "Advanced",
        "intro": (
            "<p>The Adobe Marketo Certified Expert (MCE) is the gold-standard credential for "
            "marketing automation professionals. Unlike vendor certifications that test menu "
            "navigation, the MCE probes your understanding of smart campaign logic, the lead "
            "lifecycle model, and Marketo’s architecture — the things that separate "
            "someone who has configured Marketo from someone who can run it reliably at scale.</p>"
            "<p>Demand for MCE holders consistently outstrips supply. It appears as a preferred "
            "or required qualification in a significant share of senior Marketing Operations and "
            "Demand Generation postings — particularly at companies that run complex "
            "multi-touch programmes on Marketo Engage.</p>"
        ),
        "who_should_get": (
            "Marketo power users and administrators who build and maintain programmes daily, "
            "Marketing Automation Managers owning the full instance, RevOps practitioners who "
            "need to speak credibly about lead lifecycle and database management, and consultants "
            "who implement Marketo for clients."
        ),
        "study_path": [
            {
                "step": 1,
                "title": "Adobe’s Official Marketo Engage Core Concepts",
                "desc": "Start with the Adobe Experience League learning path for Marketo Engage. Covers programmes, smart campaigns, assets, and the lead database.",
                "hours": 4,
            },
            {
                "step": 2,
                "title": "Lead Lifecycle & Database Management Deep Dive",
                "desc": "Study lead scoring, lead lifecycle model, deduplication, and data management. These are heavily weighted on the exam.",
                "hours": 3,
            },
            {
                "step": 3,
                "title": "Smart Campaigns and Flow Steps Mastery",
                "desc": "Build a variety of smart campaigns in a sandbox: trigger vs batch, flow step ordering, wait steps, and advanced filters.",
                "hours": 4,
            },
            {
                "step": 4,
                "title": "Revenue Cycle Analytics",
                "desc": "Study the Revenue Cycle Model, Success Path Analyser, and how Marketo attributes pipeline. Understand RCM stages and transitions.",
                "hours": 2,
            },
            {
                "step": 5,
                "title": "Adobe Experience League Practice Exams",
                "desc": "Complete all available practice questions on Adobe Experience League. Time yourself and review every wrong answer in depth.",
                "hours": 5,
            },
            {
                "step": 6,
                "title": "Marketo Community Study Groups",
                "desc": "Join the Marketo Community (community.marketo.com) and search for MCE study threads. Real exam feedback from recent test-takers is invaluable.",
                "hours": 0,
            },
            {
                "step": 7,
                "title": "Schedule Exam via Pearson VUE",
                "desc": "Book online or at a Pearson VUE test centre. Allow 2 hours; 60 questions, 70% to pass.",
                "hours": 2,
            },
        ],
        "exam_topics": [
            {"topic": "Lead & data management", "weight": "~25%", "desc": "Lead database, deduplication, data hygiene, merging, lead scoring, and lifecycle model."},
            {"topic": "Email & landing page programmes", "weight": "~25%", "desc": "Email programmes, engagement programmes, landing page creation, forms, and A/B testing."},
            {"topic": "Smart campaigns", "weight": "~20%", "desc": "Trigger vs batch, smart list logic, flow steps, constraints, and campaign scheduling."},
            {"topic": "Reporting & analytics", "weight": "~15%", "desc": "Programme performance, Revenue Cycle Analytics, email performance reports, and attribution."},
            {"topic": "Administration", "weight": "~15%", "desc": "User management, CRM sync, webhooks, LaunchPoint integrations, and workspace/partition setup."},
        ],
        "prep_tips": (
            "<p><strong>Master smart campaign logic before anything else.</strong> Filter vs trigger, "
            "flow step ordering, and the interaction between smart list qualifiers are tested "
            "exhaustively. Build 10+ different campaign types in a sandbox if you can.</p>"
            "<p><strong>Know the Revenue Cycle Model inside out.</strong> RCM is where many candidates "
            "lose marks. Understand stage transitions, SLA tracking, and how the Success Path "
            "Analyser reads the model.</p>"
            "<p><strong>Use Adobe’s practice exams seriously.</strong> The question style on "
            "the real MCE is close to the official practice material. Do every question at least "
            "twice and understand the ‘why’ behind each wrong answer.</p>"
            "<p><strong>Review the integration layer.</strong> Salesforce sync behaviour, field "
            "mapping, and sync errors appear more often than candidates expect. Know what happens "
            "when a sync conflict occurs.</p>"
        ),
        "meta_title": "Adobe Marketo Certified Expert (MCE) Study Guide ({year}) | MarTechJobs",
        "meta_description": (
            "Complete prep guide for the Adobe Marketo Certified Expert exam: 7-step study path, "
            "topic breakdown, exam format, and what MCE holders are earning in live job data. "
            "Updated {year}."
        ),
    },
    "Salesforce Marketing Cloud": {
        "cert_name": "Salesforce Marketing Cloud Email Specialist",
        "provider": "Salesforce",
        "cost": "$200 per attempt (retakes $100)",
        "exam_format": "60 questions, 90 minutes, 65% pass mark",
        "validity": "Annual maintenance required",
        "difficulty": "Intermediate",
        "intro": (
            "<p>The Salesforce Marketing Cloud Email Specialist certification is the most "
            "sought-after SFMC credential for email marketers and Marketing Operations professionals. "
            "It validates that you can build and send at scale in Email Studio, manage data "
            "extensions, set up automation in Automation Studio, and apply deliverability best "
            "practices including Sender Authentication Package (SAP) configuration.</p>"
            "<p>Unlike some vendor certifications that focus on UI familiarity, the SFMC Email "
            "Specialist exam tests real operational knowledge: AMPscript fundamentals, SAP and "
            "deliverability concepts, and Journey Builder basics. This is why it carries genuine "
            "weight on a resume and in job descriptions.</p>"
        ),
        "who_should_get": (
            "Email marketers who use Salesforce Marketing Cloud as their primary sending platform, "
            "SFMC admins responsible for the email channel and deliverability, Marketing Automation "
            "Specialists transitioning from other platforms to SFMC, and anyone aiming for a "
            "full SFMC certification stack."
        ),
        "study_path": [
            {
                "step": 1,
                "title": "Trailhead SFMC Email Specialist Trail",
                "desc": "Complete the official Salesforce Trailhead Email Specialist trail. This covers the exam scope systematically and is the most efficient starting point.",
                "hours": 10,
            },
            {
                "step": 2,
                "title": "Email Studio Fundamentals",
                "desc": "Deep-dive into Email Studio: creating emails, content builder, subscriber management, and send classifications. Practice sending in a Dev org.",
                "hours": 3,
            },
            {
                "step": 3,
                "title": "Automation Studio & Journey Builder Basics",
                "desc": "Build a scheduled automation in Automation Studio and a simple journey in Journey Builder. Know the difference between the two and when to use each.",
                "hours": 4,
            },
            {
                "step": 4,
                "title": "AMPscript Fundamentals",
                "desc": "Learn AMPscript basics: attribute lookup, conditional content, and personalisation strings. You don’t need to be an expert, but basic syntax is tested.",
                "hours": 3,
            },
            {
                "step": 5,
                "title": "Sender Authentication Package (SPF/DKIM/DMARC)",
                "desc": "Study the SAP in depth: what it does, how it affects deliverability, how private domains and dedicated IPs work, and how IP warming operates.",
                "hours": 2,
            },
            {
                "step": 6,
                "title": "Trailhead Superbadge & Practice Exams",
                "desc": "Complete the Email Specialist Superbadge and use Focus on Force or Trailhead practice exams to simulate the real thing.",
                "hours": 6,
            },
        ],
        "exam_topics": [
            {"topic": "Email marketing best practices", "weight": "~24%", "desc": "CAN-SPAM/GDPR compliance, deliverability principles, list hygiene, and subscriber management."},
            {"topic": "Content creation & delivery", "weight": "~20%", "desc": "Email Studio, Content Builder, templates, personalisation, dynamic content, and AMPscript basics."},
            {"topic": "Marketing automation", "weight": "~20%", "desc": "Automation Studio activities, Journey Builder entries and exits, and triggered sends."},
            {"topic": "Subscriber data management", "weight": "~18%", "desc": "Data extensions, lists, sendable vs non-sendable DEs, suppression, and Subscriber Key."},
            {"topic": "Tracking & reporting", "weight": "~18%", "desc": "Send logs, tracking data views, deliverability metrics, and Datorama/Intelligence Reports basics."},
        ],
        "prep_tips": (
            "<p><strong>Trailhead is genuinely sufficient.</strong> Unlike some certs where the "
            "official materials are thin, the SFMC Email Specialist Trailhead trail covers the exam "
            "scope well. Complete it fully before supplementing with third-party resources.</p>"
            "<p><strong>Know the SAP inside out.</strong> Sender Authentication Package questions "
            "are some of the hardest on the exam and the most commonly missed. Understand what SAP "
            "includes (private domain, dedicated IP, reply mail management) and how each component "
            "affects deliverability.</p>"
            "<p><strong>Understand deliverability concepts, not just the settings.</strong> Questions "
            "test whether you understand ‘why’ — bounce codes, spam complaint rates, "
            "domain reputation — not just where to click. Know the difference between a soft "
            "and hard bounce and what SFMC does with each.</p>"
            "<p><strong>Do the Superbadge.</strong> The SFMC Email Specialist Superbadge on "
            "Trailhead forces you to apply everything end-to-end in a real org. Completing it "
            "solidifies the practical knowledge that separates exam-passers from actual competency.</p>"
        ),
        "meta_title": "Salesforce Marketing Cloud Email Specialist Cert Guide ({year}) | MarTechJobs",
        "meta_description": (
            "Complete study guide for the Salesforce Marketing Cloud Email Specialist certification: "
            "exam format, 6-step study path, topic breakdown, and SAP/deliverability tips. "
            "Updated {year}."
        ),
    },
    "Braze": {
        "cert_name": "Braze Marketer Certification",
        "provider": "Braze Learning",
        "cost": "Free",
        "exam_format": "~60 questions, multiple choice, 80% pass mark",
        "validity": "2 years",
        "difficulty": "Intermediate",
        "intro": (
            "<p>The Braze Marketer Certification is the credential that signals you can actually run "
            "lifecycle and CRM programmes on Braze &mdash; not just navigate the UI. It validates "
            "that you can segment audiences, orchestrate cross-channel journeys in Canvas, "
            "personalise with Liquid, and read results well enough to optimise. Those are exactly "
            "the skills hiring managers screen for in Lifecycle and Retention roles.</p>"
            "<p>Because Braze Learning makes the preparation courses and the exam free, the "
            "certification has strong ROI: a low time cost and a verifiable proof point that you "
            "understand the platform as a system, from data in to messages out.</p>"
        ),
        "who_should_get": (
            "Lifecycle marketers who own engagement programmes on Braze, CRM and retention managers "
            "responsible for cross-channel messaging, and marketing automation specialists who want "
            "a verified, employer-recognised proof of Braze competence."
        ),
        "study_path": [
            {
                "step": 1,
                "title": "Braze Learning: Platform Fundamentals",
                "desc": "Complete the foundational Braze Learning courses on the data model (users, attributes, custom events), segmentation, and the messaging channels.",
                "hours": 3,
            },
            {
                "step": 2,
                "title": "Building Journeys in Canvas Flow",
                "desc": "Work through the Canvas Flow courses: entry triggers, steps, delays, action paths, and conversion events. Build a multi-step journey in a workspace.",
                "hours": 4,
            },
            {
                "step": 3,
                "title": "Segmentation & Personalisation with Liquid",
                "desc": "Study segment building and Liquid personalisation, including default/fallback values and Connected Content. Practise rendering personalised content for several profiles.",
                "hours": 3,
            },
            {
                "step": 4,
                "title": "Channel Best Practices",
                "desc": "Review channel-specific best practices across email, push, in-app, and SMS, plus frequency capping, subscription groups, and Intelligent Timing.",
                "hours": 2,
            },
            {
                "step": 5,
                "title": "Reporting & Optimisation",
                "desc": "Learn how to read campaign and Canvas reporting, run A/B tests, and use control/holdout groups to measure incremental impact.",
                "hours": 2,
            },
            {
                "step": 6,
                "title": "Practice & Take the Exam",
                "desc": "Review the Braze Learning study materials, then sit the exam. It's roughly 60 multiple-choice questions with an 80% pass mark.",
                "hours": 3,
            },
        ],
        "exam_topics": [
            {"topic": "Segmentation & targeting", "weight": "~22%", "desc": "User attributes vs custom events, building reusable segments, and entry filters."},
            {"topic": "Canvas & Campaign orchestration", "weight": "~24%", "desc": "Canvas Flow steps, triggers, delays, action paths, and when to use Campaigns vs Canvas."},
            {"topic": "Personalisation & Liquid", "weight": "~20%", "desc": "Liquid templating, default/fallback values, Connected Content, and catalogs."},
            {"topic": "Channels & deliverability", "weight": "~18%", "desc": "Email, push, in-app, and SMS best practices, frequency capping, and subscription groups."},
            {"topic": "Reporting & optimisation", "weight": "~16%", "desc": "A/B testing, conversion events, holdout groups, and reading campaign results."},
        ],
        "prep_tips": (
            "<p><strong>Build in a real workspace.</strong> The exam rewards hands-on understanding. "
            "Build at least one multi-channel Canvas with branching, a delay, and a conversion event "
            "before you sit it.</p>"
            "<p><strong>Know attributes vs events cold.</strong> Modelling questions &mdash; when "
            "something is a user attribute versus a custom event, and how that drives segments and "
            "triggers &mdash; come up repeatedly.</p>"
            "<p><strong>Practise Liquid with fallbacks.</strong> Be comfortable writing personalised "
            "content with default values so a missing attribute doesn&rsquo;t break the message.</p>"
            "<p><strong>Understand measurement.</strong> Know the difference between in-message "
            "engagement and incremental impact measured with a holdout &mdash; it shows up in the "
            "reporting questions.</p>"
        ),
        "meta_title": "Braze Marketer Certification Guide ({year}) | MarTechJobs",
        "meta_description": (
            "Complete study guide for the Braze Marketer Certification: exam format, study path, "
            "topic breakdown, and prep tips. Free cert that signals real lifecycle competence. "
            "Updated {year}."
        ),
    },
    "Klaviyo": {
        "cert_name": "Klaviyo Product Certification",
        "provider": "Klaviyo",
        "cost": "Free",
        "exam_format": "~40 questions, 80% pass mark, 1 hour",
        "validity": "1 year",
        "difficulty": "Beginner–Intermediate",
        "intro": (
            "<p>Klaviyo certifications are among the most relevant credentials for ecommerce email "
            "and retention roles. The Product Certification validates that you can navigate the "
            "platform, build flows and campaigns, segment on store data, and read the metrics that "
            "matter &mdash; exactly what agencies and ecommerce brands expect from an email "
            "specialist.</p>"
            "<p>Klaviyo offers a track rather than a single exam: the Product Certification is the "
            "core credential, alongside more focused certs such as Email Marketing and "
            "Deliverability. All preparation runs through Klaviyo Academy for free, making this a "
            "low-cost, high-signal addition to a CV.</p>"
        ),
        "who_should_get": (
            "Email and lifecycle marketers working in ecommerce, agency email specialists who manage "
            "Klaviyo for multiple clients, and retention marketers who want a verified proof point "
            "for the platform they use daily."
        ),
        "study_path": [
            {
                "step": 1,
                "title": "Klaviyo Academy: Platform Basics",
                "desc": "Complete the foundational Klaviyo Academy courses on the account structure, profiles, metrics, lists vs segments, and integrations.",
                "hours": 2,
            },
            {
                "step": 2,
                "title": "Flows & Automation",
                "desc": "Study and build the core flows: welcome series, abandoned cart, browse abandonment, post-purchase, and win-back, including triggers and flow filters.",
                "hours": 3,
            },
            {
                "step": 3,
                "title": "Segmentation & Data",
                "desc": "Learn dynamic segments, event-based segmentation, and predictive analytics (CLV, churn risk). Build a few behaviour-driven segments off store data.",
                "hours": 2,
            },
            {
                "step": 4,
                "title": "Deliverability",
                "desc": "Cover engagement-based sending, sunset flows, warming, and managing unengaged subscribers. Understand SMS consent and compliance basics.",
                "hours": 2,
            },
            {
                "step": 5,
                "title": "Campaign Strategy & Content",
                "desc": "Study campaign building, A/B testing subject lines and content, and reading reporting (attributed revenue, revenue per recipient).",
                "hours": 2,
            },
            {
                "step": 6,
                "title": "Practice & Take the Exam",
                "desc": "Review the Klaviyo Academy materials, then sit the certification exam: roughly 40 questions in an hour with an 80% pass mark.",
                "hours": 2,
            },
        ],
        "exam_topics": [
            {"topic": "Account & platform fundamentals", "weight": "~20%", "desc": "Profiles, metrics, lists vs segments, and integrations/data sync."},
            {"topic": "Flows & automation", "weight": "~24%", "desc": "Core ecommerce flows, triggers, flow filters, and conditional splits."},
            {"topic": "Segmentation & data", "weight": "~20%", "desc": "Dynamic segments, event-based segmentation, and predictive analytics."},
            {"topic": "Campaigns & content", "weight": "~18%", "desc": "Campaign building, A/B testing, and dynamic/personalised content."},
            {"topic": "Deliverability & reporting", "weight": "~18%", "desc": "Engagement-based sending, list health, attribution, and revenue per recipient."},
        ],
        "prep_tips": (
            "<p><strong>Klaviyo Academy is free and sufficient.</strong> The official courses cover "
            "the exam scope well &mdash; complete the relevant tracks fully before reaching for "
            "third-party material.</p>"
            "<p><strong>Build a real flow.</strong> Connect a test store and build a welcome series "
            "and an abandoned-cart flow with a proper flow filter. Hands-on time makes the "
            "platform questions easy.</p>"
            "<p><strong>Know the metrics.</strong> Be able to explain attributed revenue, revenue "
            "per recipient, and how Klaviyo&rsquo;s attribution window works &mdash; these come up "
            "more than candidates expect.</p>"
            "<p><strong>Understand list health.</strong> Sunset flows and engagement-based sending "
            "are tested; know why pruning unengaged subscribers protects deliverability.</p>"
        ),
        "meta_title": "Klaviyo Product Certification Guide ({year}) | MarTechJobs",
        "meta_description": (
            "Complete study guide for the Klaviyo Product Certification: exam format, study path, "
            "topic breakdown, and prep tips. Free via Klaviyo Academy. Updated {year}."
        ),
    },
    "Salesforce": {
        "cert_name": "Salesforce Certified Administrator",
        "provider": "Salesforce",
        "cost": "$200 (retake $100)",
        "exam_format": "60 multiple-choice questions, 105 minutes, 65% pass mark",
        "validity": "Maintained via release exams (3x/year)",
        "difficulty": "Intermediate",
        "intro": (
            "<p>The Salesforce Certified Administrator is the highest-leverage entry credential in "
            "the entire Salesforce ecosystem. It proves you can configure and govern an org &mdash; "
            "the data model, automation with Flow, the security model, data management, and "
            "reporting &mdash; which is why it appears as a preferred or required qualification "
            "across MarTech, RevOps, and marketing operations job descriptions where someone owns "
            "Salesforce configuration.</p>"
            "<p>For career changers and marketers who already touch Salesforce, the Admin cert is "
            "the credential that unlocks the rest of the ecosystem. Preparation runs largely through "
            "free Trailhead content, so the main investment is time and the exam fee &mdash; a "
            "strong return for how widely the credential is recognised.</p>"
        ),
        "who_should_get": (
            "Aspiring Salesforce administrators, marketing and RevOps professionals who own "
            "Salesforce configuration, and career changers using the Admin cert as their entry "
            "point into the Salesforce ecosystem."
        ),
        "study_path": [
            {
                "step": 1,
                "title": "Trailhead: Admin Beginner Trail",
                "desc": "Complete the Admin Beginner trail on Trailhead. Covers the data model, objects and fields, the UI, and core navigation systematically.",
                "hours": 12,
            },
            {
                "step": 2,
                "title": "Trailhead: Admin Intermediate Trail",
                "desc": "Work through the Admin Intermediate trail: more advanced configuration, reporting, and process automation across objects.",
                "hours": 12,
            },
            {
                "step": 3,
                "title": "Master Flow",
                "desc": "Go deep on Flow Builder: record-triggered vs screen flows, before- vs after-save, and the order of execution. Build several flows in a Developer org.",
                "hours": 6,
            },
            {
                "step": 4,
                "title": "Security Model & Data Management",
                "desc": "Study org-wide defaults, role hierarchy, sharing rules, profiles vs permission sets, and field-level security; plus data import/export, duplicate rules, and validation rules.",
                "hours": 6,
            },
            {
                "step": 5,
                "title": "Trailhead Superbadges",
                "desc": "Complete relevant admin Superbadges. They force you to apply configuration end-to-end in a real org, which is the best preparation for scenario questions.",
                "hours": 8,
            },
            {
                "step": 6,
                "title": "Official Practice Exam",
                "desc": "Take the official Salesforce Administrator practice exam, review every wrong answer in depth, and revisit weak topics on Trailhead.",
                "hours": 4,
            },
            {
                "step": 7,
                "title": "Schedule via Kryterion/Pearson VUE",
                "desc": "Book the exam through Kryterion or Pearson VUE (online or test centre). Allow 105 minutes for 60 questions; 65% is required to pass.",
                "hours": 2,
            },
        ],
        "exam_topics": [
            {"topic": "Configuration & setup", "weight": "~20%", "desc": "Company settings, user management, UI configuration, and the AppExchange."},
            {"topic": "Object Manager & Lightning App Builder", "weight": "~20%", "desc": "Standard/custom objects, fields, relationships, record types, page layouts, and Lightning pages."},
            {"topic": "Sales, marketing, service & support apps", "weight": "~23%", "desc": "Lead conversion, opportunities, the sales/marketing process, and case management basics."},
            {"topic": "Workflow & process automation", "weight": "~16%", "desc": "Flow Builder, record-triggered vs screen flows, approvals, and the order of execution."},
            {"topic": "Data & analytics management", "weight": "~14%", "desc": "Data import/export, duplicate and validation rules, report types, and dashboards."},
            {"topic": "Productivity & collaboration", "weight": "~7%", "desc": "Activities, mobile, and collaboration features that support day-to-day users."},
        ],
        "prep_tips": (
            "<p><strong>Trailhead and Superbadges are the core.</strong> The free Admin trails plus "
            "Superbadges cover the exam scope and force hands-on application. Complete them fully "
            "before buying third-party practice material.</p>"
            "<p><strong>Know the security model cold.</strong> Org-wide defaults, role hierarchy, "
            "sharing rules, profiles vs permission sets, and field-level security are heavily tested "
            "and commonly missed. Reason from &lsquo;lock down, then open up&rsquo;.</p>"
            "<p><strong>Understand Flow.</strong> Record-triggered vs screen flows, before- vs "
            "after-save, and the basics of the order of execution show up across automation "
            "questions. Build flows in a Developer org rather than just reading about them.</p>"
            "<p><strong>Take the official practice exam.</strong> Its question style closely matches "
            "the real exam. Review every wrong answer and revisit the weak topic on Trailhead before "
            "you book.</p>"
        ),
        "meta_title": "Salesforce Certified Administrator Study Guide ({year}) | MarTechJobs",
        "meta_description": (
            "Complete prep guide for the Salesforce Certified Administrator exam: exam format, "
            "study path, topic breakdown with official weightings, and Trailhead/Flow/security tips. "
            "Updated {year}."
        ),
    },
}


class Command(BaseCommand):
    help = "Create/refresh per-tool CertificationGuide content for flagship certs (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument('--overwrite', action='store_true',
                            help="Overwrite existing guide content (otherwise only fills blanks).")

    def handle(self, *args, **options):
        overwrite = options['overwrite']
        martech_cat, _ = Category.objects.get_or_create(name="MarTech", defaults={"slug": "martech"})

        year = "2026"

        for tool_name, data in GUIDES.items():
            tool = (Tool.objects.filter(name__iexact=tool_name).first()
                    or Tool.objects.filter(slug=slugify(tool_name)).first())
            if not tool:
                tool = Tool.objects.create(name=tool_name, slug=slugify(tool_name), category=martech_cat)
                self.stdout.write(self.style.WARNING(f"  created missing Tool: {tool_name}"))

            defaults = {
                "slug": tool.slug,
                "cert_name": data["cert_name"],
                "provider": data.get("provider", ""),
                "cost": data.get("cost", ""),
                "exam_format": data.get("exam_format", ""),
                "validity": data.get("validity", ""),
                "difficulty": data.get("difficulty", ""),
                "intro": data.get("intro", ""),
                "who_should_get": data.get("who_should_get", ""),
                "study_path": data.get("study_path", []),
                "exam_topics": data.get("exam_topics", []),
                "prep_tips": data.get("prep_tips", ""),
                "meta_title": data.get("meta_title", "").replace("{year}", year),
                "meta_description": data.get("meta_description", "").replace("{year}", year),
                "is_published": True,
            }
            guide, created = CertificationGuide.objects.get_or_create(tool=tool, defaults=defaults)
            if created:
                self.stdout.write(self.style.SUCCESS(
                    f"  + {tool.name} cert guide  /{tool.slug}-certification/"))
            elif overwrite:
                for k, v in defaults.items():
                    setattr(guide, k, v)
                guide.save()
                self.stdout.write(self.style.SUCCESS(f"  ~ {tool.name} cert guide refreshed"))
            else:
                self.stdout.write(f"  = {tool.name} cert guide exists (use --overwrite to refresh)")

        self.stdout.write(self.style.SUCCESS("Done."))

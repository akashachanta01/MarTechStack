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
    "Braze": {
        "intro": (
            "<p>Braze interviews for Lifecycle Marketing, Marketing Automation, and CRM roles "
            "centre on one thing: can you orchestrate the right message across the right channel "
            "at the right moment, at scale, without burning your audience? Hiring managers probe "
            "your mental model of Canvas, segmentation, and the underlying data &mdash; not just "
            "whether you can drag steps onto a canvas.</p>"
            "<p>The questions below run from platform fundamentals through orchestration, "
            "personalisation, data/integrations, and measurement. For each, we&rsquo;ve noted "
            "what a strong answer demonstrates rather than a textbook definition.</p>"
        ),
        "meta_title": "Braze Interview Questions ({year}) — 17 Real Questions + Answers | MarTechJobs",
        "meta_description": (
            "17 real Braze interview questions for Lifecycle, CRM & Marketing Automation roles, "
            "with what hiring managers look for in each answer. Built from live Braze job data. "
            "Updated {year}."
        ),
        "questions": [
            {"category": "Platform Fundamentals", "items": [
                {"q": "What's the difference between a Campaign and a Canvas in Braze, and when do you reach for each?",
                 "a": "<p>A <strong>Campaign</strong> is a single-step (or single-channel) send &mdash; good for a one-off blast or a simple triggered message. A <strong>Canvas</strong> is a multi-step, multi-channel journey with branching, delays, and audience paths. Strong candidates say they default to Canvas for anything with logic or sequencing, and reserve Campaigns for genuinely simple sends &mdash; and they mention Canvas Flow as the current builder.</p>"},
                {"q": "How do segments work in Braze, and how do they differ from filters inside a Canvas?",
                 "a": "<p>A <strong>segment</strong> is a reusable, named audience defined by filters on attributes, events, and engagement; it updates continuously as users qualify or drop out. Inside a Canvas you can additionally apply <strong>entry filters</strong> and <strong>audience paths</strong>. The signal: knowing that segments are reusable and live, and that over-segmenting creates maintenance debt.</p>"},
                {"q": "Explain the difference between a user attribute and a custom event.",
                 "a": "<p>A <strong>custom attribute</strong> describes a <em>state</em> of the user (plan tier, lifetime value, city); a <strong>custom event</strong> records that something <em>happened</em> at a point in time (purchased, completed onboarding). Strong answers note that events can carry properties, that you trigger Canvases off events, and that modelling something as the wrong type (event vs attribute) causes pain later.</p>"},
                {"q": "What are subscription groups and why do they matter?",
                 "a": "<p>Subscription groups let users opt in/out of specific message <em>types</em> (e.g. promotions vs transactional) per channel, rather than a single global on/off. The mature answer ties this to compliance and to respecting preferences as a deliverability and trust lever &mdash; not just a legal checkbox.</p>"},
            ]},
            {"category": "Cross-Channel Orchestration", "items": [
                {"q": "Walk me through how you'd build a cross-channel onboarding journey in Canvas Flow.",
                 "a": "<p>Look for: an event-triggered entry, channel steps (push/email/in-app) with <strong>action paths</strong> and delays, fallbacks when a user has no push permission, and an exit/conversion event. The strong candidate sequences channels by cost and intrusiveness (in-app/email before SMS) and builds in a goal so the journey stops when the user activates.</p>"},
                {"q": "How do you coordinate push, email, in-app, and SMS so a user isn't hit on all of them at once?",
                 "a": "<p>Strong answers describe channel prioritisation logic, decision splits on channel reachability, and treating cross-channel coordination as a design problem &mdash; plus global <strong>frequency capping</strong> as a backstop. They distinguish &lsquo;which channel&rsquo; from &lsquo;how often&rsquo;.</p>"},
                {"q": "How does frequency capping work in Braze, and what are its limits?",
                 "a": "<p>Frequency caps limit how many messages a user receives over a rolling window, globally or per channel/tag. The senior signal: knowing that caps are a safety net, not a strategy, that transactional/critical messages can be exempted, and that caps interact with Canvas priority.</p>"},
                {"q": "What is Intelligent Timing and when would you use it?",
                 "a": "<p>Intelligent Timing sends to each user at the time they&rsquo;re individually most likely to engage, based on their historical behaviour, instead of one fixed send time. Strong candidates note it&rsquo;s most useful for non-time-sensitive sends and that they&rsquo;d A/B test it against a fixed time rather than assuming a lift.</p>"},
            ]},
            {"category": "Personalization & Liquid", "items": [
                {"q": "How do you personalise messages with Liquid in Braze?",
                 "a": "<p>Look for comfort with Liquid attribute and event/property references, conditional logic (<code>{% if %}</code>), and crucially <strong>default values</strong> so a missing attribute doesn&rsquo;t render an empty or broken message. The best answers stress testing across multiple user profiles.</p>"},
                {"q": "What is Connected Content and when would you use it over stored attributes?",
                 "a": "<p>Connected Content pulls data from an external API at send time and renders it into the message. Use it when data is too volatile or large to sync as attributes (live prices, inventory, weather). The mature answer flags latency/availability risk and the need for fallbacks if the endpoint fails.</p>"},
                {"q": "How do Catalogs help with personalisation at scale?",
                 "a": "<p>Catalogs store structured reference data (products, content, locations) inside Braze that you reference in Liquid, avoiding an external call per send. Strong candidates contrast Catalogs (semi-static reference data) with Connected Content (live external data) and pick based on volatility and volume.</p>"},
            ]},
            {"category": "Data & Integrations", "items": [
                {"q": "How does event and attribute data get into Braze?",
                 "a": "<p>Via the SDKs (client-side events/attributes), the REST API / server-to-server (<code>/users/track</code>), and partner integrations (CDP, Segment, etc.). The signal: knowing which path suits which data, that server-side is more reliable for revenue/critical events, and that client and server data must be reconciled on a consistent identifier.</p>"},
                {"q": "What is Braze Currents and when would you use it?",
                 "a": "<p>Currents is the streaming data <strong>export</strong> &mdash; it pushes engagement and message events to a data warehouse or analytics tool in near real time. Strong candidates use it to close the loop on attribution and build downstream reporting Braze&rsquo;s native dashboards can&rsquo;t.</p>"},
                {"q": "Explain user identity and aliasing in Braze.",
                 "a": "<p>Look for understanding of the <code>external_id</code> as the durable identity, anonymous users created by the SDK before login, and <strong>user aliasing</strong> / identify calls to merge an anonymous profile into a known one. Getting this wrong causes duplicate profiles and broken targeting &mdash; a great candidate raises that risk unprompted.</p>"},
            ]},
            {"category": "Deliverability & Measurement", "items": [
                {"q": "How do you run an A/B test inside a Canvas, and what would you measure?",
                 "a": "<p>Strong answers use a variant/experiment step or message variants, define a single primary <strong>conversion event</strong> up front, ensure adequate sample size, and read results against conversion &mdash; not opens. They avoid testing five things at once and know to let the test reach significance.</p>"},
                {"q": "What are control/holdout groups and why use them?",
                 "a": "<p>A holdout withholds messages from a random slice of the audience so you can measure the <em>incremental</em> impact of a campaign or the whole program, not just in-message engagement. The senior signal: insisting on a global holdout to prove lifecycle messaging actually drives revenue rather than taking credit for organic behaviour.</p>"},
                {"q": "A campaign's engagement is dropping over time. How do you reduce message fatigue?",
                 "a": "<p>Look for: tightening segmentation and triggers so messages are more relevant, frequency capping, Intelligent Timing, subscription-group hygiene, sunsetting unengaged users from high-frequency journeys, and validating with a holdout. Methodical diagnosis over &lsquo;send more&rsquo;.</p>"},
            ]},
        ],
        "prep_tips": (
            "<p><strong>Build a real Canvas.</strong> Spin up a free/dev Braze workspace and build a "
            "multi-channel onboarding Canvas with branching, a delay, and a conversion event. "
            "Interviewers can tell within two questions whether you&rsquo;ve actually orchestrated "
            "journeys or only read about them.</p>"
            "<p><strong>Lead with the data model.</strong> Frame answers around attributes vs events, "
            "external_id, and segmentation. Showing you understand how data flows in (SDK/API) and "
            "out (Currents) signals you can run Braze, not just click it.</p>"
            "<p><strong>Have a measurement story.</strong> One concrete example where a holdout or a "
            "clean conversion event changed a decision separates lifecycle strategists from "
            "campaign senders.</p>"
        ),
    },
    "Klaviyo": {
        "intro": (
            "<p>Klaviyo interviews for Email, Lifecycle, and Retention Marketing roles are "
            "ecommerce-first. Hiring managers want to see that you can turn store and behavioural "
            "data into automated flows that drive revenue per recipient &mdash; and that you keep "
            "a list healthy enough to actually reach the inbox. Expect a blend of hands-on platform "
            "questions and revenue-focused scenarios.</p>"
            "<p>The questions below run from fundamentals through flows, segmentation, deliverability, "
            "and reporting. For each, we&rsquo;ve noted what a strong answer demonstrates rather than "
            "a textbook definition.</p>"
        ),
        "meta_title": "Klaviyo Interview Questions ({year}) — 14 Real Questions + Answers | MarTechJobs",
        "meta_description": (
            "14 real Klaviyo interview questions for Email, Lifecycle & Retention roles, with what "
            "hiring managers look for in each answer. Built from live Klaviyo job data. "
            "Updated {year}."
        ),
        "questions": [
            {"category": "Platform Fundamentals", "items": [
                {"q": "What's the difference between a List and a Segment in Klaviyo?",
                 "a": "<p>A <strong>List</strong> is a static, manually managed group (people you added or who signed up to it); a <strong>Segment</strong> is a dynamic, rule-based group that updates automatically as profiles meet or stop meeting conditions. Strong candidates default to segments for targeting and reserve lists for explicit opt-ins, and they note segments re-evaluate continuously.</p>"},
                {"q": "How do profiles and metrics work in Klaviyo?",
                 "a": "<p>A <strong>profile</strong> is the person; <strong>metrics</strong> are the events Klaviyo tracks about them (Placed Order, Viewed Product, Opened Email), usually synced from the store. The signal: understanding that metrics &mdash; with their properties and values &mdash; are what you build flows and segments on, not just email engagement.</p>"},
                {"q": "When do you use a Flow vs a Campaign?",
                 "a": "<p>A <strong>Campaign</strong> is a one-time, scheduled send to a chosen audience (a newsletter, a promo). A <strong>Flow</strong> is automated and triggered by an event, profile action, or date, running per-individual. Strong candidates say the bulk of revenue should come from well-built flows, with campaigns layered on top for timely moments.</p>"},
            ]},
            {"category": "Flows & Automation", "items": [
                {"q": "Which core ecommerce flows would you build first, and why?",
                 "a": "<p>Look for the revenue-driving set: <strong>welcome series</strong>, <strong>abandoned cart</strong>, <strong>browse abandonment</strong>, <strong>post-purchase</strong>, and <strong>win-back</strong>. Strong candidates prioritise abandoned cart and welcome first (highest intent/revenue), and tie each flow to a specific trigger metric rather than listing them generically.</p>"},
                {"q": "How do flow triggers and flow filters differ?",
                 "a": "<p>A <strong>trigger</strong> is the event that starts a person into the flow (e.g. Checkout Started); <strong>flow filters</strong> and <strong>trigger filters</strong> control who actually proceeds and prevent re-entry or messaging people who&rsquo;ve since converted. The senior signal: using filters to avoid emailing someone an abandoned-cart series after they&rsquo;ve already purchased.</p>"},
                {"q": "How would you design an abandoned-cart flow that doesn't annoy people?",
                 "a": "<p>Strong answers: trigger on Started Checkout, add conditional splits and a flow filter that exits anyone who has placed an order, space messages with sensible delays, and cap the series length. Bonus for testing incentive vs no-incentive and measuring incremental revenue, not just opens.</p>"},
            ]},
            {"category": "Segmentation & Data", "items": [
                {"q": "How do you use Klaviyo's predictive analytics?",
                 "a": "<p>Klaviyo predicts <strong>CLV</strong>, expected next order date, and <strong>churn risk</strong> for profiles with enough history. Strong candidates segment on these (e.g. high-value-at-risk for a win-back, predicted-next-order for replenishment) and acknowledge the data thresholds before predictions are reliable.</p>"},
                {"q": "How do dynamic segments and event-based segmentation work?",
                 "a": "<p>Dynamic segments combine profile properties and metric/event conditions (&lsquo;placed 2+ orders in 90 days&rsquo;, &lsquo;viewed a product but didn&rsquo;t buy&rsquo;) and update automatically. The signal: building behaviour-driven segments off metrics rather than static demographics, and using them as flow filters and campaign audiences.</p>"},
                {"q": "How does Klaviyo's Shopify/ecommerce data sync support segmentation?",
                 "a": "<p>The integration syncs orders, products, and browsing events as metrics, plus catalog data for product blocks. Strong candidates use that synced data for replenishment, category-based segmentation, and dynamic product feeds &mdash; and they sanity-check that the integration is actually passing the events they rely on.</p>"},
            ]},
            {"category": "Deliverability & List Health", "items": [
                {"q": "What is a sunset flow and why does it matter?",
                 "a": "<p>A <strong>sunset flow</strong> identifies chronically unengaged subscribers, gives them a last-chance message, and then suppresses them. The mature answer ties this to sender reputation: mailing dead addresses drags inbox placement for everyone, so pruning protects deliverability and is worth the list-size hit.</p>"},
                {"q": "How does engagement-based sending protect deliverability?",
                 "a": "<p>By targeting recent engagers and gradually re-including lapsed ones rather than blasting the whole list, you keep open/click rates and reputation high. Strong candidates describe <strong>warming</strong> a new account/domain by starting with the most engaged segment and ramping volume, and managing unengaged subscribers separately.</p>"},
                {"q": "What do you need to get right for SMS in Klaviyo?",
                 "a": "<p>Explicit <strong>consent</strong> collected compliantly (TCPA/local rules), separate SMS subscription, clear opt-out handling, and respecting quiet hours and frequency. The signal: treating SMS consent as distinct from email consent and never assuming an email opt-in covers SMS.</p>"},
            ]},
            {"category": "Reporting & Revenue", "items": [
                {"q": "How does Klaviyo attribute revenue, and what does revenue per recipient tell you?",
                 "a": "<p>Klaviyo attributes orders to a message within a conversion window after open/click. <strong>Revenue per recipient (RPR)</strong> normalises revenue by audience size so you can compare sends of different sizes. Strong candidates lead with RPR and attributed revenue over open rate, and know the attribution window is configurable.</p>"},
                {"q": "How do you use benchmarks and A/B testing to improve performance?",
                 "a": "<p>Look for: comparing against Klaviyo&rsquo;s industry benchmarks to spot weak flows, then A/B testing subject lines and content one variable at a time, reading results on conversion/RPR with adequate sample size. The senior signal is iterating on flows continuously rather than treating them as set-and-forget.</p>"},
            ]},
        ],
        "prep_tips": (
            "<p><strong>Build real flows.</strong> Use a free Klaviyo account connected to a test "
            "store and build a welcome series and an abandoned-cart flow with a proper flow filter. "
            "Interviewers can tell quickly whether you&rsquo;ve shipped flows or only studied them.</p>"
            "<p><strong>Speak in revenue.</strong> Frame answers around attributed revenue and "
            "revenue per recipient, not open rates. Knowing the metrics that matter for ecommerce "
            "retention is the clearest competence signal.</p>"
            "<p><strong>Know list health cold.</strong> Sunset flows, engagement-based sending, and "
            "consent handling come up constantly &mdash; have a concrete story about protecting "
            "deliverability while keeping the list productive.</p>"
        ),
    },
    "Salesforce": {
        "intro": (
            "<p>Salesforce Administrator interviews test whether you can configure and govern an org "
            "safely &mdash; data model, automation, security, and reporting &mdash; not just where "
            "the buttons are. For MarTech and RevOps roles, the admin owns the system of record that "
            "everything else syncs to, so hiring managers probe your judgement about declarative "
            "design and the order of operations.</p>"
            "<p>(Note: this guide covers core Salesforce Administrator / CRM Admin work, not "
            "Salesforce Marketing Cloud, which is a separate platform and guide.) The questions below "
            "run from core admin through automation, data, security, and reporting/lifecycle. For "
            "each, we&rsquo;ve noted what a strong answer demonstrates.</p>"
        ),
        "meta_title": "Salesforce Admin Interview Questions ({year}) — 15 Real Questions + Answers | MarTechJobs",
        "meta_description": (
            "15 real Salesforce Administrator interview questions covering the data model, Flow, "
            "security, and reporting, with what hiring managers look for. Built from live Salesforce "
            "job data. Updated {year}."
        ),
        "questions": [
            {"category": "Core Admin", "items": [
                {"q": "Explain the difference between a lookup and a master-detail relationship.",
                 "a": "<p>A <strong>lookup</strong> is a loose link; the child can exist independently and deleting the parent doesn&rsquo;t delete the child. A <strong>master-detail</strong> is tightly coupled: the child inherits the parent&rsquo;s sharing/security, is deleted with the parent (cascade), and enables roll-up summary fields. Strong candidates mention roll-ups and ownership inheritance as the deciding factors.</p>"},
                {"q": "When would you use record types, and what do they control?",
                 "a": "<p>Record types let one object serve different business processes &mdash; they drive available picklist values and which page layout a user sees, in combination with their profile. The signal: not over-using record types where a simple picklist or layout would do, and knowing they pair with page layout assignments.</p>"},
                {"q": "What's the difference between a profile and a permission set?",
                 "a": "<p>A <strong>profile</strong> sets baseline access and (historically) one per user; <strong>permission sets</strong> grant additional access on top, assigned to many users without changing their profile. The senior answer favours a minimal-profile + permission-set (and permission-set-group) model for maintainability, rather than cloning profiles endlessly.</p>"},
            ]},
            {"category": "Automation", "items": [
                {"q": "How do you decide when to use Flow versus other automation tools?",
                 "a": "<p>Salesforce now steers everything to <strong>Flow</strong>; Workflow Rules and Process Builder are retired/deprecated for new builds. Strong candidates default to Flow, reserve Apex for genuinely complex logic Flow can&rsquo;t handle, and can articulate <em>why</em> consolidating on Flow reduces maintenance debt.</p>"},
                {"q": "What's the difference between a record-triggered flow and a screen flow?",
                 "a": "<p>A <strong>record-triggered flow</strong> runs automatically on create/update/delete with no UI; a <strong>screen flow</strong> guides a user through steps in the interface. The signal: matching the type to the need &mdash; background automation vs guided user interaction &mdash; and knowing record-triggered flows can run before- or after-save.</p>"},
                {"q": "Give me the basics of the order of execution. Why does it matter?",
                 "a": "<p>Look for awareness that on save Salesforce runs things in a set sequence &mdash; validation rules, before-save flows, Apex before triggers, duplicate rules, after-save flows/triggers, roll-ups, and so on. Strong candidates use this to debug &lsquo;why did my automation overwrite that field&rsquo; problems and to avoid conflicting automations.</p>"},
            ]},
            {"category": "Data Management", "items": [
                {"q": "How do you handle a large data import safely?",
                 "a": "<p>Strong answers: choose the right tool (Data Import Wizard for simple loads, Data Loader for volume/more objects), map fields carefully, use an external ID to upsert and avoid duplicates, test in a sandbox first, and consider deactivating noisy automation during the load. Methodical over &lsquo;just import the CSV&rsquo;.</p>"},
                {"q": "How do duplicate rules and matching rules work together?",
                 "a": "<p>A <strong>matching rule</strong> defines how records are compared; a <strong>duplicate rule</strong> decides what happens when a match is found (block or alert) on create/edit. The signal: configuring both to keep the database clean at point of entry, and knowing they don&rsquo;t retroactively dedupe existing data.</p>"},
                {"q": "When do you use a validation rule, and what's the trade-off?",
                 "a": "<p>Validation rules enforce data quality by blocking saves that don&rsquo;t meet criteria. The mature answer weighs strictness against user friction and integration breakage &mdash; too many hard rules frustrate users and can fail API/integration writes &mdash; and considers required fields or automation as gentler alternatives.</p>"},
            ]},
            {"category": "Security & Access", "items": [
                {"q": "Explain org-wide defaults and the role hierarchy.",
                 "a": "<p><strong>Org-wide defaults (OWD)</strong> set the baseline record access (Private, Public Read Only, etc.); the <strong>role hierarchy</strong> then opens access upward so managers see their subordinates&rsquo; records. Strong candidates describe locking down with OWD first, then opening access deliberately &mdash; not the other way around.</p>"},
                {"q": "When would you use sharing rules versus the role hierarchy?",
                 "a": "<p>Sharing rules grant access <em>laterally</em> &mdash; to peers, other teams, or groups the hierarchy doesn&rsquo;t cover. The signal: using OWD + hierarchy for the default vertical model and sharing rules (and manual/Apex sharing) for exceptions, rather than loosening OWD for everyone.</p>"},
                {"q": "What is field-level security and how does it relate to layouts?",
                 "a": "<p>Field-level security (FLS) controls whether a user can see/edit a field <em>at all</em>, enforced everywhere including reports and the API; page layouts only control visibility on a given screen. Strong candidates stress that hiding a field on a layout is not security &mdash; FLS is.</p>"},
            ]},
            {"category": "Reporting & Lifecycle", "items": [
                {"q": "What's a report type and why does it matter?",
                 "a": "<p>A <strong>report type</strong> defines which objects and fields are available to a report and how related objects join (with vs without related records). The signal: knowing that a missing field in a report usually means the wrong or a needed custom report type, and that report types gate cross-object reporting.</p>"},
                {"q": "Walk me through lead conversion. What happens to the data?",
                 "a": "<p>On conversion a Lead maps to a Contact, an Account, and optionally an Opportunity, with field mapping configured by the admin. Strong candidates mention controlling the field mapping, handling duplicates at conversion, and that the lead becomes read-only/converted rather than deleted.</p>"},
                {"q": "How do you safely deploy changes using sandboxes and change sets?",
                 "a": "<p>Build and test in a <strong>sandbox</strong>, then move metadata to production via <strong>change sets</strong> (or a tool like a managed deployment/Git-based pipeline). The mature answer covers validating the deployment, coordinating timing/comms, and having a rollback plan &mdash; not configuring directly in production.</p>"},
            ]},
        ],
        "prep_tips": (
            "<p><strong>Get hands-on in a Developer org.</strong> Spin up a free Salesforce Developer "
            "edition and build a record-triggered Flow, a validation rule, and a custom report type. "
            "Interviewers can tell quickly whether you&rsquo;ve configured an org or only studied "
            "Trailhead modules.</p>"
            "<p><strong>Know the security model cold.</strong> OWD, role hierarchy, sharing rules, "
            "profiles vs permission sets, and field-level security come up in almost every admin "
            "interview &mdash; be able to reason from &lsquo;lock down, then open up&rsquo;.</p>"
            "<p><strong>Default to Flow and explain why.</strong> Showing you understand the move to "
            "Flow, record-triggered vs screen flows, and the basics of order of execution signals "
            "you build automation that won&rsquo;t fight itself.</p>"
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

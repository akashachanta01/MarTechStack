import os
import re
import json
import logging
from typing import Optional, Dict, List, Any 
from openai import OpenAI
from urllib.parse import urlparse
from django.conf import settings
from jobs.models import BlockRule, Tool 

logger = logging.getLogger("screener")

class MarTechScreener:
    """
    Diamond-Grade Edition (Strict Mode V5.0 - Tool-First Priority):
    1. Golden Rule: If a Tool Name is in the title, it is APPROVED.
    2. Bypasses "Vendor Trap" if the title mentions a specific tool.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        api_key = os.environ.get("OPENAI_API_KEY")
        # Timeout + retries so a hung OpenAI request can't stall the daily run.
        self.client = OpenAI(api_key=api_key, timeout=30, max_retries=2) if api_key else None

        # Manual blocklist (admin-managed). Loaded once per run.
        try:
            self.block_rules = [(r.rule_type, r.value) for r in BlockRule.objects.filter(enabled=True)]
        except Exception:
            self.block_rules = []
        
        self.hunt_roles = []
        self.hunt_tools = []
        
        target_file = os.path.join(settings.BASE_DIR, 'hunt_targets.txt')
        if os.path.exists(target_file):
            current_list = self.hunt_roles 
            with open(target_file, 'r') as f:
                for line in f:
                    raw = line.strip()
                    if not raw: continue
                    if raw.startswith('#'):
                        if "ROLE" in raw.upper(): current_list = self.hunt_roles
                        else: current_list = self.hunt_tools
                        continue
                    parts = [p.strip().replace('"', '') for p in raw.split(' OR ')]
                    current_list.extend(parts)
        else:
            self.hunt_roles = ["MarTech"]
            self.hunt_tools = ["Marketo", "Salesforce", "HubSpot", "Adobe", "Tealium", "Braze", "mParticle"]

        self.REQUIRED_KEYWORDS = list(set([r.lower() for r in self.hunt_roles + self.hunt_tools]))

        # Robust built-in MarTech title terms so the title gate doesn't depend
        # solely on hunt_targets.txt coverage (which dropped legit roles like
        # "Lifecycle Marketing Manager"). Multi-word role phrases + specific tool
        # names only — deliberately NO bare "marketing"/"manager"/"data".
        _GATE_ROLE_TERMS = {
            "marketing operations", "marketing ops", "mops", "marops",
            "marketing automation", "campaign operations", "campaign manager",
            "martech", "marketing technology", "marketing technologist",
            "marketing analytics", "marketing data", "marketing engineer",
            "customer data platform", "cdp", "solutions architect",
            "marketing systems", "web analytics", "digital analytics",
            "web analyst", "tag management", "analytics engineer",
        }
        _GATE_TOOL_TERMS = {
            "salesforce", "hubspot", "marketo", "pardot", "eloqua", "braze",
            "iterable", "klaviyo", "segment", "tealium", "mparticle", "amplitude",
            "mixpanel", "adobe experience", "aep", "ga4", "google analytics",
            "looker", "snowflake", "optimizely", "6sense", "demandbase",
            "outreach", "salesloft", "customer.io", "activecampaign",
            "marketing cloud", "sfmc",
        }
        self.gate_terms = set(self.REQUIRED_KEYWORDS) | _GATE_ROLE_TERMS | _GATE_TOOL_TERMS

        # Specialist, IN-SCOPE tools whose presence in a job DESCRIPTION is a
        # strong MarTech signal even when the title is generic ("Marketing
        # Manager" whose JD is all Marketo/Segment). Deliberately excludes the
        # ubiquitous tools (bare Salesforce/HubSpot/Google Analytics appear in
        # nearly every marketing JD) and the out-of-scope lifecycle messaging
        # tools (Braze/Iterable/Klaviyo) so we don't flood GPT with noise.
        self.desc_signal_tools = {
            "marketo", "pardot", "oracle eloqua", "eloqua",
            "salesforce marketing cloud", "sfmc", "adobe journey optimizer",
            "adobe campaign", "twilio segment", "segment", "tealium",
            "mparticle", "rudderstack", "hightouch", "census", "actioniq",
            "salesforce data cloud", "adobe experience platform",
            "adobe experience manager", "adobe analytics", "google tag manager",
            "tag manager", "optimizely", "amplitude", "mixpanel", "heap",
        }
        # Ensure we have a clean list of just tools for the prompt and check
        self.tool_list_clean = [t.lower() for t in self.hunt_tools if len(t) > 2]
        self.tool_menu_str = ", ".join(set(self.hunt_tools))
        
        self.VENDOR_COMPANIES = [
            "Braze", "Iterable", "Adobe", "Salesforce", "HubSpot", "Segment", 
            "Tealium", "Klaviyo", "mParticle", "Amplitude", "Mixpanel", 
            "Optimizely", "6sense", "Demandbase", "Drift", "Outreach", "Salesloft"
        ]

    def _normalize(self, text: str) -> str:
        return (text or "").strip().lower()

    def _is_blocked(self, title, company, apply_url) -> bool:
        if not self.block_rules:
            return False
        t = (title or "").lower(); c = (company or "").lower(); u = (apply_url or "").lower()
        for rule_type, value in self.block_rules:
            v = (value or "").strip()
            if not v:
                continue
            vl = v.lower()
            if rule_type == "company" and vl in c:
                return True
            if rule_type == "domain" and vl in u:
                return True
            if rule_type == "keyword" and vl in t:
                return True
            if rule_type == "regex":
                try:
                    if re.search(v, f"{title} {company}", re.IGNORECASE):
                        return True
                except re.error:
                    pass
        return False

    def _quick_kill(self, title: str, company: str) -> Optional[dict]:
        t_low = title.lower()
        c_low = company.lower()

        # 0. Tool-name-but-wrong-role trap. These are NEVER MarTech ops/eng/
        # analytics roles, but they often carry a tool name in the title
        # (e.g. "Salesforce Account Executive", "Adobe Photoshop Designer",
        # "HubSpot Sales Rep") which sneaks them past the keyword gate.
        nonmartech_roles = [
            "account executive", "account manager", "sales representative",
            "sales rep", "sales development", " sdr", " bdr", "business development",
            "photoshop", "illustrator", "videographer", "copywriter",
            "recruiter", "talent acquisition", "customer success",
        ]
        if any(r in t_low for r in nonmartech_roles):
            return {"status": "rejected", "score": 0.0, "reason": "Hard Reject: non-MarTech role (sales/creative/CS).", "details": {}}

        # 1. SEO/Event/Social Trap (Still keep this to filter noise)
        bad_keywords = ["seo ", "seo&", "event ", "events ", "social media", "community manager", "brand manager", "pr manager", "public relations"]
        if any(bad in t_low for bad in bad_keywords):
            if "operations" not in t_low and "technology" not in t_low:
                return {"status": "rejected", "score": 0.0, "reason": "Hard Reject: Non-Technical Role (SEO/Event/Social)", "details": {}}

        # 2. Vendor Trap (Working AT Salesforce/Adobe)
        is_vendor = any(v.lower() in c_low for v in self.VENDOR_COMPANIES)
        if is_vendor:
            # SAFETY BYPASS: If the title explicitly names a tool (e.g. "Salesforce Developer"), ALLOW IT.
            has_tool_in_title = any(tool in t_low for tool in self.tool_list_clean)
            
            if not has_tool_in_title:
                # Only reject if it's a generic product role AND doesn't mention a tool
                vendor_bad_titles = ["software engineer", "product manager", "data scientist", "machine learning", "ai scientist", "account executive", "csm", "customer success"]
                if any(bt in t_low for bt in vendor_bad_titles):
                    if "marketing" not in t_low and "martech" not in t_low:
                        return {"status": "rejected", "score": 0.0, "reason": f"Vendor Trap: {title} at {company} is a product role (no tool mentioned).", "details": {}}

        return None

    def screen(self, title: str, company: str, location: str, description: str, apply_url: str) -> dict:
        if self._is_blocked(title, company, apply_url):
            return {"status": "rejected", "score": 0.0, "reason": "Blocked by admin BlockRule.", "details": {"stage": "blocklist"}}
        quick_reject = self._quick_kill(title, company)
        if quick_reject:
            return quick_reject

        # Precision gate: require a hunt keyword in the TITLE. Gating on the
        # description matches almost everything (every marketing JD lists
        # "Salesforce/HubSpot" somewhere), which is why generic roles slipped in.
        title_norm = self._normalize(title)
        has_keyword = any(kw in title_norm for kw in self.gate_terms)

        # Description-signal fallback: a lot of real MarTech roles ship with a
        # generic title ("Marketing Manager", "Technical Consultant", "Senior
        # Analyst") but a JD that is unmistakably built around an in-scope
        # specialist platform. If the title misses but the DESCRIPTION names
        # >= 2 distinct specialist tools, let GPT make the final call instead of
        # hard-rejecting. We require two distinct hits (not one) because a single
        # passing mention ("we use Marketo") is often incidental, whereas two
        # specialist tools signals the role actually owns the stack.
        desc_signal = False
        if not has_keyword:
            desc_norm = self._normalize(description)
            hits = {t for t in self.desc_signal_tools if t in desc_norm}
            desc_signal = len(hits) >= 2

        if not has_keyword and not desc_signal:
            return {"status": "rejected", "score": 0.0, "reason": "Stage 1: No MarTech term in TITLE or specialist tools in JD.", "details": {"stage": "fast_fail"}}

        if not self.client:
            return {"status": "pending", "score": 50.0, "reason": "OPENAI_API_KEY missing.", "details": {"stage": "api_missing"}}

        try:
            return self.ask_ai(title, company, description, location)
        except Exception as e:
            logger.error(f"AI Crash: {e}")
            return {"status": "pending", "score": 25.0, "reason": f"AI Crash: {e}", "details": {"stage": "api_error"}}

    def ask_ai(self, title, company, description, location):
        prompt = f"""
        You are a STRICT Senior MarTech Recruiter for a high-precision, NARROWLY
        scoped job board. We accept ONLY three role families:
          1. MARKETING OPERATIONS — Marketing Ops/MOps, Marketing Automation
             (Marketo/HubSpot/Braze platform work), and Campaign Operations.
          2. MARTECH ENGINEERING — hands-on build/integration of the marketing
             stack (marketing/MarTech engineer, integration developer, CDP engineer).
          3. MARKETING ANALYTICS / DATA — analytics, measurement, attribution,
             tagging, BI for marketing.

        JOB CONTEXT:
        - Title: {title}
        - Company: {company}
        - Snippet: {description[:3000]}...

        VALID TOOLS MENU (for stack detection): [{self.tool_menu_str}]

        DECISION RULES (precision over recall — when unsure, prefer REJECT):

        APPROVE (85-100) ONLY if the role's PRIMARY function is one of the three
        families above and it's hands-on with marketing tools, data, or operations.
        Good examples: "Salesforce Administrator", "Marketo Specialist",
        "Marketing Operations Manager", "Marketing Automation Manager",
        "Campaign Operations Manager", "MarTech Engineer", "Marketing Analytics Manager".

        REJECT (0) — IMPORTANT, this board explicitly EXCLUDES these even though
        they are marketing-adjacent:
        - Revenue Operations / RevOps / Sales Operations
        - Lifecycle Marketing / Retention / CRM Marketing Manager / Email Marketing Manager
        - Growth Marketing / Growth Operations
        - Demand Generation / Demand Gen
        (If the role's PRIMARY function is one of the above, REJECT it — even if it
        uses Marketo/HubSpot/Braze. Only approve when the primary function is truly
        Marketing Operations, Marketing Automation, Campaign Operations, MarTech
        engineering, or marketing analytics.)

        ALSO REJECT (0):
        - Creative / content / design / copywriting / video / brand / PR / social /
          community / events / SEO / SEM / paid-media-buying
        - Sales / account management / customer success / SDR / BDR / recruiting
        - Generic software engineering, data science, or product roles not specific
          to the marketing stack (even at a MarTech vendor)
        - Tool name in title but wrong role (e.g. "Adobe Photoshop Designer",
          "Salesforce Account Executive", "HubSpot Sales Rep").

        PENDING (50-70) only if genuinely ambiguous.

        IMPORTANT: A tool name in the title is a POSITIVE signal ONLY when paired
        with one of the three accepted families. NEVER auto-approve on a tool alone.

        GENERIC TITLES: Some real MarTech roles ship with a vague title
        ("Marketing Manager", "Technical Consultant", "Senior Analyst",
        "Solutions Consultant") but a JD that is clearly built around owning an
        in-scope platform (Marketo, Eloqua, SFMC, Segment, Tealium, mParticle,
        Adobe Experience Platform/AEM, GTM, etc.). In that case, judge by the JD,
        not the title: APPROVE only if the day-to-day responsibilities are
        genuinely Marketing Operations / Automation / Campaign Ops, MarTech
        engineering, or marketing analytics. If the JD only mentions the tool in
        passing, or the primary function is one of the EXCLUDED families above,
        REJECT.

        ALSO:
        - Detect stack: tools actually used (from the menu or clearly named).
        - Classify function into exactly one of:
          * "engineering": hands-on build/integration — developer, architect,
            marketing/MarTech engineer, CDP engineer, integration, implementation,
            AND analytics-engineering / web-analytics implementation / tag
            management (dbt, GTM, Tealium tagging)
          * "operations": Marketing Operations, Marketing Automation, Campaign Operations
          * "data": analysis, reporting, measurement, BI, attribution, insights
            (a Web Analyst / Marketing Analyst who analyzes, not implements)
          * "other": doesn't clearly fit

        Output JSON:
        {{
            "decision": "APPROVE" | "REJECT" | "PENDING",
            "score": 0-100,
            "reason": "Clear, specific explanation.",
            "signals": {{ "stack": [], "function": "operations" }}
        }}
        """

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a strict job screener. Output only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0
        )

        content = completion.choices[0].message.content.strip()
        
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]

        try:
            result = json.loads(content.strip())
        except json.JSONDecodeError:
            return {"status": "pending", "score": 50.0, "reason": "AI JSON Error", "details": {"raw": content}}
        
        signals = result.get("signals", {})
        stack = signals.get("stack", [])
        
        found_adobe = False
        for tool in stack:
            t_lower = tool.lower()
            # Marketo is Adobe Marketo Engage; "adobe" is self-evident. Magento
            # is e-commerce, NOT MarTech — it must not pull in Adobe Exp Cloud.
            if "adobe" in t_lower or "marketo" in t_lower:
                found_adobe = True
                break
        if found_adobe and "Adobe Experience Cloud" not in stack:
            stack.append("Adobe Experience Cloud")
            signals["stack"] = stack
            result["signals"] = signals

        score = float(result.get("score", 0.0))
        decision = result.get("decision", "PENDING").upper()
        
        if decision == "REJECT" or score == 0:
            final_status = "rejected"
        elif decision == "APPROVE" and score >= 85: 
            final_status = "approved"
        else:
            final_status = "pending"

        return {
            "status": final_status,
            "score": score,
            "reason": str(result.get("reason", "AI analysis complete.")),
            "details": {"stage": "gpt_analysis", "signals": result.get("signals", {}), "raw_response": content}
        }

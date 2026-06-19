import os
import re
import json
import logging
import traceback
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

        # 0. Clearly non-MarTech roles even when a tool name appears in the title.
        nonmartech_roles = [
            "account executive", "sales representative", "sales rep",
            "sales development", " sdr", " bdr", "business development",
            "photoshop", "illustrator", "videographer", "copywriter",
            "recruiter", "talent acquisition", "customer success",
        ]
        if any(r in t_low for r in nonmartech_roles):
            return {"status": "rejected", "score": 0.0, "reason": "Hard Reject: non-MarTech role (sales/creative/CS).", "details": {}}

        # 1. SEO/Event/Social trap
        bad_keywords = ["seo ", "seo&", "event ", "events ", "social media", "community manager", "brand manager", "pr manager", "public relations"]
        if any(bad in t_low for bad in bad_keywords):
            if "operations" not in t_low and "technology" not in t_low:
                return {"status": "rejected", "score": 0.0, "reason": "Hard Reject: Non-Technical Role (SEO/Event/Social)", "details": {}}

        # 2. Vendor trap — only applies to truly generic product/sales roles at
        # tool vendors. Salesforce/HubSpot Admins, Developers, Architects, and
        # Consultants are valid even when the company IS the vendor, because
        # practitioners still need to see those postings.
        sfdc_tech_roles = {
            "administrator", "admin", "developer", "architect", "consultant",
            "analyst", "engineer", "implementer", "specialist", "manager",
        }
        is_sfdc_tech = any(r in t_low for r in sfdc_tech_roles)

        is_vendor = any(v.lower() in c_low for v in self.VENDOR_COMPANIES)
        if is_vendor and not is_sfdc_tech:
            vendor_bad_titles = [
                "software engineer", "product manager", "data scientist",
                "machine learning", "ai scientist", "account executive",
                "csm", "customer success",
            ]
            if any(bt in t_low for bt in vendor_bad_titles):
                if "marketing" not in t_low and "martech" not in t_low:
                    return {"status": "rejected", "score": 0.0, "reason": f"Vendor Trap: generic product role at {company}.", "details": {}}

        return None

    def screen(self, title: str, company: str, location: str, description: str, apply_url: str) -> dict:
        if self._is_blocked(title, company, apply_url):
            return {"status": "rejected", "score": 0.0, "reason": "Blocked by admin BlockRule.", "details": {"stage": "blocklist"}}
        quick_reject = self._quick_kill(title, company)
        if quick_reject:
            return quick_reject

        # Fast-approve: "martech" in the title is an unambiguous signal.
        if "martech" in self._normalize(title):
            return {"status": "approved", "score": 92.0, "reason": "Fast-approve: MarTech in title.", "details": {"stage": "fast_approve", "signals": {"function": "operations", "stack": []}}}

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
            logger.error("AI Crash: %s\n%s", e, traceback.format_exc())
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

        DECISION RULES:

        APPROVE (85-100) for any of these:
          1. MARKETING OPERATIONS roles — Marketing Ops, Marketing Automation,
             Campaign Operations, Marketing Systems, CRM/MAP administration.
          2. MARTECH ENGINEERING roles — MarTech Engineer, Marketing Engineer,
             CDP/integration developer, tag management, marketing data engineer.
          3. MARKETING ANALYTICS roles — Marketing Analyst, Marketing Data Analyst,
             attribution, web analytics, campaign analytics, BI for marketing.
          4. SALESFORCE TECHNICAL roles — Salesforce Administrator, Salesforce
             Developer, Salesforce Architect, Salesforce Consultant, Salesforce
             Implementer, Salesforce Business Analyst, SFMC/Marketing Cloud roles.
             These are core MarTech skills regardless of what company posts them.
          5. ANY role with "MarTech" in the title — always approve.
          6. SFMC / Marketing Cloud Analyst or Specialist — always approve.
          7. HubSpot Administrator, Marketo Specialist, Eloqua Consultant,
             Pardot Administrator, Braze Engineer — always approve.

        REJECT (0) — hard exclusions:
        - Pure sales roles: Account Executive, Sales Rep, SDR, BDR, Sales Manager
        - Creative / content / copywriting / video / brand / PR / social media /
          community manager / events / SEO / SEM / paid media buying
        - Customer Success / Support / Recruiting / HR
        - Generic software engineering or data science with NO marketing stack
          component (e.g. backend engineer, ML engineer, data scientist building
          internal tools unrelated to marketing)
        - Finance, legal, operations roles unrelated to marketing technology

        PENDING (50-70) only if genuinely ambiguous after reading the JD.

        WHEN IN DOUBT, APPROVE — this board prefers relevant roles over missing them.
        A Salesforce Admin at any company is relevant to MarTech practitioners.
        A Marketing Operations role at a vendor company is still relevant.

        GENERIC TITLES: Judge by the JD. If a "Solutions Consultant" or "Technical
        Consultant" role is clearly built around Salesforce, HubSpot, Marketo,
        SFMC, Segment, Tealium, or another MarTech platform — APPROVE it.

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

        choices = completion.choices if completion and completion.choices else []
        if not choices:
            return {"status": "pending", "score": 50.0, "reason": "AI returned no choices.", "details": {}}
        raw_content = choices[0].message.content
        if not raw_content:
            return {"status": "pending", "score": 50.0, "reason": "AI returned empty content.", "details": {}}
        content = raw_content.strip()

        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]

        try:
            result = json.loads(content.strip())
        except json.JSONDecodeError:
            return {"status": "pending", "score": 50.0, "reason": "AI JSON Error", "details": {"raw": content}}

        if not isinstance(result, dict):
            return {"status": "pending", "score": 50.0, "reason": "AI returned non-dict JSON.", "details": {"raw": content}}

        signals = result.get("signals") or {}
        stack = signals.get("stack") or []
        
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

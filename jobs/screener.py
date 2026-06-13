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
            "revops", "revenue operations", "marketing automation",
            "lifecycle marketing", "lifecycle", "retention marketing",
            "crm manager", "crm marketing", "martech", "marketing technology",
            "marketing technologist", "demand generation", "demand gen",
            "marketing analytics", "campaign operations", "campaign manager",
            "email marketing", "growth marketing", "customer data platform",
            "cdp", "marketing engineer", "marketing data", "solutions architect",
            "marketing systems", "gtm operations", "go-to-market operations",
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
        if not has_keyword:
            return {"status": "rejected", "score": 0.0, "reason": "Stage 1: No MarTech term in TITLE.", "details": {"stage": "fast_fail"}}
        
        if not self.client:
            return {"status": "pending", "score": 50.0, "reason": "OPENAI_API_KEY missing.", "details": {"stage": "api_missing"}}

        try:
            return self.ask_ai(title, company, description, location)
        except Exception as e:
            logger.error(f"AI Crash: {e}")
            return {"status": "pending", "score": 25.0, "reason": f"AI Crash: {e}", "details": {"stage": "api_error"}}

    def ask_ai(self, title, company, description, location):
        prompt = f"""
        You are a STRICT Senior MarTech Recruiter for a high-precision job board.
        Decide if this is a genuine MARKETING TECHNOLOGY role — i.e. one of:
        Marketing Operations, Revenue Operations (RevOps), MarTech engineering /
        integration, lifecycle / CRM, or marketing analytics. These are the people
        who RUN, BUILD, or MEASURE the marketing technology stack.

        JOB CONTEXT:
        - Title: {title}
        - Company: {company}
        - Snippet: {description[:3000]}...

        VALID TOOLS MENU (for stack detection): [{self.tool_menu_str}]

        DECISION RULES (precision over recall — when unsure, prefer PENDING/REJECT):

        APPROVE (85-100) ONLY if the role is clearly Marketing Ops / RevOps /
        MarTech engineering / lifecycle-CRM / marketing analytics, and is hands-on
        with marketing tools, data, or operations.
        Good examples: "Salesforce Administrator", "Marketo Specialist", "HubSpot
        Developer", "Marketing Operations Manager", "Lifecycle Marketing Manager",
        "Marketing Analytics Manager", "RevOps Manager".

        REJECT (0) if it is ANY of:
        - Creative / content / design / copywriting / video / brand / PR / social /
          community / events / SEO / SEM / paid-media-buying
        - Sales / account management / customer success / SDR / BDR / recruiting
        - Generic software engineering, data science, or product roles that are NOT
          specifically about the marketing stack (even at a MarTech vendor)
        - A role where a tool NAME appears but the job is not ops/eng/analytics —
          e.g. "Adobe Photoshop Designer", "Salesforce Account Executive",
          "Google Ads Buyer", "HubSpot Sales Rep".

        PENDING (50-70) if genuinely ambiguous.

        IMPORTANT: A tool name in the title is a POSITIVE signal ONLY when paired
        with an operations / engineering / analytics role. NEVER auto-approve on a
        tool name alone.

        ALSO:
        - Detect stack: tools actually used (from the menu or clearly named).
        - Classify function into exactly one of:
          * "engineering": hands-on build/integration (developer, architect, engineer, implementation)
          * "operations": platform use, campaign execution, admin, strategy (ops, admin, manager, specialist)
          * "data": analytics, reporting, measurement, BI, attribution (analyst, insights)
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
            if "adobe" in t_lower or "marketo" in t_lower or "magento" in t_lower:
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

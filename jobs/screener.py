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
    Diamond-Grade Edition (Strict Mode V4.0 - Ironclad Vendor Trap):
    1. Python-side "Quick Kill" for SEO, Events, and Vendor Product roles.
    2. Prevents AI from ever seeing "Software Engineer at Braze".
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        api_key = os.environ.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        
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
            self.hunt_tools = ["Marketo"]

        self.REQUIRED_KEYWORDS = list(set([r.lower() for r in self.hunt_roles + self.hunt_tools]))
        self.tool_menu_str = ", ".join(set(self.hunt_tools))
        
        # --- NEW: VENDOR BLACKLIST ---
        # If the job is AT these companies, we forbid engineering/product roles
        self.VENDOR_COMPANIES = [
            "Braze", "Iterable", "Adobe", "Salesforce", "HubSpot", "Segment", 
            "Tealium", "Klaviyo", "mParticle", "Amplitude", "Mixpanel", 
            "Optimizely", "6sense", "Demandbase", "Drift", "Outreach", "Salesloft"
        ]

    def _normalize(self, text: str) -> str:
        return (text or "").strip().lower()

    def _quick_kill(self, title: str, company: str) -> Optional[dict]:
        """
        Runs BEFORE AI. Instantly rejects known bad patterns.
        """
        t_low = title.lower()
        c_low = company.lower()

        # 1. THE EVENT/SEO/SOCIAL KILLER
        # These words in a title = Instant Death (unless "Operations" is also there)
        bad_keywords = ["seo ", "seo&", "event ", "events ", "social media", "community manager", "brand manager", "pr manager", "public relations"]
        if any(bad in t_low for bad in bad_keywords):
            if "operations" not in t_low and "technology" not in t_low:
                return {"status": "rejected", "score": 0.0, "reason": "Hard Reject: Non-Technical Role (SEO/Event/Social)", "details": {}}

        # 2. THE VENDOR PRODUCT TRAP
        # If Company is a Vendor AND Title is Engineering/Product -> REJECT
        is_vendor = any(v.lower() in c_low for v in self.VENDOR_COMPANIES)
        if is_vendor:
            vendor_bad_titles = ["software engineer", "developer", "product manager", "data scientist", "machine learning", "ai scientist", "solutions engineer", "account executive", "csm", "customer success"]
            if any(bt in t_low for bt in vendor_bad_titles):
                # Exception: Allow "MarTech" or "Marketing Ops" titles at vendors
                if "marketing" not in t_low and "martech" not in t_low:
                    return {"status": "rejected", "score": 0.0, "reason": f"Vendor Trap: {title} at {company} is a product role.", "details": {}}

        return None

    def screen(self, title: str, company: str, location: str, description: str, apply_url: str) -> dict:
        # 1. Run Python Quick Kill (Free & Fast)
        quick_reject = self._quick_kill(title, company)
        if quick_reject:
            return quick_reject

        # 2. Standard Block Rules (DB based)
        # ... (Keep existing _apply_block_rules logic or call it here) ...

        full_text = self._normalize(f"{title} {description}")
        
        # 3. Fast Fail Keyword Check
        has_keyword = any(kw in full_text for kw in self.REQUIRED_KEYWORDS)
        if not has_keyword:
            return {"status": "rejected", "score": 0.0, "reason": "Stage 1: No hunt_targets keyword found.", "details": {"stage": "fast_fail"}}
        
        if not self.client:
            return {"status": "pending", "score": 50.0, "reason": "OPENAI_API_KEY missing.", "details": {"stage": "api_missing"}}

        try:
            return self.ask_ai(title, company, description, location)
        except Exception as e:
            logger.error(f"AI Crash: {e}")
            return {"status": "pending", "score": 25.0, "reason": f"AI Crash: {e}", "details": {"stage": "api_error"}}

    def ask_ai(self, title, company, description, location):
        prompt = f"""
        Act as a "Senior MarTech Recruiter". 
        GOAL: Accept ONLY "Marketing Operations" & "MarTech Engineering" roles.
        REJECT: "Product Engineers", "General Marketers", "Sales", "CSMs".

        JOB CONTEXT:
        - Title: {title}
        - Company: {company}
        - Snippet: {description[:3000]}...

        ✅ VALID TOOLS MENU:
        [{self.tool_menu_str}]

        ⛔ HARD REJECT KEYWORDS (Double Check):
        [
         "Customer Success", "CSM", "Account Manager", "Sales", "SDR", "BDR",
         "Event", "Social Media", "Content", "Brand", "Community", "PR", "SEO", "Search Engine",
         "Copywriter", "Creative", "Audit", "Support", "Field Marketing"
        ]

        YOUR TASKS:
        1. **Detect Tech Stack:** Identify tools from the VALID TOOLS MENU above.

        2. **Analyze Role (STRICT FILTER):**
           
           - **STEP A: The "Vendor" Check:**
             - If Company is a software vendor (e.g. Braze, Adobe) AND title is "Software Engineer" -> **REJECT (0)**. (We want users of the tool, not builders of the tool).

           - **STEP B: The "Marketing" Trap:**
             - If Title contains "SEO", "Event", "Social", "Brand" -> **REJECT (0)**.
             - If Title contains "Manager" but is generic (e.g. "Marketing Manager") -> **REJECT (0)** unless description explicitly details MarTech Admin work.

           - **STEP C: The "Good" Signals:**
             - **Case 1 (Technical Title):** Title has "MarTech", "Marketing Technologist", "Marketing Operations", "MOPs". -> **APPROVE (90)**.
             - **Case 2 (Tool Admin):** Title has exact tool name (e.g. "Marketo Admin", "Salesforce Architect"). -> **APPROVE (90)**.
             - **Case 3 (VIP Description):** Title is generic ("Product Manager") BUT description explicitly says "Owner of Adobe Experience Platform" or "Migrating to Braze". -> **APPROVE (85)**.

        3. **Scoring:**
           - 0 = Reject (CSM, Sales, Events, SEO, Generic SWE, Vendor Product Roles)
           - 65 = Pending
           - 85-100 = Auto-Approve

        Output JSON:
        {{
            "decision": "APPROVE" | "REJECT" | "PENDING",
            "score": 0-100,
            "reason": "Clear explanation.",
            "signals": {{ "stack": [], "role_type": "MOPs" }}
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

        content = completion.choices[0].message.content
        result = json.loads(content)
        
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

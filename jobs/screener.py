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
        
        self.VENDOR_COMPANIES = [
            "Braze", "Iterable", "Adobe", "Salesforce", "HubSpot", "Segment", 
            "Tealium", "Klaviyo", "mParticle", "Amplitude", "Mixpanel", 
            "Optimizely", "6sense", "Demandbase", "Drift", "Outreach", "Salesloft"
        ]

    def _normalize(self, text: str) -> str:
        return (text or "").strip().lower()

    def _quick_kill(self, title: str, company: str) -> Optional[dict]:
        t_low = title.lower()
        c_low = company.lower()

        bad_keywords = ["seo ", "seo&", "event ", "events ", "social media", "community manager", "brand manager", "pr manager", "public relations"]
        if any(bad in t_low for bad in bad_keywords):
            if "operations" not in t_low and "technology" not in t_low:
                return {"status": "rejected", "score": 0.0, "reason": "Hard Reject: Non-Technical Role (SEO/Event/Social)", "details": {}}

        is_vendor = any(v.lower() in c_low for v in self.VENDOR_COMPANIES)
        if is_vendor:
            vendor_bad_titles = ["software engineer", "developer", "product manager", "data scientist", "machine learning", "ai scientist", "solutions engineer", "account executive", "csm", "customer success"]
            if any(bt in t_low for bt in vendor_bad_titles):
                if "marketing" not in t_low and "martech" not in t_low:
                    return {"status": "rejected", "score": 0.0, "reason": f"Vendor Trap: {title} at {company} is a product role.", "details": {}}

        return None

    def screen(self, title: str, company: str, location: str, description: str, apply_url: str) -> dict:
        quick_reject = self._quick_kill(title, company)
        if quick_reject:
            return quick_reject

        full_text = self._normalize(f"{title} {description}")
        
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
           - **STEP A: The "Vendor" Check:** If Vendor company AND Engineering/Product title -> REJECT (0).
           - **STEP B: The "Marketing" Trap:** If SEO/Social/Brand -> REJECT (0).
           - **STEP C: The "Good" Signals:**
             - "Marketing Operations", "MarTech" -> APPROVE (90).
             - Tool Admin (e.g. "Marketo Admin") -> APPROVE (90).
             - Product Manager but explicitly for "Adobe Experience Platform" -> APPROVE (85).

        3. **Scoring:** 0 = Reject, 65 = Pending, 85-100 = Auto-Approve.

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

        content = completion.choices[0].message.content.strip()
        
        # FIX: Strip markdown code blocks if AI adds them
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]

        try:
            result = json.loads(content.strip())
        except json.JSONDecodeError:
            # Fallback if JSON is still broken
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

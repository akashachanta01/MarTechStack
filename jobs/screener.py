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
            self.hunt_tools = ["Marketo", "Salesforce", "HubSpot", "Adobe", "Tealium", "Braze", "mParticle"]

        self.REQUIRED_KEYWORDS = list(set([r.lower() for r in self.hunt_roles + self.hunt_tools]))
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

    def _quick_kill(self, title: str, company: str) -> Optional[dict]:
        t_low = title.lower()
        c_low = company.lower()

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
        
        JOB CONTEXT:
        - Title: {title}
        - Company: {company}
        - Snippet: {description[:3000]}...

        ✅ VALID TOOLS MENU:
        [{self.tool_menu_str}]

        ⛔ HARD REJECT KEYWORDS:
        [
         "Customer Success", "CSM", "Account Manager", "Sales", "SDR", "BDR",
         "Event", "Social Media", "Content", "Brand", "Community", "PR", "SEO", "Search Engine",
         "Copywriter", "Creative", "Audit", "Support", "Field Marketing"
        ]

        YOUR TASKS:
        1. **Detect Tech Stack:** Identify tools from the VALID TOOLS MENU above.

        2. **Analyze Role (STRICT FILTER):**
           - **STEP A: GOLDEN RULE:** If ANY tool from the VALID TOOLS MENU appears in the Job Title -> APPROVE (95). 
             (e.g. "Salesforce Developer", "HubSpot Admin", "Adobe Architect"). This overrides "Engineer" or "Developer" concerns.
           
           - **STEP B: The "Marketing" Trap:** If title contains SEO/Social/Brand -> REJECT (0).
           
           - **STEP C: The "Good" Signals:**
             - "Marketing Operations", "MarTech" -> APPROVE (90).
             - "Solution Architect" (if MarTech related) -> APPROVE (85).

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

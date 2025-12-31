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
    Diamond-Grade Edition (Strict Mode V3.2 - Anti-Vendor/Anti-User):
    1. Hard Reject List updated with specific roles (CSM, Sales, Social).
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
        self.targets_str = ", ".join(set(self.hunt_roles + self.hunt_tools))

    def _normalize(self, text: str) -> str:
        return (text or "").strip().lower()

    def _extract_domain(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""

    def _apply_block_rules(self, title: str, company: str, description: str, apply_url: str) -> Optional[dict]:
        title_n = self._normalize(title)
        company_n = self._normalize(company)
        desc_n = self._normalize(description)
        domain = self._extract_domain(apply_url)

        for rule in BlockRule.objects.filter(enabled=True):
            v = self._normalize(rule.value)
            if rule.rule_type == "domain" and domain == v:
                return {"status": "rejected", "score": 0.0, "reason": f"Blocked by domain rule: {domain}", "details": {"blocked_by": rule.value}}
            elif rule.rule_type == "company" and v in company_n:
                return {"status": "rejected", "score": 0.0, "reason": f"Blocked by company rule: {rule.value}", "details": {"blocked_by": rule.value}}
            elif rule.rule_type == "keyword" and (v in title_n or v in desc_n):
                return {"status": "rejected", "score": 0.0, "reason": f"Blocked by keyword rule: {rule.value}", "details": {"blocked_by": rule.value}}
            elif rule.rule_type == "regex":
                try:
                    if re.search(rule.value, title or "", re.IGNORECASE) or re.search(rule.value, description or "", re.IGNORECASE):
                        return {"status": "rejected", "score": 0.0, "reason": f"Blocked by regex rule: {rule.value}", "details": {"blocked_by": rule.value}}
                except: continue
        return None
        
    def screen(self, title: str, company: str, location: str, description: str, apply_url: str) -> dict:
        blocked = self._apply_block_rules(title, company, description, apply_url)
        if blocked: return blocked

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
        Act as a "Senior MarTech Recruiter". Filter out "Users" (Marketers/Sales) and keep "Builders" (Ops/Engineers).

        JOB CONTEXT:
        - Title: {title}
        - Company: {company}
        - Snippet: {description[:3000]}...

        ✅ VALID TOOLS MENU:
        [{self.tool_menu_str}]

        ⛔ HARD REJECT KEYWORDS (AUTO-FAIL):
        [
         "Customer Success", "CSM", "Account Manager", "Account Executive", "Sales", "SDR", "BDR",
         "Partner Marketing", "Field Marketing", "Demand Generation", "Demand Gen", "Growth Lead",
         "Social Media", "Content", "Brand", "Community", "PR", "SEO", "Search Engine", 
         "Copywriter", "Creative", "Audit", "Support Analyst", "Technical Support", "Support Engineer"
        ]

        🚩 GENERIC RED FLAGS (Fail unless Strong Tech Signal):
        ["Product Manager", "Project Manager", "Program Manager", "Consultant", "Specialist", "Analyst"]

        YOUR TASKS:
        1. **Detect Tech Stack:** Identify tools from the VALID TOOLS MENU above.

        2. **Analyze Role:**
           
           - **STEP A: Hard Reject (The "No-Go" List):**
             - If Title contains ANY term from "HARD REJECT KEYWORDS" -> **REJECT (0)**.
             - (e.g. "Senior Customer Success Manager", "Technical Support Engineer", "Field Marketing Manager" are ALL 0).
             - Exception: "Marketing Operations" or "MarTech" in title overrides this.

           - **STEP B: Generic Red Flag Check:**
             - If Title matches "GENERIC RED FLAGS" (e.g. "Solutions Consultant") AND no VIP tools (Adobe/Salesforce) in description -> **REJECT (0)**.

           - **STEP C: Evaluate Specificity:**
             - **Case 1 (Technical Title):** Title has "MarTech", "Marketing Technologist", or exact Tool Name (e.g. "Marketo Admin")? -> **APPROVE (90)**.
             
             - **Case 2 (MOPs Title):** Title has "Marketing Operations"? -> **APPROVE (85)**.
             
             - **Case 3 (VIP Description Match):** Title Generic + VIP Tool in Description -> **APPROVE (85)**.
             
             - **Case 4 (Standard Match):** Title Generic + Standard Tool -> **PENDING (65)**.

        3. **Scoring:**
           - 0 = Reject (CSM, Sales, Support, Events, SEO)
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

import os
import re
import json
import logging
from typing import Optional, Dict, List, Any 
from openai import OpenAI
from urllib.parse import urlparse
from django.conf import settings
from jobs.models import BlockRule 

# Setup Audit Logging
logger = logging.getLogger("screener")

class MarTechScreener:
    """
    The Brain 🧠 (AI Agent + Auditing)
    Diamond-Grade Edition: Includes "Generic Title Guard" to kill Data Scientists/SWEs.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        api_key = os.environ.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        
        # 1. LOAD KEYWORDS (Single Source of Truth)
        self.REQUIRED_KEYWORDS = []
        target_file = os.path.join(settings.BASE_DIR, 'hunt_targets.txt')
        if os.path.exists(target_file):
            with open(target_file, 'r') as f:
                for line in f:
                    clean = line.strip().lower()
                    if clean and not clean.startswith('#'):
                        self.REQUIRED_KEYWORDS.append(clean)
        
        if not self.REQUIRED_KEYWORDS:
            logger.warning("⚠️ hunt_targets.txt is missing! Defaulting to 'martech'.")
            self.REQUIRED_KEYWORDS = ["martech"]
        
        self.REQUIRED_KEYWORDS = list(set(self.REQUIRED_KEYWORDS))
        
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
        
        # Stage 1: Keyword Check
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
        # UPDATED PROMPT: Added "The Generic Title Trap"
        prompt = f"""
        Act as a "Technical MarTech Recruiter". Screen this job for a niche board (Marketing Ops & Engineering).

        JOB: {title} at {company}
        SNIPPET: {description[:2000]}...

        YOUR MISSION:
        Approve ONLY roles dedicated to **Marketing Systems** (MarTech, MOPs, CDPs).
        Reject generic data/engineering roles.

        ⭐⭐⭐ THE "GENERIC TITLE" TRAP (CRITICAL):
        If the title is "Data Scientist", "Data Engineer", "Software Engineer", "Product Manager", or "Analyst":
        1. **STRICT REJECTION:** You must REJECT it UNLESS the Title explicitly contains "Marketing", "MarTech", "Growth", or "Revenue" (e.g. "Marketing Data Scientist" = OK. "Data Scientist" = REJECT).
        2. **Exception:** If the title is generic but the role is 100% focused on implementing a specific tool like Adobe Experience Platform or Salesforce (e.g. "Software Engineer - Salesforce Marketing Cloud").
        
        🚨 REJECT THESE IMMEDIATELY:
        1. **Product Engineering:** Building the company's SaaS product (e.g. "Backend Engineer for our App").
        2. **General BI:** "Data Analyst" doing Tableau/PowerBI for Finance/Sales.
        3. **Sales:** "Account Executive", "SDR", "Solution Engineer" (Pre-sales).

        ✅ APPROVAL CRITERIA (Score 85+):
        - Role is explicitly "Marketing Operations", "MarTech Manager", "Marketo Admin".
        - Role is "Implementation Engineer" or "Solution Architect" specifically for MarTech clients/tools.

        Output JSON:
        {{
            "decision": "APPROVE" | "REJECT" | "PENDING",
            "score": 0-100,
            "reason": "Why did it pass/fail the Generic Title Trap?",
            "signals": {{
                "stack": ["Tools Found"],
                "role_type": "MOPs" | "MarTech Eng" | "Other"
            }}
        }}
        """

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a JSON extractor. Output only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0
        )

        content = completion.choices[0].message.content
        result = json.loads(content)
        
        return {
            "status": str(result.get("decision", "PENDING")).lower(),
            "score": float(result.get("score", 50.0)),
            "reason": str(result.get("reason", "AI analysis complete.")),
            "details": {"stage": "gpt_analysis", "signals": result.get("signals", {}), "raw_response": content}
        }

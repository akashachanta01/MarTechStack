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
    Diamond-Grade Edition: 100% controlled by hunt_targets.txt
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        # 1. Initialize OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        
        # 2. LOAD KEYWORDS (Single Source of Truth)
        # We start empty. We ONLY use what is in your file.
        self.REQUIRED_KEYWORDS = []
        
        target_file = os.path.join(settings.BASE_DIR, 'hunt_targets.txt')
        if os.path.exists(target_file):
            with open(target_file, 'r') as f:
                for line in f:
                    clean = line.strip().lower()
                    # Skip comments and empty lines
                    if clean and not clean.startswith('#'):
                        self.REQUIRED_KEYWORDS.append(clean)
        
        # Safety Net: If file is missing or empty, prevent logic crash
        if not self.REQUIRED_KEYWORDS:
            logger.warning("⚠️ hunt_targets.txt is missing or empty! Defaulting to 'martech' only.")
            self.REQUIRED_KEYWORDS = ["martech"]
        
        # Deduplicate just in case
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
        """
        Applies database rules before paying for AI.
        """
        title_n = self._normalize(title)
        company_n = self._normalize(company)
        desc_n = self._normalize(description)
        domain = self._extract_domain(apply_url)

        # Using BlockRule model from the database
        for rule in BlockRule.objects.filter(enabled=True):
            v = self._normalize(rule.value)

            if rule.rule_type == "domain":
                if domain and domain == v:
                    return {"status": "rejected", "score": 0.0, "reason": f"Blocked by domain rule: {domain}", "details": {"blocked_by": rule.value}}

            elif rule.rule_type == "company":
                if company_n and v and v in company_n:
                    return {"status": "rejected", "score": 0.0, "reason": f"Blocked by company rule: {rule.value}", "details": {"blocked_by": rule.value}}

            elif rule.rule_type == "keyword":
                if v and (v in title_n or v in desc_n):
                    return {"status": "rejected", "score": 0.0, "reason": f"Blocked by keyword rule: {rule.value}", "details": {"blocked_by": rule.value}}

            elif rule.rule_type == "regex":
                try:
                    pattern = re.compile(rule.value, re.IGNORECASE)
                    if pattern.search(title or "") or pattern.search(description or ""):
                        return {"status": "rejected", "score": 0.0, "reason": f"Blocked by regex rule: {rule.value}", "details": {"blocked_by": rule.value}}
                except re.error:
                    continue

        return None
        
    def screen(self, title: str, company: str, location: str, description: str, apply_url: str) -> dict:
        """
        Main entrypoint used by fetch_jobs pipeline.
        """
        # Stage 0: Block rules
        blocked = self._apply_block_rules(title, company, description, apply_url)
        if blocked:
            return blocked

        full_text = self._normalize(f"{title} {description}")
        
        # Stage 1: Fast Fail (Cost-Free)
        # Checks against your hunt_targets.txt list
        has_keyword = any(kw in full_text for kw in self.REQUIRED_KEYWORDS)
        if not has_keyword:
            return {
                "status": "rejected",
                "score": 0.0,
                "reason": "Stage 1: No core keyword from hunt_targets.txt found.",
                "details": {"stage": "fast_fail"}
            }
        
        # Stage 2: AI Judge (Paid)
        if not self.client:
            return {
                "status": "pending",
                "score": 50.0,
                "reason": "OPENAI_API_KEY missing. Needs manual review.",
                "details": {"stage": "api_missing"},
            }

        try:
            return self.ask_ai(title, company, description, location)
        except Exception as e:
            logger.error(f"AI Crash on {title}: {e}")
            return {
                "status": "pending",
                "score": 25.0,
                "reason": f"AI Crash: {e}. Needs manual review.",
                "details": {"stage": "api_error"},
            }

    def ask_ai(self, title, company, description, location):
        # UPDATED PROMPT: "Technical MarTech Recruiter" Persona
        prompt = f"""
        Act as a "Technical MarTech Recruiter". Screen this job for a niche job board focused on **Marketing Technology, Operations, and Engineering**.

        JOB DETAILS:
        - Title: {title}
        - Company: {company}
        - Snippet: {description[:2000]}...

        YOUR MISSION:
        Determine if this is a specialized role for **building, managing, or architecting Marketing Systems** (e.g. Adobe, Salesforce, CDPs, Analytics).

        ⭐⭐⭐ GOLDEN RULES (High Score 90-100):
        1. **Technical Implementers:** APPROVE "Solution Architect", "Implementation Engineer", "Technical Consultant" IF the job is explicitly about implementing MarTech tools (e.g. "AEP Architect", "Marketo Consultant").
        2. **Marketing Engineers:** APPROVE "Forward Deployed Engineer", "Marketing Data Engineer" (focusing on Segment/Reverse ETL).
        3. **The Classics:** APPROVE "Marketing Operations Manager", "MarTech Lead", "Marketo Administrator".

        🚨 STRICT REJECTION RULES (Kill these immediately):
        1. **Generic Engineering:** REJECT "Full Stack Developer" or "Backend Engineer" if they are just building a generic React app.
        2. **Generic Data/BI:** REJECT "Data Analyst" if they just do SQL/Tableau for Finance/Product. Only accept if they focus on **Marketing Data** (Attribution, CDPs, GA4).
        3. **Sales/GTM:** REJECT "Account Executive", "Sales Manager", "GTM Strategy".
        4. **Content/Social:** REJECT "Social Media Manager", "Content Writer", "SEO Specialist" (unless highly technical/technical SEO).

        ✅ FINAL DECISION LOGIC:
        - **APPROVE (Score 85-100):** Clearly a MarTech, MOPs, or Marketing Engineering role.
        - **PENDING (Score 50-80):** Technical role that mentions Marketing but might be generic.
        - **REJECT (Score 0-20):** Generic Sales, Marketing, or Software Engineering.

        Output valid JSON:
        {{
            "decision": "APPROVE" | "REJECT" | "PENDING",
            "score": 0-100,
            "reason": "Brief explanation",
            "signals": {{
                "stack": ["List", "Tools", "Found"],
                "role_type": "MOPs" | "MarTech Engineering" | "Analytics" | "Other",
                "red_flags": []
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
        signals = result.get("signals", {})

        return {
            "status": str(result.get("decision", "PENDING")).lower(),
            "score": float(result.get("score", 50.0)),
            "reason": str(result.get("reason", "AI analysis complete.")),
            "details": {
                "stage": "gpt_analysis",
                "signals": signals,
                "raw_response": content
            }
        }

import os
import re
import json
import logging
from typing import Optional, Dict, List, Any # <--- ADDED THIS LINE
from openai import OpenAI
from urllib.parse import urlparse
from jobs.models import BlockRule 

# Setup Audit Logging
logger = logging.getLogger("screener")

class MarTechScreener:
    """
    The Brain 🧠 (AI Agent + Auditing)
    Diamond-Grade Edition: Tuned to reject non-MarTech roles, but accepts "MarTech Immunity" roles.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        # 1. Initialize OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        
        # 2. Heuristic keywords (Stage 1) - ONLY used for the fast-fail check
        self.REQUIRED_KEYWORDS = [
            "marketo", "hubspot", "salesforce marketing cloud", "sfmc", "pardot",
            "braze", "customer.io", "iterable", "klaviyo", "eloqua",
            "adobe analytics", "google analytics", "ga4", "mixpanel", "amplitude",
            "segment", "mparticle", "tealium", "cdp", "customer data platform",
            "google tag manager", "gtm",
            "marketing operations", "mops", "marketing technology", "martech", 
            "growth engineer", "marketing engineer",
            "adobe target", "adobe campaign", "journey optimizer", "ajo", "adobe experience cloud"
        ]
        
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
        has_keyword = any(kw in full_text for kw in self.REQUIRED_KEYWORDS)
        if not has_keyword:
            return {
                "status": "rejected",
                "score": 0.0,
                "reason": "Stage 1: No core MarTech/Stack keywords found (likely noise).",
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
        # The prompt with all the rejection and immunity rules
        prompt = f"""
        Act as a strict MarTech Recruiter. Screen this job for a specialized "Marketing Technology & Operations" job board.

        JOB DETAILS:
        - Title: {title}
        - Company: {company}
        - Location: {location}
        - Snippet: {description[:1500]}...

        YOUR MISSION:
        Determine if this role is explicitly for **building

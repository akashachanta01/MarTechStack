import os
import json
import logging
import re
from openai import OpenAI
from django.conf import settings

# Setup Audit Logging (Saves decisions to 'screener_audit.log')
logger = logging.getLogger("screener")
handler = logging.FileHandler("screener_audit.log")
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

class MarTechScreener:
    """
    The Brain 🧠 (AI Agent + Auditing)
    Uses GPT-4o-mini to screen jobs and logs the 'Why' for every rejection.
    """

    def __init__(self):
        # 1. Initialize OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("⚠️ WARNING: OPENAI_API_KEY not found. AI Screening will fail.")
        self.client = OpenAI(api_key=api_key)

        # 2. "Fast Fail" Keywords (Stage 1)
        # We only spend money on AI if these exist.
        self.REQUIRED_KEYWORDS = [
            "marketo", "hubspot", "salesforce marketing cloud", "sfmc", "pardot",
            "braze", "customer.io", "iterable", "klaviyo", "eloqua",
            "adobe analytics", "ga4", "google analytics", "mixpanel", "amplitude",
            "segment", "mparticle", "tealium", "cdp",
            "google tag manager", "gtm",
            "marketing operations", "marketing technology", "martech", "mops",
            "marketing automation", "growth engineer", "marketing engineer"
        ]

    def clean_text(self, text):
        return str(text).lower().strip()[:4000]  # Limit context window

    def screen_job(self, title, description, company_name=""):
        full_text = self.clean_text(f"{title} {description}")

        # --- STAGE 1: FAST FAIL (Regex) ---
        # Cost: $0. Filters out obvious garbage.
        has_keyword = any(kw in full_text for kw in self.REQUIRED_KEYWORDS)
        if not has_keyword:
            return {
                "is_match": False,
                "score": 0,
                "reason": "Stage 1: No MarTech keywords found",
                "stack": [],
                "categories": []
            }

        # --- STAGE 2: THE AI JUDGE (GPT-4o-mini) ---
        # Cost: ~$0.001 per job. High intelligence.
        try:
            return self.ask_ai(title, company_name, description)
        except Exception as e:
            logger.error(f"AI Crash on {title}: {e}")
            return {
                "is_match": False, 
                "score": 0, 
                "reason": f"AI Error: {e}",
                "stack": [],
                "categories": []
            }

    def ask_ai(self, title, company, description):
        prompt = f"""
        Act as a strict MarTech Recruiter. Analyze this job to see if it fits our niche board.

        JOB:
        - Title: {title}
        - Company: {company}
        - Snippet: {description[:1500]}...

        RULES FOR "MATCH":
        1. Role MUST be "Marketing Operations", "MarTech", "Marketing Analytics", or "Marketing Engineering".
        2. Role MUST involve administering/managing systems (Marketo, Salesforce, Segment, GTM).
        
        RULES FOR "REJECT" (The Kill List):
        1. REJECT Sales/Success roles (AE, CSM, Solutions Engineer, Presales) even if they know Marketo.
        2. REJECT Internal IT (Helpdesk, Director of IT, SysAdmin) unless explicitly for Marketing Systems.
        3. REJECT Digital Marketing/Growth (running ads/campaigns) if they don't own the tech stack.
        4. REJECT Product Management (PM) unless it is specifically "PM of MarTech Platform".
        5. REJECT if the company IS the vendor (e.g. HubSpot) and the role is Sales/Consulting/Support.

        Output valid JSON:
        {{
            "is_match": boolean,
            "reason": "Short reason for decision",
            "role_type": "Marketing Operations" | "MarTech Engineer" | "Marketing Analyst" | "Other",
            "stack": ["Tool1", "Tool2"],
            "categories": ["Automation", "Analytics", "CDP", "Tagging"]
        }}
        """

        completion = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are

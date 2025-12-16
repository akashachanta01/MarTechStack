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
    Diamond-Grade Edition: Tuned to reject "Data Analyst", "GTM Strategy", and "Vendor Support" roles.
    Includes "MarTech Immunity" for high-priority titles.
    """

    def __init__(self):
        # 1. Initialize OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("⚠️ WARNING: OPENAI_API_KEY not found. AI Screening will fail.")
        self.client = OpenAI(api_key=api_key)

        # 2. "Fast Fail" Keywords (Stage 1)
        self.REQUIRED_KEYWORDS = [
            "marketo", "hubspot", "salesforce marketing cloud", "sfmc", "pardot",
            "braze", "customer.io", "iterable", "klaviyo", "eloqua",
            "adobe analytics", "ga4", "google analytics", "mixpanel", "amplitude",
            "segment", "mparticle", "tealium", "cdp",
            "google tag manager", "gtm",
            "marketing operations", "marketing technology", "martech", "mops",
            "marketing automation", "growth engineer", "marketing engineer",
            "adobe target", "adobe campaign", "journey optimizer", "ajo"
        ]

    def clean_text(self, text):
        return str(text).lower().strip()[:4000]  # Limit context window

    def screen_job(self, title, description, company_name=""):
        full_text = self.clean_text(f"{title} {description}")

        # --- STAGE 1: FAST FAIL (Regex) ---
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
        Act as a strict MarTech Recruiter. Screen this job for a specialized "Marketing Technology & Operations" job board.

        JOB DETAILS:
        - Title: {title}
        - Company: {company}
        - Snippet: {description[:1500]}...

        YOUR MISSION:
        Determine if this role is explicitly for **building, administering, or managing Marketing Systems**.

        🚨 "MARTECH" IMMUNITY RULE:
        If the Job Title explicitly contains "MarTech" (e.g. "MarTech Product Manager", "MarTech Lead"), it is AUTOMATICALLY A MATCH.
        Ignore other rejection rules (like Product Manager) in this specific case.

        🚨 STRICT REJECTION RULES (Kill these jobs unless Immunity applies):
        1. **REJECT "Data Analyst" / "BI" Roles:** If the title is "Data Analyst" or "Business Intelligence" and focuses on SQL/Tableau/Reporting, REJECT IT.
        2. **REJECT "GTM" (Go-To-Market):** If the title says "GTM" (e.g. "GTM Analyst"), REJECT IT. This usually means Sales Strategy. Exception: If it explicitly says "Google Tag Manager" implementation.
        3. **REJECT "Vendor Product" Roles:** If the company is an AdTech/MarTech vendor (e.g. StackAdapt, The Trade Desk) and the role is "Technical Analyst", "Support", or "Client Services" for *their own* product, REJECT IT.
        4. **REJECT Sales & Growth:** Reject "Account Executive", "Solutions Engineer", "Growth Manager", "Paid Media Manager".
        5. **REJECT Internal IT:** Reject "IT Director", "Systems Admin" unless specifically for Marketing.

        ✅ ACCEPT ONLY IF:
        - The role is "Marketing Operations Manager", "MarTech Architect", "Marketing Engineer".
        - The role is "Marketing Analyst" BUT specifically focuses on **implementation/tracking** (GA4, GTM, Segment).

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
                {"role": "system", "content": "You are a JSON-only job screener."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0
        )

        result = json.loads(completion.choices[0].message.content)
        
        # AUDIT LOGGING
        log_msg = f"[{'✅ MATCH' if result['is_match'] else '❌ REJECT'}] {title} @ {company} | Reason: {result['reason']}"
        logger.info(log_msg)
        print(f"      🤖 AI Decision: {log_msg}")

        return {
            "is_match": result.get("is_match", False),
            "score": 90 if result.get("is_match") else 0,
            "reason": result.get("reason", "AI Rejection"),
            "stack": result.get("stack", []),
            "categories": result.get("categories", []),
            "role_type": result.get("role_type", "Marketing Technologist")
        }

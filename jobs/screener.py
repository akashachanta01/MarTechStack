import os
import re
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from openai import OpenAI

from .models import BlockRule


@dataclass
class ScreeningResult:
    status: str  # "pending" | "approved" | "rejected"
    score: float
    reason: str
    details: Dict[str, Any]


class MarTechScreener:
    """
    Zero-Noise Brain 🧠

    Two-stage:
      Stage 0: BlockRules (free) - reject obvious spam/noise before we pay OpenAI.
      Stage 1: Heuristic score (free) - ensures we only pay OpenAI for likely matches.
      Stage 2: GPT (paid) - final decision + reasoning.

    Output: ScreeningResult with explainability we store on the Job.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # --- Heuristic keywords (tune over time) ---
    POSITIVE_SIGNALS = [
        "martech", "marketing technology", "marketing ops", "mops",
        "adobe experience platform", "aep", "adobe journey optimizer", "ajo",
        "adobe analytics", "customer journey analytics", "cja",
        "tag manager", "adobe launch", "tealium", "google tag manager", "gtm",
        "cdp", "segment", "mparticle", "lytics", "treasure data",
        "braze", "iterable", "sfmc", "marketing cloud", "salesforce marketing cloud",
        "marketo", "eloqua", "responsys", "campaign", "personalization",
        "data layer", "event schema", "identity", "consent", "privacy",
        "journey orchestration", "email deliverability", "crm", "sfdc",
        "solutions architect", "implementation", "integration", "api",
    ]

    NEGATIVE_SIGNALS = [
        "commission only", "door to door", "cold calling", "telemarketer",
        "insurance agent", "loan officer", "real estate agent",
        "mlm", "multi-level marketing", "affiliate marketing",
        "brand ambassador", "influencer", "social media intern",
        "sales representative", "account executive", "business development",
        "lead generator", "appointment setter",
    ]

    TECH_ROLE_HINTS = [
        "architect", "engineer", "developer", "analyst", "consultant",
        "marketing operations", "marketing ops", "mops",
        "platform", "implementation", "integration", "data", "automation",
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

    def _apply_block_rules(self, title: str, company: str, description: str, apply_url: str) -> Optional[ScreeningResult]:
        """
        Returns ScreeningResult if blocked, else None.
        """
        title_n = self._normalize(title)
        company_n = self._normalize(company)
        desc_n = self._normalize(description)
        domain = self._extract_domain(apply_url)

        rules = BlockRule.objects.filter(enabled=True)

        for rule in rules:
            v = self._normalize(rule.value)

            if rule.rule_type == "domain":
                if domain and domain == v:
                    return ScreeningResult(
                        status="rejected",
                        score=0.0,
                        reason=f"Blocked by domain rule: {domain}",
                        details={"blocked": True, "rule_type": "domain", "value": rule.value, "domain": domain},
                    )

            elif rule.rule_type == "company":
                if company_n and v and v in company_n:
                    return ScreeningResult(
                        status="rejected",
                        score=0.0,
                        reason=f"Blocked by company rule: {rule.value}",
                        details={"blocked": True, "rule_type": "company", "value": rule.value},
                    )

            elif rule.rule_type == "keyword":
                if v and (v in title_n or v in desc_n):
                    return ScreeningResult(
                        status="rejected",
                        score=0.0,
                        reason=f"Blocked by keyword rule: {rule.value}",
                        details={"blocked": True, "rule_type": "keyword", "value": rule.value},
                    )

            elif rule.rule_type == "regex":
                try:
                    pattern = re.compile(rule.value, re.IGNORECASE)
                    if pattern.search(title or "") or pattern.search(description or ""):
                        return ScreeningResult(
                            status="rejected",
                            score=0.0,
                            reason=f"Blocked by regex rule: {rule.value}",
                            details={"blocked": True, "rule_type": "regex", "value": rule.value},
                        )
                except re.error:
                    # bad regex in DB; ignore but record in details for visibility
                    continue

        return None

    def _heuristic_score(self, title: str, company: str, description: str) -> Tuple[float, Dict[str, Any]]:
        """
        Fast score: 0-100. Used to decide whether to pay for GPT.
        """
        t = self._normalize(title)
        c = self._normalize(company)
        d = self._normalize(description)

        matched_positive = [k for k in self.POSITIVE_SIGNALS if k in t or k in d]
        matched_negative = [k for k in self.NEGATIVE_SIGNALS if k in t or k in d]
        role_hints = [k for k in self.TECH_ROLE_HINTS if k in t]

        score = 0.0
        score += min(len(matched_positive) * 12, 60)  # cap
        score += min(len(role_hints) * 10, 25)
        score -= min(len(matched_negative) * 30, 90)

        # some bonus if company looks like a real employer (weak signal)
        if c and len(c) > 2:
            score += 5

        score = max(0.0, min(100.0, score))

        details = {
            "stage": "heuristic",
            "matched_positive": matched_positive[:30],
            "matched_negative": matched_negative[:30],
            "role_hints": role_hints[:20],
        }
        return score, details

    def _gpt_screen(self, title: str, company: str, location: str, description: str, apply_url: str) -> ScreeningResult:
        """
        Paid step. Returns a structured decision.
        """
        system = (
            "You are a strict MarTech & Marketing Operations job screener for a niche job board called MarTechStack.io. "
            "Your goal: reject noise (sales, generic marketing, MLM, vague roles) and approve high-value technical/operational roles "
            "(MarTech Architect, Marketing Ops Manager, CDP Engineer, Adobe AEP/Launch/CJA, SFMC, Marketo, Braze, Segment, etc.). "
            "Be conservative: if unclear, return PENDING."
        )

        user = {
            "job": {
                "title": title,
                "company": company,
                "location": location,
                "apply_url": apply_url,
                "description": description[:9000],  # keep prompt bounded
            },
            "output_format": {
                "decision": "APPROVE | REJECT | PENDING",
                "score": "0-100 (how strong fit is for MarTech/Marketing Ops niche)",
                "reason": "1-2 sentence justification",
                "signals": {
                    "matched_stack": ["list of stack keywords detected"],
                    "role_type": "short label like 'MarTech Architect' or 'Sales noise'",
                    "red_flags": ["list of red flags if any"],
                },
            },
        }

        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user)},
            ],
        )

        content = resp.choices[0].message.content or ""
        # Parse best-effort JSON from model. If it fails, fallback.
        decision = "PENDING"
        score = 50.0
        reason = "Unclear. Needs review."
        signals = {}

        parsed = None
        try:
            parsed = json.loads(content)
        except Exception:
            # Try to extract JSON blob
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group(0))
                except Exception:
                    parsed = None

        if isinstance(parsed, dict):
            decision = str(parsed.get("decision", decision)).upper()
            try:
                score = float(parsed.get("score", score))
            except Exception:
                score = score
            reason = str(parsed.get("reason", reason))
            signals = parsed.get("signals", {}) if isinstance(parsed.get("signals", {}), dict) else {}

        decision_map = {
            "APPROVE": "approved",
            "REJECT": "rejected",
            "PENDING": "pending",
        }
        status = decision_map.get(decision, "pending")
        score = max(0.0, min(100.0, score))

        return ScreeningResult(
            status=status,
            score=score,
            reason=reason,
            details={
                "stage": "gpt",
                "raw": content,
                "parsed": parsed if isinstance(parsed, dict) else None,
                "signals": signals,
            },
        )

    def screen(self, title: str, company: str, location: str, description: str, apply_url: str) -> ScreeningResult:
        """
        Main entrypoint used by fetch_jobs pipeline.
        """
        # Stage 0: Block rules
        blocked = self._apply_block_rules(title, company, description, apply_url)
        if blocked:
            return blocked

        # Stage 1: Heuristic score
        heuristic_score, heuristic_details = self._heuristic_score(title, company, description)

        # If clearly noise -> reject without GPT
        if heuristic_score < 15:
            return ScreeningResult(
                status="rejected",
                score=heuristic_score,
                reason="Rejected by heuristic score (too weak / likely noise).",
                details={"stage": "heuristic_reject", **heuristic_details},
            )

        # If borderline -> keep pending without GPT (cheap)
        if 15 <= heuristic_score < 40:
            return ScreeningResult(
                status="pending",
                score=heuristic_score,
                reason="Borderline by heuristic. Needs human review.",
                details={"stage": "heuristic_pending", **heuristic_details},
            )

        # Stage 2: GPT (paid) only when likely relevant
        gpt_result = self._gpt_screen(title, company, location, description, apply_url)

        # Combine details
        combined_details = {
            "heuristic_score": heuristic_score,
            "heuristic": heuristic_details,
            "gpt": gpt_result.details,
        }

        return ScreeningResult(
            status=gpt_result.status,
            score=gpt_result.score,
            reason=gpt_result.reason,
            details=combined_details,
        )

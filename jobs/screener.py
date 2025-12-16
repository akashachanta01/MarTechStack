import re

class MarTechScreener:
    """
    The Brain 🧠
    Regex Version: Refined Killers to allow "Partner with Talent Acquisition" 
    and "MarTech Full Stack" roles.
    """
    
    # 1. Define Categories & Keywords
    CATEGORIES = {
        "Automation & Email Platforms": [
            "hubspot", "hubspot marketing hub", "marketo", "adobe marketo",
            "salesforce marketing cloud", "pardot", "sfmc", "exacttarget",
            "activecampaign", "mailchimp", "klaviyo", "sendinblue", "brevo",
            "iterable", "oracle eloqua", "eloqua", "omnisend", "autopilot",
            "marketo engage", "ajo", "adobe journey optimizer",
            "adobe campaign"
        ],
        "Lead Nurturing & Campaign": [
            "braze", "customer.io", "customer io", "iterable", "drip",
            "sharpspring", "ontraport", "constant contact",
            "acoustic campaign", "eloqua"
        ],
        "Web & Product Analytics": [
            "ga4", "google analytics", "google analytics 4", "looker studio",
            "data studio", "hotjar", "mixpanel", "amplitude", "piwik",
            "piwik pro", "fathom analytics", "woopra",
            "microsoft clarity", "bigquery", "heap",
            "adobe analytics", "customer journey analytics", "cja"
        ],
        "Customer Data Platforms": [
            "segment", "twilio segment", "adobe experience platform", "aep",
            "salesforce cdp", "customer 360 audiences", "actioniq",
            "bloomreach engagement", "mparticle", "tealium audiencestream",
            "treasure data", "rudderstack", "blueconic", "lotame",
            "real-time cdp", "rt-cdp"
        ],
        "Tag Management & Tracking": [
            "google tag manager", "gtm", "tealium iq",
            "adobe launch", "dtm", "ensighten",
            "server-side tagging", "stape",
            "segment source", "segment tag manager",
            "server-side tracking"
        ],
    }

    # 2. Assign Weights
    CATEGORY_WEIGHTS = {
        "Customer Data Platforms": 30,
        "Automation & Email Platforms": 25,
        "Lead Nurturing & Campaign": 20,
        "Tag Management & Tracking": 15,
        "Web & Product Analytics": 10
    }

    # 3. Job Killers (Refined)
    JOB_KILLERS = [
        # Content / Social
        r'writing.*blog.*posts', r'content.*creation', r'social.*media.*management',
        r'brand.*manager', r'copywriter', 
        
        # Sales
        r'cold.*calling', r'sales.*representative', r'account.*executive', 
        r'account.*director', r'business.*development', r'customer.*success',

        # HR / Recruiting (Specific Roles Only)
        r'hr.*manager', r'recruiter', 
        r'talent.*acquisition.*manager',     # 🟢 CHANGED: Only blocks Managers
        r'talent.*acquisition.*specialist',  # 🟢 CHANGED: Only blocks Specialists
        r'head.*of.*talent',
        
        # Engineering (Removed Full Stack to allow MarTech Engineers)
        r'software.*engineer', r'frontend.*engineer', r'backend.*engineer',
        # REMOVED: r'full.*stack',  <-- TRUST THE SCORE SYSTEM INSTEAD
        r'platform.*engineer', r'site.*reliability',
        r'devops', r'engineering.*manager', r'director.*engineering',
        r'solutions.*engineer', r'technical.*support'
    ]
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.found_categories = []
        self.found_stack = []
    
    def clean_text(self, text):
        return str(text).lower().strip()
    
    def is_present(self, text, keyword):
        pattern = r'\b' + re.escape(keyword) + r'\b'
        return re.search(pattern, text) is not None

    def screen_job(self, title, description):
        self.reset()
        full_text = self.clean_text(f"{title} {description}")
        
        # 1. Check Killers
        for pattern in self.JOB_KILLERS:
            if re.search(pattern, full_text):
                return {
                    "is_match": False, 
                    "score": 0, 
                    "reason": f"Killer: {pattern}", 
                    "stack": [], 
                    "categories": []
                }

        # 2. Scan Categories
        total_score = 0
        
        for category, keywords in self.CATEGORIES.items():
            matches = [kw for kw in keywords if self.is_present(full_text, kw)]
            
            if matches:
                self.found_categories.append(category)
                self.found_stack.extend(matches)
                total_score += self.CATEGORY_WEIGHTS.get(category, 10)

        # 3. Decision Logic (Threshold = 20)
        is_match = total_score >= 20

        return {
            "is_match": is_match,
            "score": total_score,
            "stack": list(set(self.found_stack)), 
            "categories": self.found_categories,  
            "role_type": self.infer_role_type()
        }

    def infer_role_type(self):
        cats = self.found_categories
        if "Customer Data Platforms" in cats or "Tag Management & Tracking" in cats:
            return "MarTech Engineer/Architect"
        if "Automation & Email Platforms" in cats:
            return "Marketing Operations"
        if "Web & Product Analytics" in cats:
            return "Marketing Analyst"
        return "Marketing Technologist"

import re

class MarTechScreener:
    """
    The Brain 🧠
    Final Architecture: "Title-Shield" Edition.
    1. KILLERS are applied ONLY to the Job Title (Prevents "Reports to X" false positives).
    2. SCORING is applied to the Full Text (Finds keywords anywhere).
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

    # 3. Job Killers (Applied to TITLE ONLY)
    # We can now be very strict here without fear.
    TITLE_KILLERS = [
        # Sales & Account Mgmt
        r'sales', r'account.*executive', r'account.*manager', r'account.*director',
        r'business.*development', r'bdr', r'sdr',
        r'client.*partner', r'client.*success',
        
        # Customer Success (Blocks ALL CS titles)
        r'customer.*success', r'csm', r'customer.*experience', r'support.*specialist',
        
        # General Marketing (Too broad)
        r'marketing.*manager', r'brand.*manager', r'digital.*marketing.*manager',
        r'content', r'social.*media', r'community', r'pr\b', r'public.*relations',
        r'copywriter', r'writer', r'editor',
        r'creative', r'graphic', r'designer', r'videographer',
        
        # HR & Admin
        r'recruiter', r'talent', r'hr\b', r'human.*resources',
        r'assistant', r'admin', r'office.*manager',
        
        # Pure Engineering (Unless they pass the specific keyword score)
        r'software.*engineer', r'frontend', r'backend', r'full.*stack',
        r'mobile.*developer', r'ios', r'android',
        r'devops', r'site.*reliability'
    ]
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.found_categories = []
        self.found_stack = []
    
    def clean_text(self, text):
        return str(text).lower().strip()
    
    def is_present(self, text, keyword):
        # Enforce Word Boundaries
        pattern = r'\b' + re.escape(keyword) + r'\b'
        return re.search(pattern, text) is not None

    def screen_job(self, title, description):
        self.reset()
        clean_title = self.clean_text(title)
        full_text = self.clean_text(f"{title} {description}")
        
        # 1. Check Killers (AGAINST TITLE ONLY) 🛡️
        for pattern in self.TITLE_KILLERS:
            if re.search(pattern, clean_title):
                return {
                    "is_match": False, 
                    "score": 0, 
                    "reason": f"Title Killer: {pattern}", 
                    "stack": [], 
                    "categories": []
                }

        # 2. Scan Categories (Against Full Text)
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

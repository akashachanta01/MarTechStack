import re

class MarTechScreener:
    """
    The Brain 🧠
    Regex Version: "False-Positive Proof" Edition.
    Killers are now strictly role-specific to allow cross-functional collaboration.
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

    # 3. Job Killers (The "False-Positive Proof" List)
    JOB_KILLERS = [
        # --- Pure Content / Social Roles ---
        # (We keep these strict because MarTech rarely does pure blogging)
        r'writing.*blog.*posts', 
        r'social.*media.*manager', # Changed from 'management' to 'manager'
        r'social.*media.*specialist',
        r'brand.*manager', 
        r'copywriter', 
        
        # --- Sales Roles (Specific Titles Only) ---
        # Allows: "Support Sales Team", "Sales Operations"
        # Kills: "Sales Representative", "Account Executive"
        r'sales.*representative', 
        r'account.*executive', 
        r'account.*director', 
        r'sales.*development.*rep',
        r'business.*development.*rep',
        r'outside.*sales',
        r'inside.*sales',
        
        # --- Customer Success (Specific Titles Only) ---
        # Allows: "Work with Customer Success", "CS Operations"
        # Kills: "Customer Success Manager"
        r'customer.*success.*manager',
        r'client.*success.*manager',
        r'customer.*success.*representative',
        
        # --- HR / Recruiting (Specific Titles Only) ---
        # Allows: "Partner with Talent Acquisition"
        # Kills: "Recruiter", "Talent Acquisition Manager"
        r'hr.*manager', 
        r'human.*resources',
        r'recruiter', 
        r'talent.*acquisition.*manager',     
        r'talent.*acquisition.*specialist',  
        r'talent.*scout',
        
        # --- Engineering (Specific Titles Only) ---
        # Allows: "MarTech Engineer", "Full Stack (if high score)"
        # Kills: "Software Engineer", "Frontend Dev"
        r'software.*engineer', 
        r'frontend.*developer', 
        r'frontend.*engineer',
        r'backend.*developer', 
        r'backend.*engineer',
        r'site.*reliability.*engineer',
        r'devops.*engineer',
        # Removed 'full stack', 'solutions engineer', 'product manager' 
        # to trust the Score System.
    ]
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.found_categories = []
        self.found_stack = []
    
    def clean_text(self, text):
        return str(text).lower().strip()
    
    def is_present(self, text, keyword):
        # Enforce Word Boundaries to prevent partial matches
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

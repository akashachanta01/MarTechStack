import re

class MarTechScreener:
    """
    The Brain 🧠
    Final "Title-Only" Version.
    Replaces "Activity Blockers" (risky) with "Title Blockers" (safe).
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

    # 3. Job Killers (Title-Based Only)
    JOB_KILLERS = [
        # --- CREATIVE & CONTENT TITLES ---
        # (Removed 'content creation' activity blocker)
        r'content.*writer', r'copywriter', r'editor', r'journalist',
        r'graphic.*designer', r'art.*director', r'creative.*director',
        r'video.*editor', r'videographer',
        r'social.*media.*manager', r'community.*manager',
        r'brand.*manager', r'pr.*manager', r'public.*relations',

        # --- SALES TITLES ---
        # (Removed generic 'sales' or 'business development' activity blockers)
        r'sales.*representative', r'sales.*rep', 
        r'account.*executive', r'ae\b', # Be careful with short acronyms
        r'account.*director', 
        r'business.*development.*rep', r'bdr',
        r'sales.*development.*rep', r'sdr',
        r'outside.*sales', r'inside.*sales',
        
        # --- CUSTOMER SUCCESS TITLES ---
        # (Allows 'Work with Customer Success')
        r'customer.*success.*manager', r'csm',
        r'client.*success.*manager',
        r'customer.*support.*rep',
        r'customer.*service',

        # --- HR & ADMIN TITLES ---
        r'recruiter', r'sourcer', r'talent.*acquisition.*manager',
        r'hr.*manager', r'human.*resources',
        r'executive.*assistant', r'admin.*assistant', r'office.*manager',

        # --- PURE ENGINEERING TITLES ---
        # (Allows MarTech Engineers / Architects)
        r'software.*engineer', 
        r'frontend.*developer', r'frontend.*engineer',
        r'backend.*developer', r'backend.*engineer',
        r'mobile.*developer', r'ios.*developer', r'android.*developer',
        r'site.*reliability', r'devops.*engineer'
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

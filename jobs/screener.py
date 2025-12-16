import re

class MarTechScreener:
    """
    The Brain 🧠
    Final Architecture: "Narcissism-Penalty" Edition.
    1. Blocks "Vendor Self-Scoring" (If Company == Keyword, Score = 0).
    2. Blocks "Solutions Engineering" (Pre-Sales) and "Internal IT".
    3. Blocks "Creative" and "Programmatic" roles.
    """
    
    # 1. Define Categories & Keywords
    CATEGORIES = {
        "Automation & Email Platforms": [
            "hubspot", "hubspot marketing hub", "marketo", "adobe marketo",
            "salesforce marketing cloud", "pardot", "sfmc", "exacttarget",
            "activecampaign", "mailchimp", "klaviyo", "sendinblue", "brevo",
            "iterable", "oracle eloqua", "eloqua", "omnisend", "autopilot",
            "marketo engage", "ajo", "adobe journey optimizer",
            "adobe campaign", "customer.io" # Added customer.io explicitly
        ],
        "Lead Nurturing & Campaign": [
            "braze", "customer.io", "iterable", "drip",
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
    TITLE_KILLERS = [
        # --- VENDOR & PRE-SALES (The Cloudflare/Samsara Fix) ---
        r'solutions.*engineer', # Pre-sales technical role
        r'solutions.*consultant',
        r'sales.*engineer',
        r'presales', r'pre-sales',
        r'solutions.*architect', # Often pre-sales unless rescued
        r'value.*engineer',
        r'developer.*advocate', r'developer.*relations',
        r'banking.*specialist', # Brex Fix
        
        # --- INTERNAL IT & OPS (The Customer.io Fix) ---
        r'internal.*it', 
        r'director.*it', r'head.*of.*it', r'vp.*it',
        r'system.*admin', r'sysadmin',
        r'network.*engineer', r'security.*engineer',
        r'help.*desk', r'desktop.*support',
        
        # --- ADTECH & PROGRAMMATIC (The StackAdapt Fix) ---
        r'programmatic', 
        r'ad.*ops', r'ad.*operations',
        r'campaign.*manager', # Usually manual ad execution
        r'media.*buyer', r'trafficker',
        
        # --- CREATIVE & STRATEGY (The Flo Health Fix) ---
        r'creative.*strategist', 
        r'brand.*strategist',
        r'social.*media', r'paid.*social',
        r'copywriter', r'content',
        
        # --- CORPORATE BACK-OFFICE ---
        r'finance', r'accounting', r'controller', r'treasury', r'tax',
        r'legal', r'counsel', r'compliance', r'privacy',
        r'deal.*desk', r'order.*management',
        r'hr\b', r'human.*resources', r'recruiting', r'talent',
        r'people.*ops', r'workplace', r'facilities',
        
        # --- COMMERCIAL & SALES ---
        r'account.*executive', r'ae\b', 
        r'account.*manager', # StackAdapt Fix
        r'customer.*success', r'csm', 
        r'sales', r'business.*development', r'bdr', r'sdr',
        r'growth', r'acquisition',
        
        # --- PURE ENGINEERING ---
        r'software.*engineer', r'frontend', r'backend', r'full.*stack',
        r'mobile.*developer', r'ios', r'android',
        r'devops', r'site.*reliability'
    ]

    # 4. The Rescue List 🚑 (Saves a job even if it hit a Killer)
    TITLE_SAFELIST = [
        r'martech', 
        r'marketing.*technology', 
        r'marketing.*operations', 
        r'marketing.*platform',
        r'marketing.*systems',
        r'marketing.*automation',
        r'technical.*product.*manager',
        r'data.*platform'
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

    def screen_job(self, title, description, company_name=""):
        self.reset()
        clean_title = self.clean_text(title)
        clean_company = self.clean_text(company_name)
        full_text = self.clean_text(f"{title} {description}")
        
        # 1. Check Killers (AGAINST TITLE ONLY) 🛡️
        killer_found = False
        killer_reason = ""
        
        for pattern in self.TITLE_KILLERS:
            if re.search(pattern, clean_title):
                killer_found = True
                killer_reason = pattern
                break
        
        # 2. Check Rescue List (If Killer Found) 🚑
        if killer_found:
            is_rescued = False
            for safe_pattern in self.TITLE_SAFELIST:
                if re.search(safe_pattern, clean_title):
                    is_rescued = True
                    break
            
            if not is_rescued:
                return {
                    "is_match": False, 
                    "score": 0, 
                    "reason": f"Title Killer: {killer_reason} (Not Rescued)", 
                    "stack": [], 
                    "categories": []
                }

        # 3. Scan Categories (With Narcissism Penalty)
        total_score = 0
        
        for category, keywords in self.CATEGORIES.items():
            matches = []
            for kw in keywords:
                # NARCISSISM CHECK: 
                # If the keyword (e.g. "hubspot") is in the company name (e.g. "HubSpot"), ignore it.
                if clean_company and kw in clean_company:
                    continue
                    
                if self.is_present(full_text, kw):
                    matches.append(kw)
            
            if matches:
                self.found_categories.append(category)
                self.found_stack.extend(matches)
                total_score += self.CATEGORY_WEIGHTS.get(category, 10)

        # 4. Decision Logic (Threshold = 20)
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

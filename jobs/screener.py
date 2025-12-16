import re

class MarTechScreener:
    """
    The Brain 🧠
    Final Architecture: "Corporate-Shield" Edition.
    1. Blocks "Vendor Self-Scoring" by killing internal Corporate/Back-Office titles.
    2. Protects legitimate MarTech roles via the Rescue List.
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
    TITLE_KILLERS = [
        # --- CORPORATE BACK-OFFICE (The "Braze" Fix) ---
        # Finance & Legal
        r'finance', r'financial', r'accounting', r'controller', r'treasury', r'tax',
        r'audit', r'payroll', r'billing', r'procurement', r'purchasing', r'buyer',
        r'legal', r'lawyer', r'counsel', r'compliance', r'privacy', r'regulatory',
        r'deal.*desk', r'order.*management',
        r'investor.*relations', r'corporate.*development', r'm&a',
        
        # HR, People, Workplace
        r'hr\b', r'human.*resources', r'people', r'employee', r'culture', 
        r'talent', r'recruiting', r'recruiter', r'sourcer',
        r'learning', r'training', r'instructor',
        r'workplace', r'facilities', r'real.*estate', r'office',
        r'executive.*assistant', r'admin', r'receptionist', r'coordinator',
        r'chief.*of.*staff',

        # Generic IT (Not MarTech)
        r'help.*desk', r'service.*desk', r'it.*support', r'desktop', 
        r'system.*admin', r'network', r'security', r'ciso',

        # --- CLIENT SERVICES & SUPPORT ---
        r'consultant', r'consulting', r'implementation', r'onboarding',
        r'technical.*account.*manager', r'tam\b',
        r'customer.*support', r'technical.*support', r'support.*engineer',
        r'enablement', r'solution.*architect', r'professional.*services',
        
        # --- PRODUCT & PROGRAM ---
        r'product.*manager', r'product.*owner', r'product.*lead',
        r'head.*of.*product', r'vp.*product',
        r'program.*manager', r'project.*manager',
        
        # --- COMMERCIAL & REVENUE ---
        r'monetization', r'revenue', r'pricing', r'commercial',
        
        # --- PAID MEDIA & PERFORMANCE ---
        r'acquisition', r'performance.*marketing',
        r'paid.*media', r'paid.*social', r'paid.*search',
        r'sem\b', r'ppc\b', r'seo\b',
        r'media.*buyer', r'ad.*ops', r'trafficker',
        r'demand.*generation', r'lead.*generation',
        r'growth',

        # --- BUSINESS & STRATEGY ---
        r'^data.*analyst', r'senior.*data.*analyst',
        r'business.*intelligence', r'bi.*developer',
        r'data.*scientist', r'data.*engineer',
        r'strategy', r'strategic', r'go-to-market',
        r'loyalty', r'ecommerce', r'e-commerce', r'merchandis',
        r'partnership', r'affiliate', r'influencer',
        
        # --- NON-TECH MARKETING ---
        r'brand', r'content', r'copywriter', r'writer', r'editor',
        r'social.*media', r'community', r'pr\b', r'public.*relations',
        r'communications', r'product.*marketing', 
        r'field.*marketing', r'event', r'digital.*marketing', r'email.*marketing',

        # --- SALES & CS ---
        r'sales', r'account.*executive', r'account.*manager', r'account.*director',
        r'business.*development', r'bdr', r'sdr',
        r'client.*partner', r'client.*success',
        r'customer.*success', r'csm', r'customer.*experience', r'support.*specialist',
        
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

    def screen_job(self, title, description):
        self.reset()
        clean_title = self.clean_text(title)
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

        # 3. Scan Categories (Against Full Text)
        total_score = 0
        
        for category, keywords in self.CATEGORIES.items():
            matches = [kw for kw in keywords if self.is_present(full_text, kw)]
            
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

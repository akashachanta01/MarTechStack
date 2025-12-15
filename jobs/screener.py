import re

class MarTechScreener:
    """
    The Brain 🧠
    PM-Friendly Version: Allows MarTech Product Managers, blocks generic Engineers.
    """
    
    # GROUP A: Adobe Heavyweights & Enterprise CDPs (Score: 30)
    GROUP_A = [
        'adobe experience platform', 'aep', 'adobe analytics', 'adobe launch', 
        'customer journey analytics', 'cja', 'adobe journey optimizer', 'ajo',
        'adobe gen studio', 'adobe experience manager', 'aem', 'real-time cdp', 'rt-cdp',
        'adobe target', 'adobe campaign', 'marketo', 'adobe marketo'
    ]
    
    # GROUP B: CRM & Automation (Score: 20)
    GROUP_B = [
        'salesforce marketing cloud', 'sfmc', 'exacttarget', 'ampscript',
        'eloqua', 'pardot', 'braze', 'customer.io', 'iterable', 'moengage',
        'hubspot', 'hubspot operations', 'hubspot workflows', 'hubspot custom objects',
        'salesforce', 'salesforce crm', 'sfdc',
        'marketing technologist', 'martech developer', 'marketing technology' 
    ]
    
    # GROUP C: Data & Technical Skills (Score: 15)
    GROUP_C = [
        'javascript', 'gtm', 'google tag manager', 'server-side tracking',
        'tealium', 'mparticle', 'segment', 'segment.io',
        'sql', 'python', 'api', 'api integration', 'webhooks', 'json', 'html', 'css',
        'snowflake', 'bigquery', 'dbt', 'reverse etl', 'hightouch', 'census'
    ]
    
    # JOB KILLERS: Immediate Rejects (Wrong Role)
    # UPDATED: Removed Product Manager blockers. 
    # Still blocks Software Engineers and Sales.
    JOB_KILLERS = [
        # --- Content/Social/Generic Marketing ---
        r'writing.*blog.*posts',
        r'content.*creation',
        r'social.*media.*management',
        r'brand.*manager',
        r'copywriter',
        
        # --- Sales & HR ---
        r'cold.*calling',
        r'sales.*representative',
        r'account.*executive',
        r'account.*director',
        r'business.*development',
        r'hr.*manager',
        r'recruiter',
        r'talent.*acquisition',
        r'customer.*success', # CSMs usually don't build stacks
        
        # --- "Vendor Engineering" Firewall ---
        r'software.*engineer', 
        r'frontend.*engineer',
        r'backend.*engineer',
        r'full.*stack',
        r'platform.*engineer',
        r'site.*reliability',
        r'devops',
        r'engineering.*manager',
        r'director.*engineering',
        # REMOVED: product manager/owner are now ALLOWED ✅
        r'solutions.*engineer', # Still blocked (usually pre-sales)
        r'technical.*support'
    ]
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.matches_a = []
        self.matches_b = []
        self.matches_c = []
        self.has_killer = False

    def clean_text(self, text):
        return str(text).lower().strip()
    
    def screen_job(self, title, description):
        self.reset()
        full_text = self.clean_text(f"{title} {description}")
        
        # 1. Check for Killers first
        for pattern in self.JOB_KILLERS:
            if re.search(pattern, full_text):
                return {"is_match": False, "reason": f"Job Killer: {pattern}", "stack": [], "role_type": "None"}

        # 2. Find Matches
        self.matches_a = [kw for kw in self.GROUP_A if kw in full_text]
        self.matches_b = [kw for kw in self.GROUP_B if kw in full_text]
        self.matches_c = [kw for kw in self.GROUP_C if kw in full_text]
        
        # 3. Score It
        score = (len(self.matches_a) * 30) + (len(self.matches_b) * 20) + (len(self.matches_c) * 15)
        
        # 4. Smart Decision Logic 🧠
        # High Bar: Must have Score >= 30 OR be a strong technical match
        # This prevents "Generic PM" (0 pts) from passing, but allows "MarTech PM" (30+ pts).
        is_match = False
        
        if score >= 30:
            is_match = True
        elif self.matches_c and score >= 25: 
            is_match = True
            
        # 5. Compile Stack
        stack = list(set(self.matches_a + self.matches_b + self.matches_c))
        
        return {
            "is_match": is_match,
            "score": score,
            "stack": stack,
            "role_type": self.infer_role_type()
        }

    def infer_role_type(self):
        if self.matches_c and not self.matches_a and not self.matches_b:
            return "Technical/Data"
        if self.matches_a:
            return "Implementation/Architect"
        return "Marketing Operations"

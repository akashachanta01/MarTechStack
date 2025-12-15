import re

class MarTechScreener:
    """
    The Brain 🧠
    Filters jobs based on HARD SKILLS (Stack) vs. Generic Titles.
    """
    
    # GROUP A: Adobe Heavyweights (Score: 30)
    GROUP_A = [
        'adobe experience platform', 'aep', 'adobe analytics', 'adobe launch', 
        'customer journey analytics', 'cja', 'adobe journey optimizer', 'ajo',
        'adobe gen studio', 'adobe experience manager', 'aem', 'real-time cdp', 
        'adobe target', 'adobe campaign', 'marketo', 'adobe marketo'
    ]
    
    # GROUP B: Enterprise Automation & CRM (Score: 20)
    GROUP_B = [
        'salesforce marketing cloud', 'sfmc', 'exacttarget', 'ampscript',
        'eloqua', 'pardot', 'braze', 'customer.io', 'iterable', 'moengage',
        'hubspot operations', 'hubspot workflows', 'hubspot custom objects'
    ]
    
    # GROUP C: Data, Code & Infrastructure (Score: 15)
    # UPDATED: Restricted to your specific list
    GROUP_C = [
        'javascript', 'gtm', 'google tag manager', 'server-side tracking'
    ]
    
    # JOB KILLERS: Immediate Rejects (Wrong Role)
    JOB_KILLERS = [
        r'writing.*blog.*posts',
        r'content.*creation',
        r'social.*media.*management',
        r'cold.*calling',
        r'sales.*representative',
        r'account.*executive',
        r'hr.*manager',
        r'recruiter'
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
        
        # 4. Decision Logic
        # Must have at least ONE strong tool match
        total_keywords = len(self.matches_a) + len(self.matches_b) + len(self.matches_c)
        is_match = total_keywords >= 1

        # 5. Compile Stack for Auto-Tagging
        stack = list(set(self.matches_a + self.matches_b + self.matches_c))
        
        return {
            "is_match": is_match,
            "score": score,
            "stack": stack,
            "role_type": self.infer_role_type()
        }

    def infer_role_type(self):
        if self.matches_c:
            return "Technical/Developer"
        if self.matches_a:
            return "Implementation/Architect"
        return "Marketing Operations"

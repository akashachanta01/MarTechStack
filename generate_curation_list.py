import os
import requests
import csv
import time
import re

# --- CONFIGURATION ---
ADZUNA_ID = "a86969e3"   # <--- PASTE ID HERE
ADZUNA_KEY = "026f38bf55fd903b16e4663fa41c34fb" # <--- PASTE KEY HERE
OUTPUT_FILE = "martech_curation_list.csv"
TARGET_COUNT = 100

# --- SEARCH TERMS ---
# We search broadly, then use the Screener to filter tightly
SEARCH_TERMS = [
    'Marketo', 'Salesforce Marketing Cloud', 'HubSpot Operations', 
    'Adobe Experience Platform', 'Marketing Operations', 
    'Braze', 'Segment.io', 'Marketing Technologist',
    'Adobe Analytics', 'Tealium'
]

# --- THE SCREENER (Your "Brain" Logic) ---
class MarTechScreener:
    GROUP_A = [
        'adobe experience platform', 'aep', 'adobe analytics', 'adobe launch', 
        'customer journey analytics', 'cja', 'adobe journey optimizer', 'ajo',
        'adobe gen studio', 'adobe experience manager', 'aem', 'real-time cdp', 
        'adobe target', 'adobe campaign', 'marketo', 'adobe marketo'
    ]
    
    GROUP_B = [
        'salesforce marketing cloud', 'sfmc', 'exacttarget', 'ampscript',
        'eloqua', 'pardot', 'braze', 'customer.io', 'iterable', 'moengage',
        'hubspot operations', 'hubspot workflows', 'hubspot custom objects'
    ]
    
    GROUP_C = [
        'sql', 'python', 'r language', 'snowflake', 'bigquery', 'redshift',
        'dbt', 'reverse etl', 'hightouch', 'census', 'segment', 'tealium',
        'mparticle', 'api integration', 'webhooks', 'json',
        'javascript', 'gtm', 'google tag manager', 'server-side tracking'
    ]
    
    JOB_KILLERS = [
        r'writing.*blog.*posts', r'content.*creation', r'social.*media.*management',
        r'cold.*calling', r'sales.*representative', r'account.*executive',
        r'hr.*manager', r'recruiter'
    ]
    
    def clean_text(self, text):
        return str(text).lower().strip()
    
    def screen_job(self, title, description):
        full_text = self.clean_text(f"{title} {description}")
        
        # 1. Check for Killers
        for pattern in self.JOB_KILLERS:
            if re.search(pattern, full_text):
                return {"is_match": False, "reason": "Killer"}

        # 2. Find Matches
        matches_a = [kw for kw in self.GROUP_A if kw in full_text]
        matches_b = [kw for kw in self.GROUP_B if kw in full_text]
        matches_c = [kw for kw in self.GROUP_C if kw in full_text]
        
        # 3. Decision Logic
        total_keywords = len(matches_a) + len(matches_b) + len(matches_c)
        is_match = total_keywords >= 1 

        stack = list(set(matches_a + matches_b + matches_c))
        
        return {
            "is_match": is_match,
            "stack": stack,
            "role_type": self.infer_role_type(matches_a, matches_c)
        }

    def infer_role_type(self, matches_a, matches_c):
        if matches_c:
            if any(x in matches_c for x in ['sql', 'python', 'snowflake']):
                return "Data / Eng"
            return "Technical"
        if matches_a:
            return "Implementation"
        return "Operations"

# --- MAIN EXECUTION ---
def generate_list():
    print("🚀 Starting Smart Adzuna Export...")
    screener = MarTechScreener()
    collected_jobs = []
    seen_urls = set()

    with open(OUTPUT_FILE, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Title', 'Company', 'Location', 'Apply URL', 'Tech Stack (Detected)', 'Role Type', 'Snippet'])

        for term in SEARCH_TERMS:
            if len(collected_jobs) >= TARGET_COUNT:
                break
                
            print(f"🔎 Searching for: {term}...")
            url = "http://api.adzuna.com/v1/api/jobs/us/search/1"
            params = {
                'app_id': ADZUNA_ID, 
                'app_key': ADZUNA_KEY, 
                'results_per_page': 50, 
                'what': term, 
                'content-type': 'application/json'
            }
            
            try:
                resp = requests.get(url, params=params, timeout=10)
                if resp.status_code != 200:
                    print(f"   ❌ API Error: {resp.status_code}")
                    continue
                
                results = resp.json().get('results', [])
                for item in results:
                    if len(collected_jobs) >= TARGET_COUNT: break

                    url = item.get('redirect_url')
                    if url in seen_urls: continue

                    # SCREEN IT
                    title = item.get('title')
                    desc = item.get('description')
                    analysis = screener.screen_job(title, desc)
                    
                    if analysis['is_match']:
                        seen_urls.add(url)
                        clean_stack = ", ".join(analysis['stack'])
                        
                        row = [
                            title,
                            item.get('company', {}).get('display_name'),
                            item.get('location', {}).get('display_name'),
                            url,
                            clean_stack,
                            analysis['role_type'],
                            desc
                        ]
                        writer.writerow(row)
                        collected_jobs.append(row)
                        print(f"   ✅ Matched: {title} ({len(analysis['stack'])} tools)")
            
            except Exception as e:
                print(f"   ⚠️ Error: {e}")
            
            time.sleep(1.5)

    print(f"\n✨ DONE! Saved {len(collected_jobs)} filtered jobs to '{OUTPUT_FILE}'.")
    print("👉 Open the CSV, check the links, and add the best ones to your Admin Portal.")

if __name__ == '__main__':
    if "YOUR_ADZUNA_ID" in ADZUNA_ID:
        print("⚠️  PLEASE ENTER YOUR API KEYS IN THE SCRIPT FIRST ⚠️")
    else:
        generate_list()

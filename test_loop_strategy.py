import os
import requests
import time
from django.conf import settings

# 1. SETUP (Mock Django settings to read the file path easily if needed, or just use os)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERPAPI_KEY = os.environ.get('SERPAPI_KEY')

if not SERPAPI_KEY:
    print("❌ ERROR: SERPAPI_KEY not found. Cannot run test.")
    exit()

# 2. LOAD TARGETS (Simulating the new logic)
# We will just pick the "Hard" ones to prove the point.
# In the real script, we would read the whole file.
TEST_TARGETS = [
    "Bloomreach",       # The one you missed
    "MarTech",          # The generic one
    "AEP",              # Adobe Ecosystem
    "Tealium",          # Data Ecosystem
    "mParticle"         # Data Ecosystem
]

# 3. THE STRATEGY
def run_test():
    print(f"🧪 TESTING 'KEYWORD LOOP' STRATEGY on {len(TEST_TARGETS)} targets...\n")

    for keyword in TEST_TARGETS:
        print(f"🔎 Target: {keyword}")
        
        # THE NEW QUERY LOGIC
        # We look for the Keyword explicitly in the Title of the job page
        query = f'(site:greenhouse.io OR site:lever.co) intitle:"{keyword}"'
        
        print(f"   Query: {query}")
        
        try:
            params = {
                "engine": "google",
                "q": query,
                "api_key": SERPAPI_KEY,
                "num": 3, # Just fetch top 3 to prove it works
                "gl": "us",
                "hl": "en"
            }
            
            resp = requests.get("https://serpapi.com/search", params=params, timeout=10)
            results = resp.json().get("organic_results", [])
            
            if not results:
                print("   ⚠️  No results found.")
            
            for item in results:
                title = item.get("title")
                link = item.get("link")
                
                # Extract the "Hub" (Company Name) from the URL
                company = "Unknown"
                if "greenhouse.io" in link:
                    # Clean URL to get company token
                    # ex: https://boards.greenhouse.io/bloomreach/jobs/123 -> bloomreach
                    parts = link.split('/')
                    if 'greenhouse.io' in parts[2]:
                        # usually part 3 or 4 depending on subdomain
                        # simplest way: look for the part after the domain
                        for p in parts:
                            if p not in ['https:', '', 'boards.greenhouse.io', 'jobs', 'embed']:
                                company = p
                                break
                
                print(f"   ✅ FOUND: {title}")
                print(f"      🔗 {link}")
                print(f"      🏢 HUB DISCOVERED: {company}")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            
        print("-" * 40)
        time.sleep(1) # Be polite

if __name__ == '__main__':
    run_test()

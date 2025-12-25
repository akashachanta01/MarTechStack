import os
import requests
import time

# 1. CONFIGURATION
SERPAPI_KEY = os.environ.get('SERPAPI_KEY')
FILE_NAME = 'hunt_targets.txt'

if not SERPAPI_KEY:
    print("❌ ERROR: SERPAPI_KEY not found. Cannot run test.")
    exit()

if not os.path.exists(FILE_NAME):
    print(f"❌ ERROR: Could not find '{FILE_NAME}' in this directory.")
    print("   Make sure you are running this from the same folder as the text file.")
    exit()

def run_test():
    # 2. LOAD REAL TARGETS
    targets = []
    with open(FILE_NAME, 'r') as f:
        for line in f:
            clean = line.strip()
            # Skip comments and empty lines
            if clean and not clean.startswith('#'):
                targets.append(clean)

    print(f"📋 Loaded {len(targets)} keywords from {FILE_NAME}")
    print(f"🧪 TESTING 'INTITLE' STRATEGY (Top 3 results per keyword)...")
    print("="*60)

    # 3. EXECUTE LOOP
    for keyword in targets:
        # We search specifically for the tool in the job title on ATS sites
        query = f'(site:greenhouse.io OR site:lever.co OR site:ashbyhq.com) intitle:"{keyword}"'
        
        print(f"\n🔎 Hunting: {keyword}")
        
        try:
            params = {
                "engine": "google",
                "q": query,
                "api_key": SERPAPI_KEY,
                "num": 3,  # Low number to save credits/time for test
                "gl": "us",
                "hl": "en"
            }
            
            resp = requests.get("https://serpapi.com/search", params=params, timeout=10)
            data = resp.json()
            results = data.get("organic_results", [])
            
            if not results:
                # If Google returns nothing, it might be a rate limit or just a rare keyword
                if "error" in data:
                    print(f"   ⚠️ API Error: {data['error']}")
                else:
                    print("   ⚠️  No jobs found with this specific title.")
            
            for item in results:
                title = item.get("title", "No Title")
                link = item.get("link", "No Link")
                
                # Extract Company Name (The "Hub")
                company = "Unknown"
                if "greenhouse.io" in link:
                    # https://boards.greenhouse.io/bloomreach/jobs/123
                    parts = link.split('/')
                    # Simple heuristic to grab the company slug
                    for p in parts:
                        if p not in ['https:', '', 'boards.greenhouse.io', 'jobs', 'embed', 'www.greenhouse.io']:
                            company = p
                            break
                elif "lever.co" in link:
                    # https://jobs.lever.co/valtech/123
                    parts = link.split('/')
                    if len(parts) > 3: company = parts[3]
                
                print(f"   ✅ FOUND: {title}")
                print(f"      🔗 {link}")
                print(f"      🏢 HUB: {company}")

        except Exception as e:
            print(f"   ❌ System Error: {e}")
            
        # Sleep to avoid hitting Google's rate limit during the test
        time.sleep(1.5) 

    print("\n" + "="*60)
    print("✨ TEST COMPLETE.")

if __name__ == '__main__':
    run_test()

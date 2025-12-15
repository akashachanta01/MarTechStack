import sys
import re
import requests
from jobs.screener import MarTechScreener

def test_url(url):
    print(f"\n🕵️‍♂️ Auditing URL: {url}")
    
    # 1. Extract Token
    token = None
    if "greenhouse.io" in url:
        match = re.search(r'greenhouse\.io/([^/]+)', url)
        if match: token = match.group(1)
    
    if not token:
        print("❌ FAILED: Could not extract company token.")
        return

    # 2. Fetch Job
    print(f"⏳ Fetching API for {token}...")
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    
    try:
        resp = requests.get(api_url, timeout=10)
        jobs = resp.json().get('jobs', [])
    except:
        print("❌ Connection Error")
        return

    # 3. Find Specific Job ID
    job_id_match = re.search(r'jobs/(\d+)', url)
    if not job_id_match:
        print("❌ Could not find Job ID in URL.")
        return

    target_id = int(job_id_match.group(1))
    target_job = next((j for j in jobs if j['id'] == target_id), None)
    
    if target_job:
        print(f"✅ Found Job: {target_job['title']}")
        
        # 4. Run Screener
        screener = MarTechScreener()
        analysis = screener.screen_job(target_job['title'], target_job['content'])
        
        print(f"\n🧠 SCREENER RESULTS:")
        print(f"   - Match: {analysis['is_match']}")
        print(f"   - Score: {analysis['score']} (Needs 20)")
        print(f"   - Stack: {analysis['stack']}")
        print(f"   - Killers: {analysis.get('reason', 'None')}")
    else:
        print("⚠️ Job ID not found in API (Job might be closed).")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_job.py <url>")
    else:
        test_url(sys.argv[1])

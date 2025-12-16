import sys
import re
import requests
from jobs.screener import MarTechScreener

def get_headers():
    return {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

def sniff_token(url):
    print(f"🐕 Sniffing for hidden ATS token in {url}...")
    try:
        resp = requests.get(url, headers=get_headers(), timeout=10)
        if resp.status_code != 200:
            print(f"❌ Could not access page. Status: {resp.status_code}")
            return None, None
            
        html = resp.text
        
        # 1. Try Greenhouse Pattern (iframe or script)
        # Matches: boards.greenhouse.io/TOKEN or grnhse.load_demo('TOKEN')
        gh_match = re.search(r'greenhouse\.io/([^/"\'?]+)', html)
        if gh_match: return "greenhouse", gh_match.group(1)
        
        gh_js_match = re.search(r'grnhse\.load_demo\([\'"]([^\'"]+)[\'"]\)', html)
        if gh_js_match: return "greenhouse", gh_js_match.group(1)

        # 2. Try Lever Pattern
        lever_match = re.search(r'jobs\.lever\.co/([^/"\'?]+)', html)
        if lever_match: return "lever", lever_match.group(1)

    except Exception as e:
        print(f"❌ Sniffing Error: {e}")
    
    return None, None

def test_url(url):
    print(f"\n🕵️‍♂️ Auditing URL: {url}")
    
    # 1. Extract Token
    token = None
    source = None
    
    # Check if it's a direct ATS link
    if "greenhouse.io" in url:
        source = "greenhouse"
        match = re.search(r'greenhouse\.io/([^/]+)', url)
        if match: token = match.group(1)
    elif "lever.co" in url:
        source = "lever"
        match = re.search(r'lever\.co/([^/]+)', url)
        if match: token = match.group(1)
    else:
        # It's a Vanity URL -> Sniff it!
        source, token = sniff_token(url)
    
    if not token:
        print("❌ FAILED: Could not find company token (Greenhouse/Lever) on this page.")
        return

    print(f"✅ Token Found: {token} ({source})")

    # 2. Fetch API
    print(f"⏳ Fetching API for {token}...")
    jobs = []
    
    if source == "greenhouse":
        # Try US API
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        resp = requests.get(api_url, headers=get_headers())
        
        # Try EU API if US fails
        if resp.status_code == 404:
            print("   (US API 404, trying EU...)")
            api_url = f"https://job-boards.eu.greenhouse.io/v1/boards/{token}/jobs?content=true"
            resp = requests.get(api_url, headers=get_headers())
            
        if resp.status_code == 200:
            jobs = resp.json().get('jobs', [])
    
    elif source == "lever":
        api_url = f"https://api.lever.co/v0/postings/{token}?mode=json"
        resp = requests.get(api_url, headers=get_headers())
        if resp.status_code == 200:
            jobs = resp.json()

    if not jobs:
        print("❌ API Error: Could not fetch jobs. (Board might be private or empty)")
        return

    print(f"✅ API Success: Found {len(jobs)} active jobs.")

    # 3. Find Specific Job ID
    # Look for ID in URL params (gh_jid=...) or path
    job_id_match = re.search(r'gh_jid=(\d+)', url) # URL param style
    if not job_id_match:
        job_id_match = re.search(r'jobs/(\d+)', url) # Path style
    
    target_job = None
    if job_id_match:
        target_id = job_id_match.group(1)
        print(f"🔎 Looking for Job ID: {target_id}")
        
        for j in jobs:
            # Greenhouse uses 'id', Lever uses 'id' string
            if str(j.get('id')) == str(target_id):
                target_job = j
                break
    else:
        print("⚠️ No Job ID found in URL. Can't screen specific job.")

    if target_job:
        title = target_job.get('title', target_job.get('text'))
        content = target_job.get('content', target_job.get('description'))
        
        print(f"\n📝 Analyzing Job: {title}")
        
        # 4. Run Screener
        screener = MarTechScreener()
        analysis = screener.screen_job(title, content)
        
        print(f"--------------------------------------------------")
        print(f"Match Status:  {'✅ PASS' if analysis['is_match'] else '❌ REJECT'}")
        print(f"Total Score:   {analysis['score']} (Needs 20)")
        print(f"Categories:    {analysis['categories']}")
        print(f"Keywords:      {analysis['stack']}")
        if not analysis['is_match']:
             print(f"Reason:        {analysis.get('reason', 'Score too low')}")
        print(f"--------------------------------------------------")
    else:
        print("❌ Job ID not found in API list. (The job might be closed).")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_job.py <url>")
    else:
        test_url(sys.argv[1])

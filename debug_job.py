import sys
import re
import requests
from jobs.screener import MarTechScreener

# 🕵️‍♂️ STEALTH HEADERS (The "Fake ID")
def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }

def sniff_token(url):
    print(f"🐕 Sniffing for hidden ATS token in {url}...")
    try:
        # Use a Session to handle cookies automatically (helps with 403s)
        session = requests.Session()
        session.headers.update(get_headers())
        
        resp = session.get(url, timeout=10)
        
        if resp.status_code == 403:
            print("❌ Access Denied (403). Trying fallback strategy...")
            # FALLBACK: Try to guess token from domain name
            # e.g. branch.io -> try 'branch' and 'branchmetrics'
            domain_match = re.search(r'https?://(www\.)?([^/.]+)', url)
            if domain_match:
                guess = domain_match.group(2)
                print(f"🤔 Guessing token from domain: '{guess}'")
                return "guess", guess
            return None, None
            
        if resp.status_code != 200:
            print(f"❌ Could not access page. Status: {resp.status_code}")
            return None, None
            
        html = resp.text
        
        # 1. Try Greenhouse Patterns
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
        print("❌ FAILED: Could not find company token.")
        return

    print(f"✅ Token Found: {token} ({source})")

    # 2. Fetch API
    print(f"⏳ Fetching API for {token}...")
    jobs = []
    
    # Helper to fetch with retries for "Guess" mode
    def try_fetch_greenhouse(t):
        url = f"https://boards-api.greenhouse.io/v1/boards/{t}/jobs?content=true"
        r = requests.get(url, headers=get_headers())
        if r.status_code == 200: return r.json().get('jobs', [])
        return []

    if source == "greenhouse":
        jobs = try_fetch_greenhouse(token)
    elif source == "lever":
        api_url = f"https://api.lever.co/v0/postings/{token}?mode=json"
        resp = requests.get(api_url, headers=get_headers())
        if resp.status_code == 200: jobs = resp.json()
    elif source == "guess":
        # Try exact guess first
        print(f"   Trying token: '{token}'...")
        jobs = try_fetch_greenhouse(token)
        if not jobs:
            # Try typical variations (e.g. 'branchmetrics' instead of 'branch')
            alt_token = token + "metrics" # Common pattern
            print(f"   Trying alternate: '{alt_token}'...")
            jobs = try_fetch_greenhouse(alt_token)
            if jobs: token = alt_token # Update verified token

    if not jobs:
        print("❌ API Error: Could not fetch jobs. (Token might be wrong or board is private)")
        return

    print(f"✅ API Success: Found {len(jobs)} active jobs for '{token}'.")

    # 3. Find Specific Job ID
    job_id_match = re.search(r'gh_jid=(\d+)', url)
    if not job_id_match: job_id_match = re.search(r'jobs/(\d+)', url)
    
    target_job = None
    if job_id_match:
        target_id = job_id_match.group(1)
        print(f"🔎 Looking for Job ID: {target_id}")
        
        for j in jobs:
            if str(j.get('id')) == str(target_id):
                target_job = j
                break
    else:
        print("⚠️ No Job ID found in URL.")

    if target_job:
        title = target_job.get('title', target_job.get('text'))
        content = target_job.get('content', target_job.get('description'))
        
        print(f"\n📝 Analyzing Job: {title}")
        
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
        print("❌ Job ID not found in API list.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_job.py <url>")
    else:
        test_url(sys.argv[1])

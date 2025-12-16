import sys
import re
import requests
from jobs.screener import MarTechScreener

# 🚫 IGNORE THESE GENERIC TOKENS
BLACKLIST_TOKENS = {'embed', 'api', 'test', 'demo', 'jobs', 'careers', 'board'}

def get_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
        'Accept-Language': 'en-US,en;q=0.9',
    }

def try_fetch_greenhouse(token):
    if token in BLACKLIST_TOKENS: return []
    for domain in ["boards-api.greenhouse.io", "job-boards.eu.greenhouse.io"]:
        url = f"https://{domain}/v1/boards/{token}/jobs?content=true"
        try:
            r = requests.get(url, headers=get_headers(), timeout=5)
            if r.status_code == 200:
                jobs = r.json().get('jobs', [])
                if jobs: return jobs
        except: pass
    return []

def sniff_token(url):
    print(f"🐕 Sniffing for hidden ATS token in {url}...")
    try:
        session = requests.Session()
        session.headers.update(get_headers())
        resp = session.get(url, timeout=10)
        
        if resp.status_code != 200: return None, None
        html = resp.text
        
        # 1. Try Greenhouse Patterns
        gh_match = re.search(r'greenhouse\.io/([^/"\'?]+)', html)
        if gh_match:
            token = gh_match.group(1)
            if token not in BLACKLIST_TOKENS: return "greenhouse", token
        
        gh_js_match = re.search(r'grnhse\.load_demo\([\'"]([^\'"]+)[\'"]\)', html)
        if gh_js_match:
            token = gh_js_match.group(1)
            if token not in BLACKLIST_TOKENS: return "greenhouse", token

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
    
    # 1. Direct Detection
    if "greenhouse.io" in url and "embed" not in url:
        match = re.search(r'greenhouse\.io/([^/]+)', url)
        if match and match.group(1) not in BLACKLIST_TOKENS:
            source = "greenhouse"
            token = match.group(1)
    elif "lever.co" in url:
        match = re.search(r'lever\.co/([^/]+)', url)
        if match:
            source = "lever"
            token = match.group(1)
    
    # 2. Sniffing (if not found yet)
    if not token:
        source, token = sniff_token(url)
    
    # 3. Fallback: The "Guesser" 🧠
    jobs = []
    
    if token:
        print(f"✅ Token Found: {token} ({source})")
        if source == "greenhouse":
            jobs = try_fetch_greenhouse(token)
            if not jobs:
                print("   ❌ Token found but API failed. Retrying with Guesser...")
                token = None # Force Guesser
        elif source == "lever":
            try:
                r = requests.get(f"https://api.lever.co/v0/postings/{token}?mode=json", headers=get_headers())
                if r.status_code == 200: jobs = r.json()
            except: pass
            
    if not token or not jobs:
        print("🤔 Switching to 'Brute Force Guessing'...")
        domain_match = re.search(r'https?://(www\.)?([^/.]+)', url)
        if domain_match:
            base_guess = domain_match.group(2)
            guesses = [base_guess, base_guess + "metrics", base_guess + "io", base_guess + "inc", base_guess + "data"]
            
            for guess in guesses:
                print(f"   Trying token: '{guess}'...")
                jobs = try_fetch_greenhouse(guess)
                if jobs:
                    print(f"   🎉 SUCCESS! The correct token is: '{guess}'")
                    token = guess
                    source = "greenhouse"
                    break

    if not jobs:
        print("❌ API Error: Could not fetch jobs. (Board is likely private or unguessable)")
        return

    print(f"✅ API Success: Found {len(jobs)} active jobs.")

    # 4. Find Specific Job ID
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
        
        # SIMULATE COMPANY NAME (In real fetcher this comes from the token)
        company_guess = token.capitalize() if token else "Unknown"
        print(f"\n📝 Analyzing Job: {title}")
        print(f"🏢 Company: {company_guess}")
        
        screener = MarTechScreener()
        analysis = screener.screen_job(title, content, company_name=company_guess)
        
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

import os
import requests
import json
from bs4 import BeautifulSoup
from openai import OpenAI
import django

# 1. Setup Django environment
# This allows the script to access your database without running the server
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from jobs.models import Job, Tool

# 2. Setup OpenAI Client
# It will look for the key in your environment variables
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def extract_job_data(url):
    """
    Visits a URL, cleans the HTML, and asks GPT-4o-mini to extract structured JSON data.
    """
    print(f"Fetching: {url}...")
    
    # A. Fetch the HTML
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"❌ Failed to load page: Status {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error fetching URL: {e}")
        return None

    # B. Clean the HTML (Remove noise to save tokens and improve accuracy)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Remove elements that confuse the AI (menus, footers, sidebars, scripts)
    for tag in soup(["script", "style", "nav", "footer", "header", "iframe", "noscript"]):
        tag.extract()
    
    # Get text and compress whitespace
    text = soup.get_text(separator=' ')
    clean_text = " ".join(text.split())[:15000] # Limit to ~3000 tokens

    # C. The AI Prompt
    print("🤖 Asking AI to parse and extract details...")
    prompt = f"""
    You are an expert Job Parser. Extract the following details from the job posting text below into a valid JSON object.
    
    FIELDS TO EXTRACT:
    - title: The official job title.
    - company: The name of the hiring company.
    - company_domain: The official website domain of the company (e.g., 'adobe.com', 'hubspot.com'). Infer this from the text or company name. Do NOT use the job board domain (like 'greenhouse.io').
    - location: The city/state. If 'Remote' is mentioned anywhere, use 'Remote'.
    - description: A concise summary of the role (approx 3-4 sentences). HTML format is allowed (e.g. <p>tags</p>).
    - tools: A list of specific Marketing Technology tools mentioned (e.g., 'Marketo', 'Salesforce', 'Adobe Analytics', 'Tableau', 'Segment').
    
    JOB TEXT:
    {clean_text}
    """

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a JSON extractor. Output only valid JSON."},
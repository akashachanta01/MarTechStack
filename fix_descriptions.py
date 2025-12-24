import os
import django
from bs4 import BeautifulSoup

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from jobs.models import Job

def clean_html(text):
    if not text: return ""
    
    # 1. Parse the HTML
    soup = BeautifulSoup(text, 'html.parser')
    
    # 2. Remove "junk" tags (scripts, styles, metadata)
    for tag in soup(["script", "style", "meta", "link", "head", "title", "iframe"]):
        tag.extract()

    # 3. Unwrap "div" and "span" tags (keep the text, lose the container)
    # This specifically fixes the <div class="content-intro"> issue in your screenshot
    for tag in soup.find_all(True):
        tag.attrs = {} # Remove all attributes (class, style, id)

    # 4. Get clean HTML
    # We allow basic formatting: p, ul, li, h1-h6, b, i, strong, em, br
    valid_tags = ['p', 'ul', 'li', 'ol', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'b', 'i', 'strong', 'em', 'br']
    
    for tag in soup.find_all(True):
        if tag.name not in valid_tags:
            tag.unwrap() # Remove the tag but keep the text inside

    return str(soup).strip()

def run():
    print("🧼 STARTING DESCRIPTION CLEANUP...")
    jobs = Job.objects.all()
    count = 0
    
    for job in jobs:
        original = job.description
        
        # Check if it looks like raw HTML garbage
        if "<div class=" in original or "&lt;div" in original or len(original) < 200:
            clean = clean_html(original)
            
            # If the description is ridiculously short (cut off), mark it
            if len(clean) < 300:
                print(f"   ⚠️ Job {job.id} description is too short/cut off. Consider re-fetching.")
            
            if clean != original:
                job.description = clean
                job.save()
                count += 1
                print(f"   ✨ Fixed Job {job.id}: {job.title}")

    print(f"\n✅ DONE. Cleaned {count} job descriptions.")

if __name__ == '__main__':
    run()

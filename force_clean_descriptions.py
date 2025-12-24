import os
import django
import html
from bs4 import BeautifulSoup
from django.core.cache import cache

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from jobs.models import Job

def aggressive_clean(text):
    if not text: return ""
    
    # STEP 1: Unescape HTML entities (Fixes &lt;div&gt;)
    text = html.unescape(text)
    
    # STEP 2: Parse
    soup = BeautifulSoup(text, 'html.parser')
    
    # STEP 3: Kill Junk Tags completely
    for tag in soup(["script", "style", "meta", "link", "head", "title", "iframe", "input", "form", "button"]):
        tag.extract()

    # STEP 4: Remove ALL attributes (class, id, style, etc.)
    # This turns <div class="content-intro"> into <div>
    for tag in soup.find_all(True):
        tag.attrs = {}

    # STEP 5: Unwrap structural tags (keep text, lose the box)
    # We only want to keep semantic formatting
    allowed_tags = ['p', 'ul', 'li', 'ol', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'b', 'i', 'strong', 'em', 'br', 'u']
    
    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap() # Removes <div> but keeps the text inside!

    # STEP 6: Final Cleanup
    clean_text = str(soup).strip()
    
    # Remove empty tags (like <p></p>)
    clean_text = clean_text.replace("<p></p>", "").replace("<ul></ul>", "")
    
    return clean_text

def run():
    print("☢️  STARTING NUCLEAR DESCRIPTION CLEANUP...")
    
    jobs = Job.objects.all()
    count = 0
    
    for job in jobs:
        original = job.description
        
        # We run this on EVERYTHING that contains a tag-like character
        if "<" in original or "&lt;" in original:
            cleaned = aggressive_clean(original)
            
            if cleaned != original:
                job.description = cleaned
                job.save()
                count += 1
                # print(f"   ✨ Scrubbed Job {job.id}: {job.title[:30]}...")

    print(f"\n✅ DONE. Aggressively cleaned {count} jobs.")
    
    # IMPORTANT: Clear cache so the site updates immediately
    cache.clear()
    print("🧹 Cache cleared.")

if __name__ == '__main__':
    run()

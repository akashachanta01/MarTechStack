import os
import django
import re

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from jobs.models import Job

def normalize_location(loc):
    if not loc: return None
    
    # 1. Basic Clean
    cleaned = loc.strip().replace(" - ", ", ").replace(" | ", ", ").replace("/", ", ")
    
    # 2. Fix specific "Fake Canada" & Long List errors
    bad_canada_fixes = {
        "San Diego, Canada": "San Diego, CA, United States",
        "San Francisco, Canada": "San Francisco, CA, United States",
        "Toronto, Canada": "Toronto, ON, Canada",
        "Vancouver, Canada": "Vancouver, BC, Canada",
    }
    if cleaned in bad_canada_fixes: return bad_canada_fixes[cleaned]

    # 3. Master Dictionary (Enforce City, State, Country)
    city_map = {
        # --- INDIA (Fixing your screenshot issues) ---
        "noida": "Noida, India",
        "noida, uttar pradesh": "Noida, UP, India",
        "uttar pradesh": "Uttar Pradesh, India",
        "gurugram": "Gurugram, India",
        "gurgaon": "Gurugram, India",
        "bengaluru": "Bengaluru, India",
        "bangalore": "Bengaluru, India",
        "mumbai": "Mumbai, India",
        "hyderabad": "Hyderabad, India",
        "delhi": "Delhi, India",
        "new delhi": "Delhi, India",
        "pune": "Pune, India",
        "chennai": "Chennai, India",

        # --- UNITED STATES ---
        "new york": "New York, NY, United States",
        "new york city": "New York, NY, United States",
        "nyc": "New York, NY, United States",
        "ny": "New York, NY, United States",
        "san francisco": "San Francisco, CA, United States",
        "sf": "San Francisco, CA, United States",
        "los angeles": "Los Angeles, CA, United States",
        "chicago": "Chicago, IL, United States",
        "austin": "Austin, TX, United States",
        "boston": "Boston, MA, United States",
        "seattle": "Seattle, WA, United States",
        "denver": "Denver, CO, United States",
        "atlanta": "Atlanta, GA, United States",
        "san diego": "San Diego, CA, United States",
        
        # --- GLOBAL ---
        "london": "London, United Kingdom",
        "london, uk": "London, United Kingdom",
        "toronto": "Toronto, ON, Canada",
        "vancouver": "Vancouver, BC, Canada",
        "singapore": "Singapore",
        "sydney": "Sydney, Australia",
        "melbourne": "Melbourne, Australia",
        "berlin": "Berlin, Germany",
        "munich": "Munich, Germany",
        "paris": "Paris, France",
        "amsterdam": "Amsterdam, Netherlands",
        "dublin": "Dublin, Ireland",
        "zurich": "Zurich, Switzerland",
    }
    
    lower_loc = cleaned.lower()
    if lower_loc in city_map:
        return city_map[lower_loc]

    # 4. Suffix Logic: If it ends with "Uttar Pradesh", add India
    if lower_loc.endswith("uttar pradesh") and "india" not in lower_loc:
        return cleaned + ", India"

    # 5. Smart "CA" Fix (Canada vs California)
    if cleaned.endswith(" CA"):
        if any(c in lower_loc for c in ["toronto", "vancouver", "montreal", "ottawa"]):
            return cleaned.replace(" CA", ", Canada")
        return cleaned.replace(" CA", ", CA, United States")

    # 6. Generic US State Fixer (e.g. "City, TX")
    parts = cleaned.split(',')
    if len(parts) >= 2:
        last_part = parts[-1].strip()
        if len(last_part) == 2 and last_part.isupper() and last_part.isalpha():
            if last_part not in ["US", "UK", "GB", "IN", "DE", "FR", "ES", "IT", "NL"]:
                if "United States" not in cleaned:
                    return f"{cleaned}, United States"

    return cleaned

def run():
    print("🌍 STARTING FINAL LOCATION FIX...")
    jobs = Job.objects.all()
    count = 0
    for job in jobs:
        if not job.location: continue
        original = job.location
        new_loc = normalize_location(original)
        
        if new_loc and new_loc != original:
            print(f"   ✏️ Fixing: '{original}' -> '{new_loc}'")
            job.location = new_loc
            job.save()
            count += 1
            
    print(f"\n✅ DONE. Updated {count} locations.")

if __name__ == '__main__':
    run()

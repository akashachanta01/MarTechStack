import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from jobs.models import Job

def normalize_location(loc):
    if not loc: return None
    
    cleaned = loc.strip().replace(" - ", ", ").replace(" | ", ", ")
    lower_loc = cleaned.lower()
    
    # 1. REMOVE NOISE (Bad data that isn't a location)
    if lower_loc in ["not specified", "on-site", "onsite", "various locations", "multiple locations"]:
        return None

    # 2. FIX REMOTE
    if any(k in lower_loc for k in ["remote", "work from home", "wfh", "anywhere", "home based"]):
        return "Remote"

    # 3. SMART MAPPING (City/State -> Full Country)
    # Catches the specific issues from your screenshot
    mapping = {
        # US Cities & States
        "new york": "New York, NY, United States",
        "nyc": "New York, NY, United States",
        "ny": "New York, NY, United States",
        "san francisco": "San Francisco, CA, United States",
        "sf": "San Francisco, CA, United States",
        "california": "California, United States",
        "ca": "California, United States",
        "illinois": "Illinois, United States",
        "il": "Illinois, United States",
        "chicago": "Chicago, IL, United States",
        "seattle": "Seattle, WA, United States",
        "wa": "Washington, United States",
        "austin": "Austin, TX, United States",
        "texas": "Texas, United States",
        "tx": "Texas, United States",
        "boston": "Boston, MA, United States",
        "burlingame": "Burlingame, CA, United States",
        "atlanta": "Atlanta, GA, United States",
        "denver": "Denver, CO, United States",
        
        # India
        "india": "India",
        "gurugram": "Gurugram, India",
        "gurgaon": "Gurugram, India",
        "bengaluru": "Bengaluru, India",
        "bangalore": "Bengaluru, India",
        "hyderabad": "Hyderabad, India",
        "uttar pradesh": "Uttar Pradesh, India",
        "noida": "Noida, India",
        "mumbai": "Mumbai, India",
        "pune": "Pune, India",
        "delhi": "Delhi, India",
        "new delhi": "Delhi, India",

        # Europe
        "london": "London, United Kingdom",
        "uk": "United Kingdom",
        "united kingdom": "United Kingdom",
        "paris": "Paris, France",
        "berlin": "Berlin, Germany",
        "munich": "Munich, Germany",
        "amsterdam": "Amsterdam, Netherlands",
        "dublin": "Dublin, Ireland",
        "zurich": "Zurich, Switzerland",
        "poland": "Poland",
        "warsaw": "Warsaw, Poland",
        "barcelona": "Barcelona, Spain",
        "madrid": "Madrid, Spain",
        "va de los poblados": "Madrid, Spain", # Specific fix for your screenshot

        # Americas
        "canada": "Canada",
        "toronto": "Toronto, Canada",
        "vancouver": "Vancouver, Canada",
        "mexico": "Mexico",
        "mexico city": "Mexico City, Mexico",
        "latin america": "Latin America", 
        "brazil": "Brazil",
        "sao paulo": "Sao Paulo, Brazil",

        # APAC
        "australia": "Australia",
        "sydney": "Sydney, Australia",
        "melbourne": "Melbourne, Australia",
        "singapore": "Singapore",
    }
    
    # Exact match check
    if lower_loc in mapping:
        return mapping[lower_loc]

    # Suffix check (e.g. "Hyderabad, India" -> catch "India")
    # This standardizes the country name format
    country_corrections = {
        "usa": "United States",
        "us": "United States",
        "united states of america": "United States",
        "uk": "United Kingdom",
        "great britain": "United Kingdom",
        "england": "United Kingdom",
        "deutschland": "Germany",
        "españa": "Spain",
        "brasil": "Brazil",
    }

    # Check if the string ENDS with a known country (e.g. "City, USA")
    parts = cleaned.replace(",", " ").split()
    last_word = parts[-1].lower()
    
    if last_word in country_corrections:
        # Replace the last word with the canonical country
        # "Boston, USA" -> "Boston, United States"
        prefix = " ".join(parts[:-1]).strip().rstrip(",")
        return f"{prefix}, {country_corrections[last_word]}"

    # Fallback: If it looks like "City, State", assume US
    # Regex for ", XX" where XX is 2 uppercase letters
    import re
    if re.search(r', [A-Z]{2}$', cleaned) and "United States" not in cleaned:
         return f"{cleaned}, United States"

    return cleaned

def run():
    print("🌍 STARTING DEEP CLEAN LOCATION FIX...")
    jobs = Job.objects.all()
    count = 0
    for job in jobs:
        if not job.location: continue
        
        original = job.location
        new_loc = normalize_location(original)
        
        # If it returns None (e.g. "Not specified"), we clear it so it doesn't clutter the UI
        if new_loc is None and original: 
             print(f"   🗑️ Clearing invalid location: '{original}'")
             job.location = None
             job.save()
             continue

        if new_loc and new_loc != original:
            print(f"   ✏️ Fixing: '{original}' -> '{new_loc}'")
            job.location = new_loc
            job.save()
            count += 1
            
    print(f"\n✅ DONE. Updated {count} locations.")

if __name__ == '__main__':
    run()

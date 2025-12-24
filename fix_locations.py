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
    
    # 2. Fix specific "Fake Canada" errors (Bad data already in DB)
    # This fixes the specific issue in your screenshot where "San Diego, CA" became "San Diego, Canada"
    bad_canada_fixes = {
        "San Diego, Canada": "San Diego, CA, United States",
        "San Francisco, Canada": "San Francisco, CA, United States",
        "Los Angeles, Canada": "Los Angeles, CA, United States",
        "Mountain View, Canada": "Mountain View, CA, United States",
        "Palo Alto, Canada": "Palo Alto, CA, United States",
        "Santa Monica, Canada": "Santa Monica, CA, United States",
        "Sunnyvale, Canada": "Sunnyvale, CA, United States",
        "San Jose, Canada": "San Jose, CA, United States",
        "Menlo Park, Canada": "Menlo Park, CA, United States",
        "Irvine, Canada": "Irvine, CA, United States",
        "Ontario, Canada": "Ontario, Canada", # This one is actually correct!
        "Toronto, Canada": "Toronto, ON, Canada",
        "Vancouver, Canada": "Vancouver, BC, Canada",
    }
    
    if cleaned in bad_canada_fixes:
        return bad_canada_fixes[cleaned]

    # 3. Master Dictionary (Enforce City, State, Country)
    # This handles the "Missing Country" issue (e.g. "New York City, New York")
    city_map = {
        # --- UNITED STATES ---
        "new york": "New York, NY, United States",
        "new york city": "New York, NY, United States",
        "nyc": "New York, NY, United States",
        "new york, ny": "New York, NY, United States",
        "new york city, new york": "New York, NY, United States",
        "ny": "New York, NY, United States",
        
        "san francisco": "San Francisco, CA, United States",
        "sf": "San Francisco, CA, United States",
        "san francisco, ca": "San Francisco, CA, United States",
        "san francisco bay area": "San Francisco Bay Area, CA, United States",
        
        "los angeles": "Los Angeles, CA, United States",
        "la": "Los Angeles, CA, United States",
        
        "chicago": "Chicago, IL, United States",
        "chicago, il": "Chicago, IL, United States",
        
        "austin": "Austin, TX, United States",
        "austin, tx": "Austin, TX, United States",
        
        "boston": "Boston, MA, United States",
        "boston, ma": "Boston, MA, United States",
        
        "seattle": "Seattle, WA, United States",
        "seattle, wa": "Seattle, WA, United States",
        
        "denver": "Denver, CO, United States",
        "atlanta": "Atlanta, GA, United States",
        "san diego": "San Diego, CA, United States",
        "san diego, ca": "San Diego, CA, United States",
        
        # --- GLOBAL ---
        "london": "London, United Kingdom",
        "london, uk": "London, United Kingdom",
        "toronto": "Toronto, ON, Canada",
        "vancouver": "Vancouver, BC, Canada",
        "bengaluru": "Bengaluru, India",
        "bangalore": "Bengaluru, India",
        "gurugram": "Gurugram, India",
        "mumbai": "Mumbai, India",
        "hyderabad": "Hyderabad, India",
        "singapore": "Singapore",
        "sydney": "Sydney, Australia",
        "melbourne": "Melbourne, Australia",
        "berlin": "Berlin, Germany",
        "munich": "Munich, Germany",
        "paris": "Paris, France",
        "amsterdam": "Amsterdam, Netherlands",
    }
    
    lower_loc = cleaned.lower()
    if lower_loc in city_map:
        return city_map[lower_loc]

    # 4. Smart Suffix Logic (The "CA" Disambiguator)
    # If it ends in "CA", checking if it's likely Canada or California
    if cleaned.endswith(" CA"):
        # List of major Canadian cities to protect
        canadian_cities = ["toronto", "vancouver", "montreal", "ottawa", "calgary", "edmonton", "quebec"]
        first_part = cleaned.split(",")[0].lower().strip()
        
        if any(c in first_part for c in canadian_cities):
            return cleaned.replace(" CA", ", Canada")
        else:
            # Default to California, US for unknown cities (safer bet in tech)
            return cleaned.replace(" CA", ", CA, United States")

    # 5. Generic US State Fixer
    # If it looks like "City, ST" (2 uppercase letters), append United States
    # But SKIP if it's already a country code like UK, IN, DE, FR
    country_codes = ["US", "UK", "GB", "IN", "DE", "FR", "ES", "IT", "NL", "SE", "CH", "AU", "BR", "MX", "SG"]
    
    parts = cleaned.split(',')
    if len(parts) >= 2:
        last_part = parts[-1].strip()
        # If it matches a 2-letter state code (and isn't a known country code)
        if len(last_part) == 2 and last_part.isupper() and last_part.isalpha():
            if last_part not in country_codes:
                return f"{cleaned}, United States"

    # 6. Safety Net: Ensure Country is present
    # If we still haven't fixed it, and it's missing a country, try to guess
    if "United States" not in cleaned and "USA" not in cleaned:
        # Check for full state names
        us_states = ["California", "New York", "Texas", "Massachusetts", "Washington", "Illinois", "Colorado", "Georgia"]
        if any(state.lower() in lower_loc for state in us_states):
             return f"{cleaned}, United States"

    return cleaned

def run():
    print("🌍 STARTING 'CITY, STATE, COUNTRY' STANDARDIZATION...")
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

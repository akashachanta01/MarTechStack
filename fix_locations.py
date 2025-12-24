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
    
    # 2. STATE SHORTENER (California -> CA)
    # This must run BEFORE the dictionary lookup to standardize inputs
    state_map = {
        "California": "CA", "New York": "NY", "Texas": "TX", "Washington": "WA",
        "Illinois": "IL", "Massachusetts": "MA", "Georgia": "GA", "Colorado": "CO",
        "Florida": "FL", "Virginia": "VA", "Pennsylvania": "PA", "Ohio": "OH",
        "North Carolina": "NC", "Michigan": "MI", "Arizona": "AZ", "New Jersey": "NJ",
        "Uttar Pradesh": "UP" # Common for Noida
    }
    
    # Replace ", California" with ", CA" safely
    for state, code in state_map.items():
        if f", {state}" in cleaned:
            cleaned = cleaned.replace(f", {state}", f", {code}")
        elif cleaned.endswith(f" {state}"):
            cleaned = cleaned.replace(f" {state}", f" {code}")

    # 3. SPECIFIC FIXES (The "Hyderabad" & "Noida" Fix)
    # If the location matches exactly (lowercase check), swap it for the perfect format.
    city_map = {
        # --- INDIA ---
        "hyderabad": "Hyderabad, India",
        "hyderabad, india": "Hyderabad, India", # Ensure consistency
        "noida": "Noida, UP, India",
        "noida, up": "Noida, UP, India",
        "gurugram": "Gurugram, India",
        "gurgaon": "Gurugram, India",
        "bengaluru": "Bengaluru, India",
        "bangalore": "Bengaluru, India",
        "mumbai": "Mumbai, India",
        "pune": "Pune, India",
        "chennai": "Chennai, India",
        "delhi": "Delhi, India",
        "new delhi": "Delhi, India",

        # --- USA (Shortened States) ---
        "new york": "New York, NY, United States",
        "new york city": "New York, NY, United States",
        "nyc": "New York, NY, United States",
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
        
        # --- CANADA (Fixing the "CA" confusion) ---
        "toronto": "Toronto, ON, Canada",
        "toronto, canada": "Toronto, ON, Canada",
        "vancouver": "Vancouver, BC, Canada",
        "vancouver, canada": "Vancouver, BC, Canada",
        
        # --- GLOBAL ---
        "london": "London, United Kingdom",
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

    # 4. HANDLE "CA" AMBIGUITY
    # If it ends in ", CA", it's usually California, unless it's a known Canadian city.
    if cleaned.endswith(", CA") or cleaned.endswith(" CA"):
        canadian_cities = ["toronto", "vancouver", "montreal", "ottawa", "calgary"]
        if any(c in lower_loc for c in canadian_cities):
            cleaned = cleaned.replace(" CA", ", Canada").replace(", CA", ", Canada")
        else:
            # If it's already "San Diego, CA", just append country
            if "United States" not in cleaned:
                cleaned = f"{cleaned}, United States"

    # 5. GENERIC US APPENDER
    # If it looks like "City, ST" (2 uppercase letters) and isn't a country code
    parts = cleaned.split(',')
    if len(parts) >= 2:
        last_part = parts[-1].strip()
        # If it is exactly 2 uppercase letters (state code)
        if len(last_part) == 2 and last_part.isupper() and last_part.isalpha():
            exclude_codes = ["US", "UK", "GB", "IN", "DE", "FR", "ES", "IT", "NL", "AU", "BR", "MX", "SG", "CA"]
            if last_part not in exclude_codes:
                if "United States" not in cleaned:
                    return f"{cleaned}, United States"

    return cleaned

def run():
    print("🌍 STARTING LOCATION STANDARDIZATION...")
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

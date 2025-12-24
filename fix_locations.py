import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from jobs.models import Job

def normalize_location(loc):
    if not loc: return None
    
    cleaned = loc.strip()
    
    # 1. Fix "Remote" variations
    if any(k in cleaned.lower() for k in ["remote", "work from home", "wfh", "anywhere"]):
        return "Remote"

    # 2. Dictionary of Specific Major Cities (City -> Full Location)
    # Use this for cities that often appear WITHOUT a country or state
    city_map = {
        "New York": "New York, NY, United States",
        "NYC": "New York, NY, United States",
        "San Francisco": "San Francisco, CA, United States",
        "SF": "San Francisco, CA, United States",
        "Los Angeles": "Los Angeles, CA, United States",
        "London": "London, United Kingdom",
        "Berlin": "Berlin, Germany",
        "Munich": "Munich, Germany",
        "Paris": "Paris, France",
        "Amsterdam": "Amsterdam, Netherlands",
        "Toronto": "Toronto, Canada",
        "Vancouver": "Vancouver, Canada",
        "Sydney": "Sydney, Australia",
        "Melbourne": "Melbourne, Australia",
        "Bengaluru": "Bengaluru, India",
        "Bangalore": "Bengaluru, India",
        "Singapore": "Singapore",
        "Dublin": "Dublin, Ireland",
        "Zurich": "Zurich, Switzerland",
    }
    
    if cleaned in city_map:
        return city_map[cleaned]

    # 3. ISO Country Codes (Catch "City, CODE" formats)
    # This automatically fixes "Paris, FR" -> "Paris, France"
    country_codes = {
        "US": "United States", "USA": "United States",
        "UK": "United Kingdom", "GB": "United Kingdom",
        "CA": "Canada",
        "AU": "Australia",
        "DE": "Germany",
        "FR": "France",
        "NL": "Netherlands",
        "IN": "India",
        "SG": "Singapore",
        "IE": "Ireland",
        "CH": "Switzerland",
        "ES": "Spain",
        "IT": "Italy",
        "SE": "Sweden",
        "BR": "Brazil",
        "MX": "Mexico"
    }

    # Check if the string ends with a known code (e.g. "Berlin, DE")
    parts = cleaned.replace(',', ' ').split()
    if len(parts) > 1:
        last_part = parts[-1].upper().strip()
        if last_part in country_codes:
            full_country = country_codes[last_part]
            # Avoid double naming like "France, France"
            if full_country.lower() not in cleaned.lower():
                return cleaned[:-len(last_part)].strip().strip(',') + ", " + full_country

    # 4. Catch-all for US States (e.g., "Atlanta, GA")
    if "," in cleaned and "United States" not in cleaned:
        state_part = cleaned.split(',')[-1].strip()
        if len(state_part) == 2 and state_part.isupper() and state_part.isalpha():
            if state_part not in country_codes: 
                return f"{cleaned}, United States"

    return cleaned

def run():
    print("🌍 STARTING SMART LOCATION NORMALIZATION...")
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

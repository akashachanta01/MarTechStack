"""Country from a free-text job location ("CAN, ON, Mississauga" -> "CA").

Used to fill Job.country and to build the country-only location dropdown.
Returns "" when the text doesn't name one country ("Multiple locations",
"Latin America"), never a guess.
"""
import re

COUNTRY_NAMES = {
    "US": "United States", "GB": "United Kingdom", "CA": "Canada", "IN": "India", "AU": "Australia",
    "DE": "Germany", "FR": "France", "NL": "Netherlands", "IE": "Ireland", "ES": "Spain", "PT": "Portugal",
    "BR": "Brazil", "MX": "Mexico", "SG": "Singapore", "DK": "Denmark", "NO": "Norway", "SE": "Sweden",
    "FI": "Finland", "PL": "Poland", "SK": "Slovakia", "HU": "Hungary", "LV": "Latvia", "LT": "Lithuania",
    "EE": "Estonia", "IL": "Israel", "TH": "Thailand", "PH": "Philippines", "TW": "Taiwan", "CO": "Colombia",
    "CR": "Costa Rica", "AR": "Argentina", "CL": "Chile", "PE": "Peru", "JP": "Japan", "CN": "China",
    "HK": "Hong Kong", "AE": "United Arab Emirates", "SA": "Saudi Arabia", "ZA": "South Africa",
    "NZ": "New Zealand", "CH": "Switzerland", "AT": "Austria", "BE": "Belgium", "IT": "Italy", "RO": "Romania",
    "CZ": "Czech Republic", "GR": "Greece", "TR": "Turkey", "EG": "Egypt", "NG": "Nigeria", "KE": "Kenya",
    "MY": "Malaysia", "ID": "Indonesia", "VN": "Vietnam", "KR": "South Korea", "LU": "Luxembourg",
    "UA": "Ukraine", "RS": "Serbia", "BG": "Bulgaria", "HR": "Croatia",
}

_ALIASES = {
    "usa": "US", "u.s.": "US", "u.s.a.": "US", "united states of america": "US", "us": "US",
    "uk": "GB", "u.k.": "GB", "england": "GB", "scotland": "GB", "wales": "GB", "great britain": "GB",
    "can": "CA", "mex": "MX", "méxico": "MX", "deutschland": "DE", "españa": "ES", "brasil": "BR",
    "uae": "AE", "dubai": "AE", "abu dhabi": "AE", "holland": "NL", "the netherlands": "NL",
    "czechia": "CZ", "korea": "KR", "danmark": "DK", "sverige": "SE", "norge": "NO",
}

_US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}
_US_ABBR = set(_US_STATES.values())

_CITIES = {
    "US": ["san francisco", "los angeles", "san jose", "santa clara", "seattle", "chicago", "boston", "austin",
           "atlanta", "denver", "dallas", "houston", "miami", "orlando", "omaha", "phoenix", "new york city",
           "nyc", "palo alto", "mountain view", "sunnyvale", "san diego", "philadelphia", "minneapolis",
           "detroit", "charlotte", "raleigh", "nashville", "portland", "salt lake city", "pittsburgh",
           "irvine", "jacksonville", "washington dc", "washington, d.c."],
    "GB": ["london", "manchester", "birmingham", "edinburgh", "glasgow", "leeds", "bristol", "welwyn",
           "cambridge, uk", "reading"],
    "IN": ["bengaluru", "bangalore", "hyderabad", "mumbai", "pune", "chennai", "gurgaon", "gurugram", "noida",
           "delhi", "new delhi", "kolkata", "ahmedabad", "uttar pradesh", "karnataka", "maharashtra",
           "telangana", "tamil nadu", "haryana"],
    "CA": ["toronto", "vancouver", "montreal", "montréal", "ottawa", "calgary", "mississauga", "waterloo",
           "ontario", "quebec", "québec", "british columbia", "alberta"],
    "AU": ["sydney", "melbourne", "brisbane", "perth", "adelaide"],
    "DE": ["berlin", "munich", "münchen", "hamburg", "frankfurt", "cologne", "köln", "düsseldorf", "stuttgart"],
    "FR": ["paris", "lyon", "marseille", "toulouse", "lille"],
    "NL": ["amsterdam", "rotterdam", "utrecht", "eindhoven", "the hague"],
    "IE": ["dublin", "cork", "galway", "limerick"],
    "ES": ["madrid", "barcelona", "valencia", "seville", "gijon", "gijón", "malaga", "málaga", "bilbao"],
    "PT": ["lisbon", "lisboa", "porto"],
    "BR": ["são paulo", "sao paulo", "rio de janeiro"],
    "MX": ["mexico city", "ciudad de méxico", "guadalajara", "monterrey"],
    "DK": ["copenhagen", "københavn", "aarhus"],
    "NO": ["oslo"], "SE": ["stockholm", "gothenburg"], "FI": ["helsinki"], "PL": ["warsaw", "krakow", "kraków"],
    "HU": ["budapest"], "LV": ["riga"], "SK": ["bratislava"], "CZ": ["prague"], "AT": ["vienna"],
    "CH": ["zurich", "zürich", "geneva"], "BE": ["brussels"], "IT": ["milan", "rome"], "IL": ["tel aviv", "herzliya"],
    "SG": ["singapore"], "JP": ["tokyo"], "HK": ["hong kong"], "AE": ["dubai"], "TH": ["bangkok"],
    "PH": ["manila"], "TW": ["taipei"], "AR": ["buenos aires"], "CO": ["bogota", "bogotá", "medellin"],
}
_CITY_TO_CODE = {c: code for code, cities in _CITIES.items() for c in cities}
_NAME_TO_CODE = {n.lower(): c for c, n in COUNTRY_NAMES.items()}
_NAME_TO_CODE.update(_ALIASES)
_WORD = lambda s: re.compile(r"(?<![a-z])" + re.escape(s) + r"(?![a-z])")
_NAME_RX = [(_WORD(n), c) for n, c in sorted(_NAME_TO_CODE.items(), key=lambda x: -len(x[0])) if len(n) > 3]
_CITY_RX = [(_WORD(n), c) for n, c in sorted(_CITY_TO_CODE.items(), key=lambda x: -len(x[0]))]
_STATE_RX = [_WORD(s) for s in sorted(_US_STATES, key=len, reverse=True)]


def country_code(location):
    """ISO-2 country for a location string, or "" if it doesn't name exactly one.
    Multi-location strings ("A; B") count only when every part is the same country."""
    if not location:
        return ""
    if re.search(r"\+\s*\d+\s+more", location.lower()):
        return ""
    if ";" in location:
        codes = {_one(p) for p in location.split(";") if p.strip()}
        return codes.pop() if len(codes) == 1 and "" not in codes else ""
    return _one(location)


def _one(location):
    raw = location.strip()
    low = raw.lower()
    if low in ("multiple locations", "remote", ""):
        return ""
    # ATS feeds end with a lowercase ISO code: "Paris, IDF, fr", "Bengaluru, in".
    # (US states are written in capitals, "Austin, TX", so "in"/"ca" here are countries.)
    last = raw.rsplit(",", 1)[-1].strip() if "," in raw else ""
    if len(last) == 2 and last.islower() and last.upper() in COUNTRY_NAMES:
        return "GB" if last == "uk" else last.upper()
    if last == "uk":
        return "GB"
    found = set()
    # Leading codes: "US-CT-REMOTE", "US, CA, Santa Clara", "CAN, ON, ...", "MEX Work-at-Home".
    head = re.split(r"[\s,\-]+", low, maxsplit=1)[0]
    if head in ("us", "usa", "can", "mex", "uk", "gb"):
        return {"us": "US", "usa": "US", "can": "CA", "mex": "MX", "uk": "GB", "gb": "GB"}[head]
    # A US state name wins over a same-named country ("New Mexico", "Georgia").
    if any(rx.search(low) for rx in _STATE_RX):
        return "US"
    for rx, code in _NAME_RX:
        if rx.search(low):
            found.add(code)
    # Short aliases only as a whole part ("Remote, US", "Remote - USA").
    for part in (p.strip() for p in re.split(r"[,|/]|\s-\s", low)):
        if part in _ALIASES and len(part) <= 5:
            found.add(_ALIASES[part])
    # "Remote UK only", "Field-UK", "Remote-USA": stand-alone UK / USA tokens.
    if not found:
        if re.search(r"(?<![a-z])usa(?![a-z])", low):
            found.add("US")
        if re.search(r"(?<![a-z])uk(?![a-z])", low):
            found.add("GB")
    if not found:
        for rx, code in _CITY_RX:
            if rx.search(low):
                found.add(code)
    if not found:
        if re.search(r",\s*([A-Z]{2})(?:\s+\d{5})?\s*(?:,|$)", raw) and \
                re.search(r",\s*([A-Z]{2})(?:\s+\d{5})?\s*(?:,|$)", raw).group(1) in _US_ABBR:
            found.add("US")
    return found.pop() if len(found) == 1 else ""


def country_name(code):
    return COUNTRY_NAMES.get((code or "").upper(), "")


def code_for_name(name):
    return _NAME_TO_CODE.get((name or "").strip().lower(), "")

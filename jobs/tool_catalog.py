"""
Canonical MarTech tool catalog + alias normalization.

Goal: the screener emits stack names like "SFMC", "GA4", "Account Engagement";
this maps them to ONE canonical Tool name so tags are consistent, and lets us
auto-create valid-but-missing tools instead of silently dropping them — while
NOT creating junk (only names we recognize get through).

resolve_tool_name(raw) -> canonical display name, or None if unrecognized.
"""

# Canonical display name -> list of aliases (all matched case-insensitively).
# The canonical name itself is always recognized too.
_CATALOG = {
    "Salesforce": ["sfdc", "salesforce crm", "sales cloud"],
    "Salesforce Marketing Cloud": ["sfmc", "marketing cloud", "exacttarget", "salesforce marketing cloud"],
    "Pardot": ["account engagement", "marketing cloud account engagement", "salesforce pardot"],
    "HubSpot": ["hubspot crm", "hub spot"],
    "Marketo": ["marketo engage", "adobe marketo"],
    "Adobe Experience Platform": ["aep"],
    "Adobe Experience Manager": ["aem"],
    "Adobe Journey Optimizer": ["ajo"],
    "Adobe Campaign": [],
    "Adobe Analytics": ["omniture"],
    "Adobe Target": [],
    "Braze": [],
    "Iterable": [],
    "Klaviyo": [],
    "Customer.io": ["customerio", "customer io"],
    "Mailchimp": ["mail chimp"],
    "ActiveCampaign": ["active campaign"],
    "Oracle Eloqua": ["eloqua"],
    "Segment": ["twilio segment"],
    "Tealium": [],
    "mParticle": ["m particle"],
    "RudderStack": ["rudder stack"],
    "Snowflake": [],
    "dbt": ["data build tool"],
    "Fivetran": [],
    "Google Analytics": ["ga4", "google analytics 4", "ga 4", "universal analytics"],
    "Google Tag Manager": ["gtm"],
    "Google BigQuery": ["bigquery", "big query"],
    "Looker": ["looker studio"],
    "Tableau": [],
    "Power BI": ["powerbi", "microsoft power bi"],
    "Amplitude": [],
    "Mixpanel": ["mix panel"],
    "Heap": ["heap analytics"],
    "Optimizely": [],
    "6sense": ["six sense"],
    "Demandbase": ["demand base"],
    "Drift": [],
    "Intercom": [],
    "Outreach": ["outreach.io"],
    "Salesloft": ["sales loft"],
    "ZoomInfo": ["zoom info"],
    "Census": [],
    "Hightouch": ["high touch"],
    "Zapier": [],
    "Workato": [],
    "Tray.io": ["tray", "tray io"],
    "MuleSoft": ["mule soft"],
    "Contentful": [],
    "Sprinklr": [],
    "Iterable": [],
    "Sendgrid": ["send grid", "twilio sendgrid"],
    "Braze": [],
    "Apollo": ["apollo.io"],
    "Marketing Cloud Personalization": ["interaction studio"],
    "Hubspot Operations Hub": ["operations hub"],
}

# Build a fast lookup: normalized alias/name -> canonical display name.
_LOOKUP = {}
for _canon, _aliases in _CATALOG.items():
    _LOOKUP[_canon.lower()] = _canon
    for _a in _aliases:
        _LOOKUP[_a.lower()] = _canon


def resolve_tool_name(raw):
    """Return the canonical Tool display name for a raw stack string, or None."""
    if not raw:
        return None
    key = " ".join(str(raw).strip().lower().split())
    if not key:
        return None
    # exact alias/canonical match
    if key in _LOOKUP:
        return _LOOKUP[key]
    # tolerate trailing noise like "salesforce (sfmc)" / "hubspot crm platform"
    for alias, canon in _LOOKUP.items():
        if len(alias) >= 4 and (key == alias or key.startswith(alias + " ") or key.endswith(" " + alias)):
            return canon
    return None


def all_canonical_names():
    return sorted(_CATALOG.keys())

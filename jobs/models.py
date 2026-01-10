from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth.models import User
import html
from bs4 import BeautifulSoup
import re
from datetime import timedelta

# --- HELPER 1: LOCATION STANDARDIZER ---
def normalize_location(loc):
    if not loc: return "Remote"
    cleaned = loc.strip().replace(" - ", ", ").replace(" | ", ", ").replace("/", ", ")
    state_map = {
        "California": "CA", "New York": "NY", "Texas": "TX", "Washington": "WA",
        "Illinois": "IL", "Massachusetts": "MA", "Georgia": "GA", "Colorado": "CO",
        "Florida": "FL", "Virginia": "VA", "Pennsylvania": "PA", "Ohio": "OH",
        "North Carolina": "NC", "Michigan": "MI", "Arizona": "AZ", "New Jersey": "NJ"
    }
    for state, code in state_map.items():
        if f", {state}" in cleaned:
            cleaned = cleaned.replace(f", {state}", f", {code}")
    lower_loc = cleaned.lower()
    city_map = {
        "new york": "New York, NY, United States",
        "nyc": "New York, NY, United States",
        "san francisco": "San Francisco, CA, United States",
        "sf": "San Francisco, CA, United States",
        "los angeles": "Los Angeles, CA, United States",
        "london": "London, United Kingdom",
        "bengaluru": "Bengaluru, India",
        "bangalore": "Bengaluru, India",
        "toronto": "Toronto, ON, Canada",
        "vancouver": "Vancouver, BC, Canada",
        "sydney": "Sydney, Australia",
        "remote": "Remote",
    }
    if lower_loc in city_map: return city_map[lower_loc]
    if "United States" not in cleaned and "Remote" not in cleaned:
        if re.search(r', [A-Z]{2}$', cleaned): cleaned += ", United States"
    return cleaned

# --- HELPER 2: DESCRIPTION CLEANER ---
def clean_html_description(text):
    if not text: return ""
    text = html.unescape(text)
    soup = BeautifulSoup(text, 'html.parser')
    for tag in soup(["script", "style", "meta", "link", "head", "title", "iframe", "input", "form", "button", "img", "svg"]):
        tag.extract()
    for tag in soup.find_all(True):
        tag.attrs = {} 
    allowed_tags = ['p', 'ul', 'li', 'ol', 'h3', 'h4', 'strong', 'b', 'em', 'i', 'br']
    for tag in soup.find_all(True):
        if tag.name not in allowed_tags:
            tag.unwrap()
    clean_text = str(soup).strip()
    return re.sub(r'\n\s*\n', '\n\n', clean_text)

# --- MODELS ---

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    def __str__(self): return self.name
    class Meta: verbose_name_plural = "Categories"

class Tool(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="tools")
    
    # SEO Fields
    logo_url = models.URLField(max_length=500, blank=True, null=True, help_text="Official logo of the tool")
    description = models.TextField(blank=True, default="", help_text="SEO Content: Appears at top of page.")
    seo_title = models.CharField(max_length=200, blank=True, default="", help_text="Browser Title (e.g. 'HubSpot Jobs & Careers')")
    seo_h1 = models.CharField(max_length=200, blank=True, default="", help_text="Page Heading (e.g. 'Top HubSpot Jobs')")

    def __str__(self): return self.name
    @property
    def color_class(self):
        colors = ['bg-emerald-100 text-emerald-700 border-emerald-200','bg-amber-100 text-amber-800 border-amber-200','bg-rose-100 text-rose-700 border-rose-200','bg-sky-100 text-sky-700 border-sky-200','bg-violet-100 text-violet-700 border-violet-200','bg-indigo-100 text-indigo-700 border-indigo-200']
        return colors[sum(ord(c) for c in self.name) % len(colors)]

class Job(models.Model):
    ROLE_TYPE_CHOICES = [('full_time', 'Full-time'), ('contract', 'Contract'), ('part_time', 'Part-time'), ('temporary', 'Temporary'), ('internship', 'Internship')]
    STATUS_CHOICES = [('pending', 'Pending Review'), ('approved', 'Approved'), ('rejected', 'Rejected')]
    WORK_ARRANGEMENT_CHOICES = [('remote', 'Remote'), ('hybrid', 'Hybrid'), ('onsite', 'On-site')]

    title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    company_logo = models.URLField(max_length=500, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField()
    apply_url = models.URLField(max_length=500)
    slug = models.SlugField(max_length=250, null=True, blank=True)
    
    role_type = models.CharField(max_length=20, choices=ROLE_TYPE_CHOICES, default='full_time')
    salary_range = models.CharField(max_length=100, blank=True, null=True)
    work_arrangement = models.CharField(max_length=10, choices=WORK_ARRANGEMENT_CHOICES, default='onsite')
    tools = models.ManyToManyField(Tool, related_name="jobs", blank=True)
    
    screening_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_active = models.BooleanField(default=False)
    screened_at = models.DateTimeField(blank=True, null=True)
    
    screening_score = models.FloatField(blank=True, null=True)
    screening_reason = models.TextField(blank=True, default="")
    screening_details = models.JSONField(blank=True, default=dict)

    is_featured = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    plan_name = models.CharField(max_length=50, blank=True, null=True)
    tags = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self): return f"{self.title} at {self.company}"

    def get_salary_min_max(self):
        if not self.salary_range: return None, None
        try:
            txt = self.salary_range.lower().replace(',', '').replace('.', '')
            nums = re.findall(r'\d+', txt)
            if not nums: return None, None
            vals = []
            for n in nums:
                val = int(n)
                if val < 1000: val *= 1000
                vals.append(val)
            vals.sort()
            if len(vals) >= 2: return vals[0], vals[-1]
            if len(vals) == 1: return vals[0], vals[0]
        except: pass
        return None, None

    def get_schema_valid_through(self):
        return (self.created_at + timedelta(days=90)).strftime('%Y-%m-%d')

    def save(self, *args, **kwargs):
        if self.location: self.location = normalize_location(self.location)
        if self.description: self.description = clean_html_description(self.description)
        if not self.slug: self.slug = slugify(f"{self.title} at {self.company}")
        if self.screening_status == 'approved': 
            self.is_active = True
        else:
            self.is_active = False
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        indexes = [models.Index(fields=['is_active', 'screening_status']), models.Index(fields=['created_at'])]

class BlogPost(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, help_text="URL friendly version of title")
    excerpt = models.TextField(help_text="Short summary for the blog card (2-3 sentences).")
    content = models.TextField(help_text="Full HTML content of the article.")
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    author = models.CharField(max_length=100, default="MarTechJobs Team")
    category = models.CharField(max_length=50, default="Career Advice")
    read_time = models.CharField(max_length=20, default="5 min read")
    published_at = models.DateField(default=timezone.now)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self): return self.title
    class Meta: ordering = ['-published_at']

class Subscriber(models.Model):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.email

class BlockRule(models.Model):
    RULE_TYPES = [("domain", "Domain"), ("company", "Company"), ("keyword", "Keyword"), ("regex", "Regex")]
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES, db_index=True)
    value = models.CharField(max_length=500)
    enabled = models.BooleanField(default=True)
    notes = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.rule_type}: {self.value}"

class UserSubmission(Job):
    class Meta: proxy = True; verbose_name = "User Submission"

class ActiveJob(Job):
    class Meta: proxy = True; verbose_name = "Active Job"

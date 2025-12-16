from django.db import models
from django.utils import timezone

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Categories"

class Tool(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="tools")

    def __str__(self):
        return self.name

    @property
    def color_class(self):
        """
        Returns a consistent Tailwind CSS class string based on the tool name.
        This ensures 'Marketo' is always the same color, on every card.
        """
        # "Saturated Pastel" Palette (200 bg, 900 text, 300 border)
        colors = [
            'bg-emerald-200 text-emerald-900 border-emerald-300',
            'bg-amber-200 text-amber-900 border-amber-300',
            'bg-rose-200 text-rose-900 border-rose-300',
            'bg-sky-200 text-sky-900 border-sky-300',
            'bg-violet-200 text-violet-900 border-violet-300',
            'bg-teal-200 text-teal-900 border-teal-300',
            'bg-indigo-200 text-indigo-900 border-indigo-300',
            'bg-fuchsia-200 text-fuchsia-900 border-fuchsia-300',
            'bg-orange-200 text-orange-900 border-orange-300',
            'bg-cyan-200 text-cyan-900 border-cyan-300',
            'bg-lime-200 text-lime-900 border-lime-300',
            'bg-pink-200 text-pink-900 border-pink-300',
        ]
        # Sum the ASCII values of the characters to get a consistent number
        char_sum = sum(ord(c) for c in self.name)
        # Use modulo to pick a color from the list
        return colors[char_sum % len(colors)]

class Job(models.Model):
    ROLE_TYPE_CHOICES = [
        ('full_time', 'Full-time'),
        ('part_time', 'Part-time'),
        ('contract', 'Contract'),
        ('temporary', 'Temporary'),
        ('internship', 'Internship'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    company_logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    location = models.CharField(max_length=200, blank=True, null=True)
    
    description = models.TextField()
    apply_url = models.URLField(max_length=500)
    
    role_type = models.CharField(max_length=20, choices=ROLE_TYPE_CHOICES, default='full_time')
    salary_range = models.CharField(max_length=100, blank=True, null=True)
    remote = models.BooleanField(default=False)
    
    tools = models.ManyToManyField(Tool, related_name="jobs", blank=True)
    
    # Screening fields
    screening_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_active = models.BooleanField(default=False)
    screened_at = models.DateTimeField(blank=True, null=True)
    
    # AI/Scraper Fields
    screening_score = models.FloatField(blank=True, null=True)
    screening_reason = models.TextField(blank=True, default="")
    screening_details = models.JSONField(blank=True, default=dict)
    
    # Simple tagging
    tags = models.CharField(max_length=200, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} at {self.company}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'screening_status']),
            models.Index(fields=['created_at']),
        ]

class Subscriber(models.Model):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email

class BlockRule(models.Model):
    RULE_TYPES = [
        ("domain", "Domain"),
        ("company", "Company"),
        ("keyword", "Keyword"),
        ("regex", "Regex (title/description)"),
    ]
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES, db_index=True)
    value = models.CharField(max_length=500, help_text="Value for the rule (domain/company/keyword/regex).")
    enabled = models.BooleanField(default=True)
    notes = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.rule_type}: {self.value}"

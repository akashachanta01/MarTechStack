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
        UPDATED: Using 'Level 100' backgrounds for a softer, professional look.
        """
        colors = [
            'bg-emerald-100 text-emerald-700 border-emerald-200',
            'bg-amber-100 text-amber-800 border-amber-200',
            'bg-rose-100 text-rose-700 border-rose-200',
            'bg-sky-100 text-sky-700 border-sky-200',
            'bg-violet-100 text-violet-700 border-violet-200',
            'bg-teal-100 text-teal-700 border-teal-200',
            'bg-indigo-100 text-indigo-700 border-indigo-200',
            'bg-fuchsia-100 text-fuchsia-700 border-fuchsia-200',
            'bg-orange-100 text-orange-800 border-orange-200',
            'bg-cyan-100 text-cyan-700 border-cyan-200',
            'bg-lime-100 text-lime-700 border-lime-200',
            'bg-pink-100 text-pink-700 border-pink-200',
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
    
    # CHANGED: ImageField -> URLField to allow automated external links
    company_logo = models.URLField(max_length=500, blank=True, null=True)
    
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

# --- PROXY MODEL FOR ADMIN ---
class UserSubmission(Job):
    class Meta:
        proxy = True
        verbose_name = "User Submission"
        verbose_name_plural = "User Submissions"

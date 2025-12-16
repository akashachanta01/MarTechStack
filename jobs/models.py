from django.db import models
from django.utils import timezone


class ToolCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Tool(models.Model):
    name = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey(ToolCategory, on_delete=models.CASCADE, related_name="tools")

    def __str__(self):
        return self.name


class Job(models.Model):
    ROLE_TYPE_CHOICES = (
        ("full_time", "Full-time"),
        ("part_time", "Part-time"),
        ("contract", "Contract"),
        ("temporary", "Temporary"),
        ("internship", "Internship"),
    )

    SCREENING_STATUS_CHOICES = (
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True, default="")
    remote = models.BooleanField(default=False)

    description = models.TextField(blank=True, default="")
    apply_url = models.URLField(max_length=1000)

    role_type = models.CharField(max_length=50, choices=ROLE_TYPE_CHOICES, default="full_time")

    tools = models.ManyToManyField(Tool, blank=True, related_name="jobs")
    tags = models.JSONField(default=list, blank=True)

    salary_range = models.CharField(max_length=255, blank=True, default="")

    # visibility in public listings
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # --- Zero-Noise: screening fields ---
    screening_status = models.CharField(
        max_length=20, choices=SCREENING_STATUS_CHOICES, default="pending", db_index=True
    )
    screening_score = models.FloatField(null=True, blank=True)
    screening_reason = models.TextField(blank=True, default="")
    screening_details = models.JSONField(default=dict, blank=True)
    screened_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} @ {self.company}"


class Subscriber(models.Model):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class BlockRule(models.Model):
    RULE_TYPE_CHOICES = (
        ("domain", "Domain"),
        ("company", "Company"),
        ("keyword", "Keyword"),
        ("regex", "Regex (title/description)"),
    )

    rule_type = models.CharField(max_length=20, choices=RULE_TYPE_CHOICES, db_index=True)
    value = models.CharField(max_length=500, help_text="Value for the rule (domain/company/keyword/regex).")
    enabled = models.BooleanField(default=True)
    notes = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        status = "ON" if self.enabled else "OFF"
        return f"[{status}] {self.rule_type}: {self.value}"

from django.db import models

class ToolPage(models.Model):
    title = models.CharField(max_length=200, help_text="e.g. 'Marketing Operations Job Description Generator'")
    slug = models.SlugField(unique=True, help_text="e.g. 'marketing-operations-job-description-generator'")
    seo_title = models.CharField(max_length=255, blank=True)
    seo_description = models.TextField(blank=True)
    
    # Configuration for the generator
    role_name = models.CharField(max_length=100, help_text="Default role name for this page")
    default_responsibilities = models.TextField(help_text="Bullet points, one per line")
    default_skills = models.TextField(help_text="Bullet points, one per line")

    def __str__(self):
        return self.title

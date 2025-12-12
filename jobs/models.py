from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Categories"

class Tool(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='tools')
    
    def __str__(self):
        return f"{self.name} ({self.category.name})"

class Job(models.Model):
    title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    company_logo = models.URLField(blank=True, null=True)
    location = models.CharField(max_length=100, default="Remote")
    salary_range = models.CharField(max_length=100, blank=True, null=True)
    tags = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField()
    apply_url = models.URLField()
    tools = models.ManyToManyField(Tool, related_name='jobs')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} at {self.company}"
    
    def get_tag_list(self):
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',')]
        return []

# --- NEW SUBSCRIBER MODEL ---
#class Subscriber(models.Model):
   # email = models.EmailField(unique=True)
   # created_at = models.DateTimeField(auto_now_add=True)

   # def __str__(self):
      #  return self.email

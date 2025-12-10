import os
import django

# 1. Setup Django manually
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# 2. Import your models
from jobs.models import Category, Tool
from django.utils.text import slugify

def run():
    print("--- STARTING DATABASE INJECTION ---")
    
    # Check what exists before
    print(f"Categories before: {Category.objects.count()}")
    
    taxonomy = {
        "Marketing Automation": ["Marketo", "HubSpot", "Braze"],
        "Analytics": ["Google Analytics (GA4)", "Mixpanel", "Amplitude"],
        "Customer Data": ["Segment", "Tealium", "mParticle"],
        "Commerce": ["Shopify Plus", "Magento"],
    }

    for cat_name, tools in taxonomy.items():
        # Create Category
        cat, created = Category.objects.get_or_create(
            name=cat_name, 
            defaults={'slug': slugify(cat_name)}
        )
        status = "Created" if created else "Found"
        print(f"[{status}] Category: {cat_name}")

        # Create Tools
        for tool_name in tools:
            Tool.objects.get_or_create(
                name=tool_name,
                category=cat,
                defaults={'slug': slugify(tool_name)}
            )

    # Check what exists after
    print(f"Categories after: {Category.objects.count()}")
    print("--- INJECTION COMPLETE ---")

if __name__ == '__main__':
    run()